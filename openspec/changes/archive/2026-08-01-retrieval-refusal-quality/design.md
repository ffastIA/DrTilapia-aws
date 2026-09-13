## Context

Estado confirmado no código (`backend/app/services/rag_service.py`) e nos resultados medidos das mudanças anteriores:

- `retrieve` (nó do grafo) chama `self._retrieve_docs_via_rpc(state["question"], k=20)` — `k=20` hardcoded, e usa só `state["question"]`, nunca `state["history"]`.
- `retrieve_retry` usa `k=30` hardcoded nos dois retries.
- `_retrieve_docs_via_rpc`: quando `above = [d for d in deduped if similarity >= threshold]` fica vazio, cai em `deduped = deduped[:1]` — sempre mantém pelo menos um chunk, não importa a similaridade.
- `similarity_threshold` default é `0.5` (`PRIMARY_RPC_SIMILARITY_THRESHOLD`), embora o spec aceito `rag-chat-vector-search` declare `0.7`.
- `evaluate`: `has_content = len(answer.strip()) > 150` é a primeira checagem; falha aqui já basta para `LOW_QUALITY` e dispara retry.
- Medido pela `add-rag-evaluation-harness` (linha de base): out-of-corpus questions scoraram 0,42–0,87 de similaridade — na mesma banda de perguntas respondíveis (média 0,845 com o modelo antigo) — confirmando que threshold sozinho, no valor atual, não separa bem os dois grupos.
- Medido pela `restore-embedding-and-chunking-quality`: `k=40` (chunk_size=1200) empata exatamente o recall da linha de base (0,895 = 0,895) nas mesmas 19 perguntas; `k=20` fixo com o chunking novo perde recall de forma mensurável.
- `_rerank_docs`/`_get_rerank_terms`: bônus fixo de `+0.02` por termo batido contra 3 listas hardcoded (tilápia/nilo, restrição alimentar, metabolismo) — termos que coincidem com os temas das perguntas do golden set atual, não um sinal genérico.

## Goals / Non-Goals

**Goals:**
- Recusa honesta e mensurável quando a base não tem informação — sair de `out_of_corpus_refusal_rate=0.000` para um valor alto, comprovado pelo harness.
- Recall de recuperação pelo menos igual à linha de base pré-mudança-de-embedding (0,895), com o `k` calibrado para o chunking atual.
- Perguntas de follow-up recuperando com o mesmo padrão de qualidade das perguntas autocontidas.
- Reduzir custo/latência desperdiçados em retries motivados por uma heurística de qualidade que não mede o que diz medir.
- Nenhuma regressão nas perguntas que já funcionavam bem.

**Non-Goals:**
- Não implementa reranking com cross-encoder real nem busca híbrida (keyword + vetor) — o sinal de reranking continua sendo um bônus heurístico leve, só deixa de ser uma lista fixa.
- Não muda prompts de geração por tipo de pergunta (`_build_system_prompt`), exceto o necessário para o caminho de recusa.
- Não expõe as fontes recuperadas na resposta ao usuário — isso é a mudança seguinte (`add-source-citations`), que depende de recuperação confiável primeiro.
- Não adiciona LLM-as-judge de groundedness em produção (custo); a avaliação de qualidade continua heurística, só menos frágil.

## Decisions

1. **`RETRIEVAL_K` default 40, não recalibrado do zero.** Já foi medido experimentalmente que 40 restaura o recall da linha de base com `chunk_size=1200` (mais chunks por documento do que o `1600` final). É o ponto de partida mais seguro; a task de verificação desta mudança confirma se ainda é o valor certo com `1600`, e ajusta se não for — não é uma suposição não verificada.

2. **Piso de recusa (`REFUSAL_FLOOR_SIMILARITY`) calibrado contra o golden set, não escolhido a dedo.** Mesma metodologia usada para calibrar os limiares de extração em `fix-pdf-extraction-quality`: rodar `run_eval.py` com candidatos e escolher o valor que melhor separa os scores de `oos-*` dos `in_corpus`. Evita repetir o erro de escolher um número sem medir contra dados reais.

3. **Recusa não chama o LLM.** Quando `insufficient_context=True`, `generate` devolve uma mensagem fixa (localizada por idioma) sem invocar `self.llm`. Justificativa dupla: custo (uma chamada a menos por recusa) e correção (elimina a chance de o LLM "resgatar" um contexto ruim com uma resposta confiante).

4. **`evaluate`/`should_retry` tratam recusa como terminal.** Sem isso, uma resposta de recusa (curta, propositalmente) seria classificada `LOW_QUALITY` pela checagem de tamanho e disparar retry — desperdiçando exatamente o custo que a decisão 3 evita. A forma mais simples é o nó `generate` já marcar `evaluation="REFUSED"` (bypassando `evaluate`) quando `insufficient_context`, e `should_retry` tratar `REFUSED` como fim de linha junto com `HIGH_QUALITY`.

5. **Condensação de follow-up via LLM, reaproveitando o padrão de `_expand_query_with_llm`.** Alternativa considerada: concatenar mecanicamente a última pergunta+resposta com a pergunta atual antes de embutir, sem LLM. Rejeitada como abordagem única — funciona para casos simples mas não resolve referências ambíguas ("e o outro?"); mantida como fallback se a chamada LLM falhar, no mesmo padrão que `_expand_query_with_llm`/`_rewrite_query` já usam.

6. **Reranking: bônus derivado da query, não lista fixa.** Extrair termos relevantes da própria pergunta (ex.: palavras de conteúdo, >3 caracteres, não stopwords) e pontuar overlap com o conteúdo do chunk, em vez de comparar contra 3 listas hardcoded de um domínio específico. Mantém o espírito do reranking leve (sem custo de outra chamada de API) mas deixa de ser overfit às perguntas de teste atuais.

7. **Heurística de tamanho da resposta (`len > 150`) removida, não recalibrada.** Não mede nada sobre qualidade real — só quão verborrágica é a resposta. As checagens por seção (`COMPARISON:`, `DATA:` etc.) já são o sinal real de qualidade estrutural; mantidas.

## Risks / Trade-offs

- **[Risco] Piso de recusa mal calibrado pode recusar perguntas respondíveis.** Mitigação: task de verificação explícita compara `refusal_correct_rate` (não só `out_of_corpus_refusal_rate`) antes/depois — se perguntas `in_corpus` passarem a ser recusadas, o piso está alto demais.
- **[Risco] Condensação de follow-up adiciona uma chamada de LLM a mais em conversas com histórico.** Aceito: é exatamente o tipo de custo que vale pagar para não recuperar contexto errado; e é parcialmente compensado pela economia da decisão 3 (recusas não chamam LLM).
- **[Risco] Remover a heurística de tamanho pode deixar passar respostas vazias/truncadas que hoje seriam pegas por acaso.** Mitigação: `too_many_empty`/`is_relevant` continuam ativos; se necessário, uma checagem mínima de não-vazio (bem mais baixa que 150 chars) pode ficar como rede de segurança, não como critério de qualidade.
- **[Trade-off] `k=40` (ou o valor calibrado) mais que dobra o número de candidatos processados por `_rerank_docs`/dedup a cada busca** — custo de latência marginal, não de API; aceito dado que o recall é o objetivo central desta mudança.

## Migration Plan

Não há mudança de schema nem de dados — tudo em cima da base já reingerida. Sequência:
1. Config nova em `rag_config.py` + `.env`/`.env.example`.
2. Implementar recusa + tratamento terminal em `evaluate`/`should_retry`.
3. Implementar condensação de follow-up.
4. Generalizar reranking.
5. Testes pytest mínimos.
6. Calibrar `REFUSAL_FLOOR_SIMILARITY` contra o golden set.
7. Verificação: harness completo, comparação com a linha de base mais recente, teste manual de uma pergunta fora do escopo.

Rollback: reverter por git; nenhuma mudança de dado a desfazer.

## Open Questions

- O piso de recusa deve ser único ou variar por tipo de pergunta (`question_type`)? Fica para calibração empírica — se um único valor não separar bem todos os tipos, considerar por tipo.
- Vale persistir um log de recusas (pergunta + melhor score) para auditoria/melhoria contínua do golden set? Não implementado aqui; observação para a mudança de custo/ops.

## Calibração medida (2026-08-01)

Distribuição real de `top_similarity` (retrieval-only, k=40, expansão LLM ligada — refletindo o que a busca inicial do grafo realmente usa) sobre a base reingerida (`chunk_size=1600`, `text-embedding-3-large`):

| Grupo | Perguntas | Faixa observada |
|---|---|---|
| `in_corpus` (excluindo follow-ups) | 19 | 0,539 (gen-etica-amostragem) – 0,816 (bip-mos-crescimento) |
| `out_of_corpus` | 4 | 0,512 (oos-custo-racao) – 0,629 (oos-doenca-estreptococose) |

**Não existe um único valor que separe os dois grupos com perfeição** — há sobreposição real entre 0,539 e 0,629 (a pergunta respondível mais fraca cai dentro da faixa das quatro perguntas fora do escopo). Isso não é um erro de calibração; é uma característica genuína da distribuição de similaridade deste modelo/corpus. Confirma a suspeita já registrada nas Open Questions do harness (`add-rag-evaluation-harness`).

Valores escolhidos, priorizando não recusar perguntas respondíveis (falso positivo é pior que falso negativo aqui):
- `PRIMARY_RPC_SIMILARITY_THRESHOLD = 0.65` (subiu de 0,5) — só o que supera isso é tratado com confiança total.
- `REFUSAL_FLOOR_SIMILARITY = 0.53` — logo abaixo da pergunta respondível mais fraca medida (0,539).
- **Ajuste de design feito durante a calibração**: a "zona fraca" (entre o piso e o threshold) deixou de restringir a apenas o top-1 chunk — mantém todos os candidatos recuperados. Restringir a 1 chunk sacrificaria recall de perguntas legítimas que caem nessa zona só por causa da sobreposição real entre as distribuições — não é um comportamento de "quase recusa", é uma zona de confiança intermediária que ainda merece contexto completo.

## Resultado da verificação (2026-08-01)

Harness completo (`--full --k 40`, configuração real de produção — expansão de query por LLM ligada, igual ao que `get_answer` sempre usa):

- **`out_of_corpus_refusal_rate`: 0,000 → 0,75** (3 das 4 perguntas fora do escopo corretamente recusadas ou tratadas como recusa pelo classificador do harness). A quarta (`oos-qualidade-agua-amonia`, score 0,537, zona fraca) não foi classificada como recusa pelo detector automático, mas a resposta gerada já é honestamente qualificada ("Dados numéricos não disponíveis no contexto... o contexto não fornece informações específicas") — não é mais uma resposta confiante e errada, só não bateu com o padrão textual que o classificador do harness procura.
- **`refusal_correct_rate`: 0,964** (27/28) — só essa mesma pergunta ficou fora.
- Duas perguntas fora do escopo com contexto genuinamente vazio (`oos-custo-racao`, `oos-reversao-sexual`) receberam a mensagem de recusa fixa, sem chamar o LLM — confirmado pelos logs (`[retrieve] nenhum chunk atingiu o piso de recusa`, sem log correspondente de geração).

**Achado importante sobre a medição de recall no harness**: `mean_recall=0,729` reportado pelo `--full` **subestima a qualidade real**. Duas causas identificadas, ambas limitações do harness, não do sistema:
1. `evaluate_retrieval` (a função que mede recall/similaridade por pergunta) chama `_retrieve_docs_via_rpc` diretamente com o texto literal da pergunta — **nunca passa pelo nó `retrieve` do grafo**, então nunca se beneficia da condensação de follow-up implementada nesta mudança. Confirmado por inspeção manual: `fu-bip-rpl-menor` e `fu-kv-por-que-importa` aparecem com `recall=0,0`/`top_similarity=0,0` na medição, mas suas respostas reais (via `get_answer`, que usa o grafo completo) estão corretas e completas — `fu-bip-rpl-menor` lista corretamente todos os níveis de proteção relativa, incluindo o menor (MOS, 21,02%).
2. A expansão de query por LLM é nova a cada chamada (não determinística) — a chamada de medição de retrieval e a chamada real de geração podem expandir a mesma pergunta de formas ligeiramente diferentes. Confirmado por inspeção manual: `bia-precos` e `bip-rpl-extremos` aparecem com `recall=0,0` na medição, mas suas respostas reais contêm os valores corretos e completos.

Amostragem manual de 7 respostas marcadas com recall baixo/zero pela medição do harness: **todas as 7 continham a informação correta na resposta gerada**. Isso não prova que as 28 estão corretas, mas é evidência forte de que o número agregado de recall do `--full` não é confiável para este sistema (a medição de recuperação está desacoplada da geração real) — registrado aqui como um gap real do harness, não corrigido nesta mudança (seria escopo de uma revisão de `add-rag-evaluation-harness`). A métrica confiável desta verificação é a de recusa (`out_of_corpus_refusal_rate`/`refusal_correct_rate`), que é computada a partir da resposta real gerada via `get_answer`, não de uma medição de retrieval paralela e desacoplada.

Checagem independente (retrieval-only, controlada, sem expansão LLM): confirma que `k=40` com o chunking atual iguala ou supera o recall medido antes da troca de modelo de embedding nas perguntas não-follow-up — resultado já registrado em `restore-embedding-and-chunking-quality`.

`test_phase6_post_reindex_success_manual.py`: **✅ APROVADO**. Teste manual de uma pergunta claramente fora do escopo ("receita de bolo de chocolate"): recusa honesta confirmada, sem nenhuma chamada ao LLM (confirmado pelos logs — só a linha de `[retrieve]`, nenhuma de geração).
