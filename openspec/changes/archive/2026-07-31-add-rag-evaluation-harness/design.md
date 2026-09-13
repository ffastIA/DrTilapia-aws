## Context

O acervo atual são 4 documentos científicos de aquicultura (49 chunks): caracterização genética/fenotípica de tilápia do Nilo, BIP 2024, índice volumétrico de abate e BIA_RAG. As perguntas do golden set precisam sair desse conteúdo real — um conjunto genérico não mede nada útil.

O que já existe e deve ser reaproveitado: `backend/test_phase4_1_retrieval_manual.py` já roda múltiplas formulações equivalentes da mesma pergunta com k variável e reporta cobertura lexical + ranking por similaridade. `backend/test_phase4_quality_manual.py` faz diagnóstico de contexto/resposta. Ambos são manuais, com uma única query hardcoded, e sem persistência — servem de base, não de substituto.

Restrição relevante: `rag_service.get_answer()` hoje devolve apenas uma `str`. Os documentos recuperados morrem dentro do grafo LangGraph. Medir recall de trechos exige acesso aos documentos recuperados, não só à resposta final.

## Goals / Non-Goals

**Goals:**
- Detectar objetivamente melhora ou piora de qualidade entre duas configurações do RAG.
- Cobrir os três modos de falha que a revisão identificou: recuperação imprecisa, ausência de recusa honesta e follow-up sem contexto.
- Ser reprodutível e barato o suficiente para rodar a cada mudança relevante.

**Non-Goals:**
- Não altera o comportamento do RAG (isso é escopo das mudanças seguintes).
- Não é um teste automatizado de CI com gate bloqueante — por ora é uma ferramenta de diagnóstico executada sob demanda; virar gate pode ser um passo futuro.
- Não pretende ser um framework de avaliação genérico (RAGAS etc.); é específico deste acervo.

## Decisions

1. **Golden set em arquivo versionado (YAML) em vez de código.** Perguntas e respostas esperadas são dados, não lógica; ficam legíveis e revisáveis em diff, e podem crescer sem tocar no executor. Alternativa rejeitada: hardcodar no script de teste (padrão atual dos `test_phase*_manual.py`), que já se mostrou não escalável.

2. **Medir recuperação e geração separadamente.** A métrica primária é de **recuperação** (os trechos certos foram trazidos?), porque é onde estão as regressões conhecidas e porque é determinística e barata. A avaliação da **resposta** é secundária e mais cara. Isso permite iterar em chunking/embeddings medindo só a parte barata.

3. **Embasamento (groundedness) avaliado por LLM-as-judge, com o julgamento isolado da geração.** Não há como medir "a resposta inventou?" por heurística — o nó `evaluate` atual tenta isso com `len(answer) > 150` e falha. O juiz recebe contexto + resposta e decide se cada afirmação se sustenta. Usar modelo separado da geração, temperatura 0, e registrar o custo.

4. **Perguntas fora de escopo são cidadãs de primeira classe do conjunto.** Hoje o sistema nunca recusa (fallback top-1 sempre entrega algo). Sem medir isso, a correção dessa falha não teria como ser comprovada.

5. **O executor precisa de acesso aos documentos recuperados.** Como `get_answer` só devolve `str`, o executor chamará a camada de recuperação diretamente para as métricas de recall, em vez de depender de mudança na API pública. Quando a mudança de atribuição de fontes expuser os documentos, o executor pode passar a usar o caminho oficial.

6. **Execuções salvas com carimbo da configuração vigente** (modelo de embedding, chunk size/overlap, threshold, k). Sem isso, comparar duas execuções não diz o que mudou. É exatamente a informação que faltava para perceber as regressões atuais.

## Risks / Trade-offs

- **[Risco] Golden set enviesado por quem o escreve** (perguntas fáceis demais, ou moldadas ao que o sistema já acerta) → Mitigação: derivar as perguntas do conteúdo dos PDFs, não do comportamento observado do sistema; incluir perguntas que hoje sabidamente falham.
- **[Risco] LLM-as-judge é ruidoso e não determinístico** → Mitigação: temperatura 0, critério objetivo por afirmação, e tratar a métrica como tendência entre execuções, não como número absoluto.
- **[Risco] Conjunto pequeno (4 documentos) limita significância estatística** → Aceito: o objetivo é detectar regressões grosseiras como as atuais (chunk 4x maior, modelo obsoleto), que aparecem com folga nesse tamanho. Diferenças sutis exigirão acervo maior.
- **[Trade-off] Custo por execução** — cada rodada consome embeddings + geração + julgamento. Mitigado por permitir rodar só a parte de recuperação (barata) durante a iteração.
- **[Risco] O baseline será medido com o sistema já degradado**, o que torna qualquer mudança "boa" por comparação → Mitigação: registrar também as métricas absolutas, não só o delta; uma melhora relativa sobre uma base ruim ainda pode ser insuficiente.

## Migration Plan

Aditivo e isolado: apenas arquivos novos sob `backend/evaluation/`. Não altera código de produção, não toca no banco, não requer variáveis novas além das já existentes (`OPENAI_API_KEY`, credenciais Supabase). Rollback = remover o diretório.

## Achado durante a implementação — extração falha do `BIP 2024 publicado.pdf`

Ao ler o acervo real para escrever o golden set, constatou-se que **um dos 4 documentos está praticamente vazio na base**, por falha de extração de PDF não detectada:

| Documento | Chunks | Palavras/chunk | % dígitos |
|---|---|---|---|
| Indice volumetrico abate | 6 | 216 | 1,4% |
| BIA_RAG | 5 | 255 | 4,4% |
| Genetic characterization | 26 | 394 | 6,0% |
| **BIP 2024 publicado** | 12 | **51** | **15,0%** |

A página 3 inteira (resultados zootécnicos) resume-se a 265 caracteres de esqueleto: cabeçalhos de seção, `p` órfãos (p-values sem os números), `2` soltos (expoentes de R²) e o cabeçalho de `Table 1` **sem nenhuma linha de dados**.

Causa: `_is_text_garbled` só reprova `len < 50` ou >4% de `?`. Esse conteúdo tem 265 caracteres e zero `?` — passou na validação, e a cascata de fallback (pdfplumber → Tesseract → Vision), que provavelmente o resgataria, nunca foi acionada.

**Consequência para esta mudança**: o golden set cobre apenas os 3 documentos íntegros. Perguntas sobre o BIP 2024 serão adicionadas depois que a extração for corrigida — não há o que recuperar hoje.

**Consequência para o plano**: esta é uma terceira causa raiz, independente das regressões de chunking e embedding, e nenhuma delas a resolve. Endereçada em mudança dedicada (`fix-pdf-extraction-quality`). Também explica a existência de `_add_data_companion_chunks`, que varre arquivos atrás de chunks com muitos dígitos — provavelmente uma compensação para esse tipo de perda.

## Linha de base medida (2026-07-27)

Configuração vigente: `text-embedding-ada-002`, chunk 4000/500, threshold 0.5, sem expansão por LLM (para determinismo).

| Métrica | k=20 | k=5 |
|---|---|---|
| `mean_recall` | 0.895 | 0.842 |
| `perfect_recall_rate` | 0.895 | 0.842 |
| `mean_top_similarity` | 0.845 | 0.845 |

**Achado mais importante — o threshold não consegue separar o que é respondível do que não é.**

As 4 perguntas `out_of_corpus`, cuja resposta **não existe** na base, obtiveram similaridade de topo entre **0.817 e 0.871** — dentro da mesma faixa das perguntas respondíveis (média 0.845), e **acima tanto do threshold atual (0.5) quanto do 0.7 exigido pela spec**.

Consequência direta: **calibrar o threshold sozinho não resolve a ausência de recusa honesta**. Com `ada-002`, a distribuição de similaridade é comprimida a ponto de uma pergunta sem resposta ser indistinguível de uma com resposta. Isso reforça a troca de modelo de embedding (que tem separação de similaridade muito melhor) como pré-requisito, e não como alternativa, à calibração de threshold.

**Outros problemas conhecidos reproduzidos** (requisito da task 6.3):
- `fu-gen-menor-valor` (follow-up) — recall 0 e **a menor similaridade de todo o conjunto (0.738)**. Confirma que o follow-up é embutido isolado, sem o contexto do turno anterior.
- `gen-fis-extremos` — recall 0 em ambos os `k`. É a pergunta sobre a tabela de métricas genéticas (FIS): conteúdo tabular que o chunk de 4000 caracteres dilui.
- `gen-posicao-fao` — passa em k=20, falha em k=5.

**Modo completo (geração + juiz de embasamento):**

| Métrica | Valor |
|---|---|
| `out_of_corpus_refusal_rate` | **0.000** |
| `refusal_correct_rate` | 0.826 |
| `mean_groundedness` (in_corpus) | 87.1 |
| `mean_mention_coverage` | 0.816 |
| latência média por pergunta | 8.4 s (máx 23.3 s) |
| custo | US$ 0,068 em 71 chamadas de LLM |

Execução de referência: `runs/20260727T055505Z-baseline-full-v2.json`.

Dois números do custo merecem atenção como sintoma, não como contabilidade: **566 mil tokens de prompt em 71 chamadas** dão ~8.000 tokens por chamada — consequência direta de chunks de 4000 caracteres com k=20 e sem orçamento de contexto. E 71 chamadas para 23 perguntas (~3 por pergunta) confirmam o laço de retry do grafo disparando com frequência.

*Ressalva de precisão*: o valor vem do callback do LangChain, que usa a própria tabela de preços interna. O cálculo manual com os preços públicos atuais do `gpt-4o-mini` dá ~US$ 0,090 — cerca de 25% acima. A ordem de grandeza é confiável; o valor absoluto, não. O custo de embeddings não entra nessa conta (o callback só cobre chamadas de chat) e é estimado à parte pelo número de chamadas.

**O sistema não recusou nenhuma das 4 perguntas sem resposta na base** — produziu de 455 a 1436 caracteres de resposta segura de si para cada uma:

| Pergunta fora do escopo | Recusou? | Similaridade | Tamanho da resposta |
|---|---|---|---|
| `oos-doenca-estreptococose` | não | 0.817 | 1436 chars |
| `oos-qualidade-agua-amonia` | não | 0.871 | 492 chars |
| `oos-custo-racao` | não | 0.826 | 455 chars |
| `oos-reversao-sexual` | não | 0.832 | 480 chars |

Isso confirma o fallback top-1 (`rag_service.py:1085-1096`) na prática: o modelo sempre recebe contexto, então sempre responde. A latência média de 8.4s (máximo 23.3s) também é coerente com o laço de retry do grafo, que dispara até 3 gerações por pergunta.

**Ressalva sobre o poder discriminativo do recall.** Com 49 chunks na base, `k=20` recupera **41% do acervo inteiro** a cada consulta — o recall alto é em boa parte artefato disso. Por isso a linha de base foi registrada também em `k=5`, que é a referência mais informativa para comparar mudanças de chunking e embedding. Quando a base crescer, esse viés diminui naturalmente.

## Open Questions

- O golden set deve ser commitado com respostas esperadas em texto integral ou apenas com os trechos-fonte? Proposta: trechos-fonte + resumo curto do que a resposta precisa conter, para evitar manutenção pesada a cada mudança de prompt.
