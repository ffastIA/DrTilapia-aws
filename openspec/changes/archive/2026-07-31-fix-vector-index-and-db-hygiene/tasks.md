## 1. Snapshot antes de mexer

- [x] 1.1 Registrar o estado atual para comparação posterior: `pg_indexes` de `documents`, `idx_scan`/`seq_scan` de `pg_stat_user_indexes`/`pg_stat_user_tables`, e o `EXPLAIN` da consulta de similaridade.
- [x] 1.2 Guardar o resultado de uma busca de referência (mesmo vetor de query, mesmo `limit_count`): ids, similaridades e ordem. Servirá para provar que o comportamento não mudou.
- [x] 1.3 **Reconfirmado**: `count(vector) = 0` de 49 linhas, imediatamente antes das mudanças. Autoriza a remoção da coluna — não confiar na medição da revisão; é a checagem que autoriza a remoção da coluna.

## 2. Índice sobre a coluna correta

- [x] 2.1 `CREATE INDEX CONCURRENTLY documents_embedding_hnsw_idx ON public.documents USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)`.
- [x] 2.2 Confirmar que o índice ficou `valid` (índice criado com `CONCURRENTLY` pode falhar e ficar inválido silenciosamente — checar `pg_index.indisvalid`).
- [x] 2.3 `DROP INDEX documents_vector_hnsw_idx`.

## 3. Eliminar a coluna de embedding duplicada

- [x] 3.1 Ajustar `insert_vector_batch` para inserir apenas em `embedding` (hoje faz `VALUES (..., v, v)` gravando nas duas).
- [x] 3.2 `ALTER TABLE public.documents DROP COLUMN vector` — só após 1.3 confirmar 0 linhas preenchidas.
- [x] 3.3 Confirmar que `SupabaseVectorStore` (LangChain) continua inserindo normalmente: fazer um insert de teste e removê-lo em seguida.

## 4. `search_path` nas funções

- [x] 4.1 `rpc_vector_search` recriada com `SET search_path = public`. **Achado**: a assinatura real tinha `limit_count integer DEFAULT 5` (o default não constava na task); preservado, pois omiti-lo mudaria o contrato silenciosamente para chamadores que não passam o parâmetro.
- [x] 4.2 Recriar `insert_vector_batch` com `SET search_path = public`.
- [x] 4.3 Confirmar que a assinatura e o tipo de retorno de `rpc_vector_search` não mudaram — `rag_service` chama por nome e parâmetros nomeados.

## 5. Políticas RLS

- [x] 5.1 Duplicatas identificadas: SELECT (`Enable read for service_role` + `service_role can read documents`) e INSERT (`Enable insert for service_role` + `service_role can insert documents`). DELETE e UPDATE tinham apenas uma cada.
- [x] 5.2 Remover as duplicatas, mantendo uma política por comando.
- [x] 5.3 Trocar `auth.role() = 'service_role'` por `(select auth.role()) = 'service_role'` nas políticas restantes.
- [x] 5.4 **Testar imediatamente** o acesso do backend (`supabase_admin.table('documents').select('id').limit(1)`) — se a consolidação quebrar o acesso, reverter na hora.

## 6. Remover o código da tabela inexistente

- [x] 6.1 Remover `_count_ingestion_logs` e `_best_effort_delete_ingestion_logs` de `backend/app/vector_admin_repository.py` e suas chamadas.
- [x] 6.2 Remover `ingestion_logs_deleted` de `DeleteFileResponse` e `total_ingestion_logs_deleted` de `CleanupVectorBaseResponse` (`backend/app/vector_admin_schemas.py`).
- [x] 6.3 Frontend verificado: **nenhuma referência** a `ingestion_logs`/`ingestionLogs` em `.ts`/`.tsx` — nada a remover na UI.
- [x] 6.4 Confirmar por busca que não resta nenhuma referência a `ingestion_logs` no backend.

## 7. Verificação

- [x] 7.1 Repetir a busca de referência de 1.2 e confirmar **ids, similaridades e ordem idênticos** — o requisito é que o comportamento não mude.
- [x] 7.2 Como antecipado, o planejador **continua preferindo `Seq Scan`** com 49 linhas — comportamento legítimo, não falha. Com `SET LOCAL enable_seqscan = off` o plano passa a `Index Scan using documents_embedding_hnsw_idx`, provando que o índice agora é utilizável (antes era impossível: estava sobre uma coluna vazia).
- [x] 7.3 `get_advisors` de segurança: `function_search_path_mutable` **eliminado** para as duas RPCs. Alertas restantes (`extension_in_public`, `rls_auto_enable` SECURITY DEFINER, proteção de senha vazada) são pré-existentes e fora do escopo desta mudança.
- [x] 7.4 `get_advisors` de performance: `multiple_permissive_policies` e `auth_rls_initplan` **eliminados** para `documents` (os que restam são de `videos`/`fish_*`/`users`, fora do escopo). **Ressalva honesta**: surgiu um `unused_index` novo, agora sobre `documents_embedding_hnsw_idx` — pelo mesmo motivo da task 7.2 (com 49 linhas o planejador não usa o índice). Deixa de ser alerta quando a base crescer; o índice está correto e comprovadamente utilizável.
- [x] 7.5 Exercitar o chat de ponta a ponta (`POST /consultoria/chat`) e confirmar que continua respondendo normalmente.
- [x] 7.6 `preview_cleanup` retorna 4 arquivos/49 docs sem o campo removido e **sem warnings** de tabela ausente. `delete_file` exercitado de verdade com um documento descartável inserido para o teste (`documents_deleted: 1`, mensagem sem menção a logs); base de 49 chunks confirmada intacta depois. Exclusão dos documentos reais **não** foi executada — seria destrutiva e a base é necessária para as mudanças seguintes.
- [x] 7.7 Se o harness de avaliação (`add-rag-evaluation-harness`) já existir, rodá-lo e confirmar métricas **inalteradas** — esta mudança não deve mexer em qualidade.
