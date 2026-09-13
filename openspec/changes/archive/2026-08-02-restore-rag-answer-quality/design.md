## Context

Pipeline atual em `backend/app/services/rag_service.py` (~1580 linhas), grafo LangGraph `retrieve → generate → evaluate → (retrieve_retry)*`. Config em `backend/app/utils/rag_config.py`. Corpus indexado: **124 chunks / ~170k caracteres** em 4 PDFs (`BIP 2024`: 57 chunks; `Genetic characterization`: 53; `BIA_RAG`: 8; `Indice volumetrico`: 6) — `chunk_size=1600`, `overlap=200`. `RETRIEVAL_K=40` é 32% de todo o corpus.

Este change consome o instrumento de medição corrigido em `fix-rag-eval-harness-fidelity` (deve ser aplicado antes) e usa o run `pre-fase-a` gerado lá como baseline de comparação.

Dados medidos que embasam as decisões abaixo (golden set, 28 perguntas, config de produção: `text-embedding-3-large`, chunk 1600, threshold 0.65, `k=40`, expansão de query LLM ligada):

- Distribuição de `retrieved_count`: 12 perguntas com 1-6 chunks, 8 com 40 chunks, 2 com 0 (recusa), **nenhuma entre 7 e 39**.
- `top_similarity` médio in-corpus: **0.628** — abaixo do `PRIMARY_RPC_SIMILARITY_THRESHOLD=0.65`.
- Similaridade não separa in/out-of-corpus de forma confiável: `oos-doenca-estreptococose` marca 0.620, acima de perguntas legítimas como `gen-etica-amostragem` (0.539) e `fu-gen-menor-valor` (0.544).
- Rank do primeiro chunk correto (`first_hit_rank`), com expansão de query LLM ligada: a maioria ≤ 3, mas alguns em 11, 14 (`fu-kv-medidas`, `bip-rpl-extremos`) — testado A/B contra expansão desligada (mesmo chunk/threshold): expansão ligada tem recall maior (0.833 vs 0.792) e groundedness maior (98.8 vs 89.6), então permanece ligada; a implicação é que a janela de contexto precisa ser ampla o suficiente para não perder ranks 11-14.

## Goals / Non-Goals

**Goals:**
- Toda pergunta recebe um contexto de tamanho estável — nem faminto nem inundado — independente de onde a similaridade do melhor candidato cai.
- Uma pergunta fora do escopo recebe recusa honesta e limpa, nunca um formulário preenchido com "não disponível".
- A resposta é prosa contínua, legível como a maioria das plataformas de LLM — tópicos só para destacar, nunca como estrutura obrigatória.
- Citações refletem exatamente os documentos que embasaram a resposta.
- O ciclo de avaliação do LangGraph (`evaluate`) continua funcional após a mudança de formato, sem depender de nenhum cabeçalho.

**Non-Goals:**
- Não implementa busca híbrida léxico+vetorial (change `add-hybrid-lexical-vector-search`) nem grading semântico de contexto pré-geração ou verificação numérica pós-geração (change `add-rag-self-correction-loop`) — este change resolve o que é possível só ajustando seleção, prompt e citações.
- Não altera `retrieve_retry` nem seu bypass do piso de recusa (`skip_threshold=True`) — esse nó é substituído inteiro pelo `grade_context` da change `add-rag-self-correction-loop`, que decide antes de gerar em vez de tentar de novo depois. Este change só ajusta `evaluate`/`should_retry` (contagem de tentativas e o tipo de pergunta considerado), que são pré-requisito da mudança de formato de resposta e não dependem do redesenho do retry.
- Não decompõe perguntas de "maior e menor" em sub-buscas — fica condicional a medir se a janela de 16 chunks já resolve (ver change de self-correction).
- Não muda o chunking nem reingesta documentos.
- Não troca o provedor de LLM — permanece OpenAI, só varia o modelo dentro da mesma família.

## Decisions

**1. Seleção por ranking com piso e teto, não portão binário.** Substituir a lógica atual (`if above_threshold: só isso; elif above_floor: tudo; else: nada`) por: se o melhor candidato não atinge o piso de recusa → recusa; senão, uma janela relativa ao melhor score (`top - margem`) determina o corte natural; se essa janela produzir menos que o mínimo, completa até o mínimo com os próximos melhores candidatos (nunca deixa faminto); a lista final é limitada a um teto de chunks e a um orçamento de caracteres.

   *Valores*: mínimo 8 chunks (elimina a fome que causa a maioria das falhas medidas), teto 16 (cobre os ranks 11-14 observados com expansão de query ligada), orçamento de 22000 caracteres (~5.5k tokens — reduz ~3.6× o pior caso atual de ~80k chars/20k tokens). Margem relativa 0.08 e piso absoluto 0.45 controlam a forma da janela sem nunca bloquear o preenchimento mínimo. `REFUSAL_FLOOR_SIMILARITY=0.53` é preservado sem alteração — é o único gate calibrado contra dados reais de separação in/out-of-corpus.

   *Alternativa rejeitada*: manter um `k` fixo simples (ex.: sempre os 10 melhores, sem piso de similaridade). Rejeitada porque não distingue "10 chunks genuinamente relevantes" de "10 chunks arbitrários de uma pergunta fora do escopo" — o piso de recusa continua necessário como primeira decisão, antes de qualquer contagem.

**2. Confiança como sinal contínuo (`strong`/`partial`), não gate binário de tudo-ou-nada.** Hoje "abaixo do threshold" nunca chega a gerar — ou é tratado como se fosse igualmente confiável (zona fraca antiga) ou é descartado. Com a seleção por ranking sempre produzindo um contexto, a diferença entre confiança alta e parcial vira uma instrução de tom na geração (ressalva explícita), não uma decisão de incluir/excluir dados. Implementa diretamente a postura escolhida pelo usuário: responder com ressalva na zona de incerteza, não recusar.

**3. Um prompt base em prosa, tipo de pergunta como ênfase de uma linha.** Rejeitado manter 4 templates completos e só remover os cabeçalhos "por dentro" de cada um — os quatro templates são 90% estrutura repetida (regras de fundamentação, instrução de idioma, instrução de fidelidade) com uma seção de layout diferente. Colapsar em 1 prompt + 4 linhas de ênfase é mais simples de manter e elimina a tentação de reintroduzir estrutura obrigatória em um dos quatro no futuro. Os exemplos com números reais de um estudo específico (`FIS 0.44`, `DEST 0.00-0.818`) são removidos — não são mais necessários sem formato de tabela a exemplificar, e representavam um few-shot anchor perigoso (convite a vazar números de um estudo para perguntas sobre outro).

**4. Sentinela textual para recusa, detectado e substituído em `generate`.** Alternativa considerada: usar `insufficient_context` (já existe no `State`) para decidir recusa *antes* de chamar o LLM. Isso continua sendo o caminho primário (contexto vazio → recusa sem custo de LLM, como hoje). O sentinela cobre o caso em que o contexto *existe* mas, mesmo com ressalva, o modelo conclui que não pode responder — situação que hoje é impossível de expressar porque o prompt proíbe a recusa. Sem o sentinela, esse caso teria que ser detectado por heurística sobre a prosa livre, que é frágil; com um marcador textual explícito instruído no prompt, a detecção é uma comparação exata.

**5. Citações discretas por página, não span min/max.** O span atual mistura literalmente todas as páginas entre o menor e o maior número visto — com seleção de contexto ampla (companions incluídos), isso produzia "página 0 a 15" para uma resposta que na verdade usou 2 chunks específicos. Trocar por lista de páginas realmente presentes nos chunks que entraram no contexto final (pós-seleção, pós-orçamento), agrupada em intervalo só onde as páginas forem de fato contíguas. Chunks de companion são excluídos das citações a menos que o arquivo já esteja citado por um chunk genuinamente recuperado — um chunk trazido só por densidade de dígitos nunca justificou, sozinho, citar um documento novo.

**6. Modelo de geração separado do modelo utilitário.** Uma única instância de LLM (`gpt-4o-mini`, temperature 0) hoje atende geração de resposta, expansão de query e condensação de follow-up. Para Q&A científico com números e tabelas, a chamada de geração é o gargalo de qualidade mais isolável — subir só ela captura a maior parte do ganho por menor custo incremental (1 chamada por pergunta, versus 2-3 chamadas utilitárias mais baratas que não precisam do mesmo raciocínio). O modelo utilitário permanece `gpt-4o-mini`. Ambos configuráveis por variável de ambiente, permitindo comparação A/B sem deploy.

**7. Companions limitados, não removidos.** `_add_data_companion_chunks` é hoje a única fonte de duas tabelas específicas que a busca semântica não recupera bem (`gen-fis-extremos`, `bip-rpl-extremos`) — confirmado comparando resposta de produção (correta, via companion) contra medição de retrieval puro (que não vê companions). Removê-lo agora regrediria essas duas perguntas até que a busca híbrida (change futura) proveja paridade. Em vez disso: teto total (não por arquivo), elegibilidade restrita a arquivos já presentes no top-3 do ranking, e inclusão no orçamento de caracteres — elimina o pior caso (~20 chunks de um único arquivo irrelevante) sem eliminar o benefício real.

## Risks / Trade-offs

- **[Risco] A seleção por ranking pode perder, em algumas perguntas, chunks que hoje só apareciam graças à inundação de 40 candidatos.** Aceito e esperado — é o motivo de a change de busca híbrida (fase seguinte do programa) existir; será medido explicitamente comparando contra o baseline `pre-fase-a`. Se o `mean_recall` cair de forma inaceitável antes da híbrida estar pronta, o teto pode ser ajustado via env sem novo deploy de código.
- **[Trade-off] Modelo de geração mais caro por chamada.** Mitigado pela própria mudança de seleção de contexto, que corta ~3.6× os tokens de entrada — o custo líquido por pergunta deve ficar próximo ou abaixo do atual.
- **[Risco] Mudar o contrato de `sources` é breaking para o frontend.** Mitigação: as duas pontas (`backend/app/services/rag_service.py` e `frontend/components/ChatMessage.tsx`/`frontend/hooks/useChat.ts`) são alteradas na mesma change; não há período de compatibilidade dupla porque não há consumidor externo do contrato além deste frontend.
- **[Risco] Sem o teste de formato (nenhum cabeçalho de seção nas respostas), pode ser tentador reintroduzir estrutura obrigatória em uma correção futura isolada.** Mitigação: a suíte de verificação deste programa inclui uma checagem de regressão de formato (ver Fase de verificação do plano) que falha se qualquer resposta contiver os marcadores antigos (`DATA:`, `COMPARISON:`, `Empty section.` etc.).
- **[Risco] Reescrever `evaluate` junto com a remoção de cabeçalhos é obrigatório, não opcional** — sem essa mudança simultânea, o avaliador reprovaria toda resposta válida (ele procura literalmente `"COMPARISON:" in answer`) e o grafo entraria em retries infinitos até o teto. Esta dependência está refletida nas tasks como um único grupo de trabalho, não duas tarefas independentes.

## Migration Plan

Sem migração de dados. Passos de rollout:
1. Implementar prompt único + sentinela + `evaluate` reescrito juntos (mesmo commit — ver risco acima).
2. Implementar seleção por ranking + constantes novas em `rag_config.py`.
3. Implementar citações discretas; atualizar frontend no mesmo change.
4. Implementar separação de modelo de geração/utilitário atrás de variáveis de ambiente.
5. Limitar companions.
6. Rodar `run_eval.py --full` e comparar contra `pre-fase-a`; ajustar constantes de seleção via env se necessário, sem novo código.
7. Verificação end-to-end manual no app rodando localmente (backend `:8000`, frontend `:3000`).

Rollback: todas as constantes novas (`CONTEXT_MIN_CHUNKS`, `CONTEXT_MAX_CHUNKS`, `CONTEXT_CHAR_BUDGET`, `GENERATION_MODEL`, `DATA_COMPANION_MAX_TOTAL`) são lidas de variável de ambiente com default — reverter para o comportamento anterior não exigiria reverter o commit, mas reverter é a via recomendada já que o formato de prompt e citações não têm flag de rollback parcial (são substituições completas, não aditivas).

## Open Questions

- Modelo exato de geração (`gpt-4o` vs outro da família mais recente disponível no momento da implementação) — decidir no momento de implementar, verificando disponibilidade/pricing atuais; não bloqueia o resto do design.
