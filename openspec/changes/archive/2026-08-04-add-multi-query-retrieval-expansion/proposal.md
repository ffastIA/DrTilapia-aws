## Why

O RAG está satisfatório em qualidade, mas continua restritivo demais quando
o usuário não fraseia a pergunta com a terminologia exata dos documentos —
comum, já que a maioria dos usuários não é especialista no vocabulário
técnico/científico do corpus. Hoje `_retrieve_docs_via_rpc` embute e busca
com **uma única** formulação da pergunta (original + um bloco de sinônimos
apendado por LLM). Se o cosseno bruto dessa única busca não cruzar o piso de
recusa calibrado (`REFUSAL_FLOOR_SIMILARITY=0.53`), a recuperação retorna
vazia e `grade_context` **nunca chega a chamar o juiz LLM** que distingue
"mesmo assunto" de "assunto diferente parecido" — a pergunta é recusada só
por distância de embedding de uma formulação, antes de qualquer julgamento
semântico. A única retentativa existente é puramente baseada em regras (meia
dúzia de pares de termos fixos), insuficiente para fraseados coloquiais
genéricos.

## What Changes

- `_retrieve_docs_via_rpc` passa a buscar com **múltiplas variantes** da
  pergunta (original + expansão por sinônimos já existente + uma nova
  paráfrase em registro técnico/científico), geradas por uma única chamada
  LLM, atrás de uma flag (`MULTI_QUERY_EXPANSION_ENABLED`, default `false`).
- Os resultados das buscas por variante são fundidos por chunk mantendo a
  **maior similaridade de cosseno entre as variantes** (não RRF — todas as
  buscas usam o mesmo espaço vetorial, então a fusão por máximo preserva
  exatamente a calibração existente de `REFUSAL_FLOOR_SIMILARITY`/
  `CONTEXT_ABSOLUTE_FLOOR`/`CONTEXT_RELATIVE_MARGIN`, sem precisar
  recalibrar nada).
- `_select_context_docs`, o gate de recusa, `grade_context`,
  `reformulate_and_retrieve` e a busca híbrida léxica permanecem
  **inalterados** — a mudança só afeta como os candidatos vetoriais são
  coletados antes de chegarem a esse pipeline já validado.
- Nova categoria de perguntas coloquiais (`col-*`) no golden set, irmãs de
  perguntas `in_corpus` já existentes, para medir se a mudança de fato
  resolve o problema relatado — hoje não há nenhuma cobertura desse tipo de
  fraseado no harness.
- Ajustes no harness (`run_eval.py`) para contabilizar corretamente o custo
  de embeddings extra e reportar a nova categoria separadamente.
- Rollout gradual atrás de flag, validado pelo harness antes de mudar o
  default — mesmo padrão usado em `add-hybrid-lexical-vector-search`.

## Capabilities

### New Capabilities
- `rag-multi-query-retrieval`: geração de múltiplas variantes de uma
  pergunta (original, expansão por sinônimos, paráfrase técnica) e fusão dos
  resultados de busca vetorial por máxima similaridade de cosseno por chunk,
  para tolerar fraseados imprecisos sem alterar a calibração de recusa/
  seleção de contexto existente.

### Modified Capabilities
(nenhuma — `rag-chat-vector-search`, `rag-self-correction` e
`rag-hybrid-retrieval` continuam com os mesmos requisitos; esta change adiciona
uma nova capability que alimenta o mesmo pipeline sem mudar o contrato delas.)

## Impact

- `backend/app/services/rag_service.py`: novo método
  `_expand_query_multi_variant`, modificação de `_retrieve_docs_via_rpc` para
  fan-out + fusão por máximo, extensão de `trace_out` para observabilidade.
- `backend/app/utils/rag_config.py`: `MULTI_QUERY_EXPANSION_ENABLED`,
  `MULTI_QUERY_VARIANT_COUNT`.
- `backend/evaluation/golden_set.yaml`: novas perguntas `col-*`.
- `backend/evaluation/run_eval.py`: `capture_config`,
  `estimate_embedding_calls`, `summarize()`.
- Custo/latência: N embeddings + N buscas RPC por pergunta na 1ª tentativa
  (em vez de 1), com N = `MULTI_QUERY_VARIANT_COUNT` (default 3) — chamadas
  baratas (embedding + Postgres RPC), não a geração cara (`gpt-4o`); impacto
  real medido pelo harness antes de qualquer mudança de default em produção.
- Depende de `add-rag-self-correction-loop` e `add-hybrid-lexical-vector-search`
  (ambas arquivadas) estarem aplicadas — esta change modifica o mesmo trecho
  de `_retrieve_docs_via_rpc` que ambas já tocaram.
