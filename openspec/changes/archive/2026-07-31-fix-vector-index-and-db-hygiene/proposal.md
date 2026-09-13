## Why

A tabela `documents` tem **duas colunas de embedding** (`vector` e `embedding`) e o índice HNSW foi criado sobre a errada. A coluna `vector` está 100% vazia (0 de 49 linhas); os embeddings reais vivem em `embedding`, que **não tem índice nenhum**. Confirmado ao vivo no banco: `idx_scan = 0` para o índice, `seq_scan = 61` na tabela, e o `EXPLAIN` da busca mostra `Seq Scan`.

Com 49 chunks isso é invisível. A partir de alguns milhares de chunks, toda consulta vira varredura completa da tabela e a busca degrada linearmente — é uma bomba-relógio que já está armada e passa despercebida justamente porque a base ainda é pequena.

Na mesma inspeção apareceram outros problemas de higiene do banco que compartilham o mesmo contexto e o mesmo teste de verificação: funções RPC sem `search_path` fixo (alerta de segurança), políticas RLS duplicadas reavaliadas por linha (alerta de performance), e código da aplicação que consulta uma tabela `ingestion_logs` **que não existe**.

## What Changes

- Índice vetorial passa a existir sobre a coluna que é de fato consultada, tornando a busca por similaridade indexada em vez de sequencial.
- A coluna de embedding duplicada e vazia é eliminada, junto com a escrita redundante que a alimentava — deixa de haver ambiguidade sobre qual coluna é a verdadeira.
- Funções RPC de busca e inserção passam a ter `search_path` fixo.
- Políticas RLS duplicadas de `documents` são consolidadas, e a chamada de papel passa a ser avaliada uma vez por consulta em vez de uma vez por linha.
- Código morto que consulta a tabela inexistente `ingestion_logs` é removido, junto com os campos que ele reportava e que sempre valiam zero.
- **BREAKING** (interno): `insert_vector_batch` deixa de gravar na coluna `vector`. Nenhum código da aplicação chama essa função hoje (as 49 linhas atuais não vieram dela), então o impacto prático é nulo — mas quem dependesse dela veria a mudança.

Não altera embeddings, chunking, recuperação ou prompts — isso é escopo de outras mudanças. Não exige reingestão.

## Capabilities

### New Capabilities
- `vector-store-indexing`: garantias sobre a indexação da busca vetorial e a higiene do esquema que a sustenta.

### Modified Capabilities
Nenhuma. `rag-chat-vector-search` continua descrevendo o mesmo comportamento observável de busca — o que muda é o plano de execução, não o resultado.

## Impact

- Banco `tfdripphcwbjiveksuet`, tabela `public.documents`: índice, coluna `vector`, políticas RLS.
- Funções `public.rpc_vector_search` e `public.insert_vector_batch`.
- `backend/app/vector_admin_repository.py`: remoção do código que consulta `ingestion_logs` (`_count_ingestion_logs`, `_best_effort_delete_ingestion_logs`) e dos campos correspondentes.
- Schemas de resposta que expõem `ingestion_logs_deleted` / `total_ingestion_logs_deleted` (`backend/app/vector_admin_schemas.py`) — campos que hoje são sempre `0` por falha silenciosa.
- Frontend de administração do RAG, se exibir esses contadores.
- Risco de indisponibilidade momentânea da busca durante a recriação do índice (mitigável com `CREATE INDEX CONCURRENTLY`).
