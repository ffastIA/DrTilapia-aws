## Why

As perguntas que continuam falhando depois das duas changes anteriores deste programa (`restore-rag-answer-quality`, `add-rag-self-correction-loop`) são majoritariamente busca por **termo exato**: `RPL`, `PRO+MOS 64.10`, `FIS`, `LD50 1.26 x 10⁸`, `MOS 21.02`, valores em reais. Embedding semântico dilui um token raro (uma sigla, um valor numérico específico) num vetor de tópico geral — ele é bom para "do que trata este trecho", não para "este trecho contém exatamente este termo". Busca textual (full-text do Postgres) resolve exatamente esse caso, e o corpus é pequeno o suficiente (124 chunks) para que o custo de manter um segundo índice seja desprezível.

Este é o último item do programa de recuperação de qualidade porque depende de medição confiável (`fix-rag-eval-harness-fidelity`) e de uma pipeline já corrigida (`restore-rag-answer-quality`, `add-rag-self-correction-loop`) para isolar o que ainda é, de fato, um problema de recuperação — não de formato de resposta ou de seleção de contexto.

Um benefício colateral importante: a similaridade de cosseno, sozinha, não separa perguntas dentro/fora do escopo neste corpus (uma pergunta claramente fora do escopo pode pontuar mais alto que uma legítima). Um sinal léxico independente — quantos termos discriminativos da pergunta aparecem literalmente no corpus — é ortogonal a esse problema e permite um gate de recusa mais confiável do que a similaridade sozinha.

## What Changes

- Nova coluna gerada `content_tsv` (tsvector) em `public.documents`, computada a partir da coluna `content` já existente, com índice GIN — mudança de schema puramente aditiva, sem reingestão nem re-embedding.
- Nova função RPC `rpc_lexical_search`, paralela à `rpc_vector_search` existente (que permanece intocada), fazendo busca textual com ranking por relevância.
- Busca de recuperação passa a combinar os dois sinais (vetorial + léxico) via Reciprocal Rank Fusion (RRF), atrás de uma flag de configuração (`HYBRID_SEARCH_ENABLED`), permitindo desligar sem reverter código.
- O gate de recusa por similaridade de cosseno é reforçado com contagem de termos discriminativos que casam lexicalmente — uma pergunta com termos totalmente ausentes do corpus é um segundo sinal de recusa independente da similaridade vetorial.
- Reranking manual por bônus de substring (`_score_doc_bonus`/`_rerank_docs`) é removido — a fusão RRF é a versão correta e limitada do que esse bônus tentava aproximar.
- Os "data companions" (limitados na change `restore-rag-answer-quality`) são aposentados, condicionados a medição confirmando que a busca híbrida alcança paridade nas perguntas que hoje dependem deles.

## Capabilities

### New Capabilities
- `rag-hybrid-retrieval`: recuperação combinando busca vetorial semântica e busca textual léxica via fusão de ranks, com um segundo sinal de recusa baseado em cobertura léxica de termos discriminativos.

## Impact

- Migração de banco: `ALTER TABLE public.documents ADD COLUMN content_tsv ...` + `CREATE INDEX CONCURRENTLY` (aditivo, sem lock longo, sem reingestão — a tabela tem 124 linhas).
- Nova função `rpc_lexical_search` no Postgres, com `SET search_path` explícito e `REVOKE`/`GRANT` restritivos (mesmo padrão de segurança já adotado nas funções RPC existentes).
- `backend/app/services/rag_service.py`: `_retrieve_docs_via_rpc` (fusão), novo `_build_lexical_query`, novo `_rrf_fuse`, remoção de `_score_doc_bonus`/`_rerank_docs`, ajuste do gate de recusa para considerar o sinal léxico, remoção condicional de `_add_data_companion_chunks`.
- `backend/app/utils/rag_config.py`: `HYBRID_SEARCH_ENABLED`, `RRF_K`, constante de limiar de cobertura léxica discriminativa.
- Depende de `fix-rag-eval-harness-fidelity` (medição) e `restore-rag-answer-quality`/`add-rag-self-correction-loop` (pipeline já corrigida) estarem aplicados antes.
