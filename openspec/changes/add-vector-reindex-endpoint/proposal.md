## Why

`POST /admin/vector-base/reindex` era o último item pendente do H3 original (`docs/auditoria-fullstack.md`): o frontend já chama esse endpoint (`ragAdminApi.ts`/`useRagAdmin.ts`), mas ele nunca existiu — nem rota em `main.py`, nem método `reindex_files` em `VectorAdminService`/`VectorAdminRepository`, sob nenhum nome. Havia um script manual órfão (`backend/scripts/manual_clean_reindex.py`) que importava `app.services.clean_reindex_service.CleanReindexService` — módulo que não existe mais no repositório (só sobrou o `.pyc` compilado, o `.py` fonte foi perdido antes desta sessão e não está no histórico do git). Não há como recuperar essa implementação; esta proposta implementa a funcionalidade do zero, reaproveitando o pipeline de ingestão real (`RAGService.ingest_pdf`) em vez de depender do script perdido.

## What Changes

- **`backend/app/services/rag_service.py`**: `ingest_pdf` ganha um parâmetro `force: bool = False`. Quando `True`, pula a checagem de duplicata por hash de conteúdo (`_check_file_exists`) — necessário porque reindexar reprocessa deliberadamente um arquivo cujo conteúdo (e portanto `original_file_id`, que é `SHA-256` dos bytes) não muda. Default `False` preserva o comportamento de todo outro chamador (upload normal).
- **`backend/app/vector_admin_repository.py`**: 2 helpers novos — `download_storage_object(bucket, path)` (baixa os bytes do PDF original do Storage) e `delete_document_rows(chunk_ids)` (apaga linhas de `documents` por UUID, sem mexer em Storage — extraído do `delete_file` existente, que passa a reusá-lo).
- **`backend/app/services/vector_admin_service.py`**: novo método `async def reindex_files(confirmation_phrase, original_file_ids=None)`. Para cada arquivo alvo (lista específica, ou todos se omitido): baixa o PDF do Storage, reingere com `force=True` (novos chunks), só então apaga os chunks antigos (por ID, sem tocar no objeto de Storage, que a reingestão já reaproveita no mesmo caminho determinístico). Se a reingestão falhar, os chunks antigos permanecem intocados — sem janela de perda de dados. Relatório agregado por arquivo (sucesso/falha, chunks criados/removidos).
- **`backend/app/vector_admin_schemas.py`**: `ReindexFilesRequest` (`confirmation_phrase`, `original_file_ids` opcional), `ReindexFileResult`, `ReindexFilesResponse`.
- **`backend/app/main.py`**: `POST /admin/vector-base/reindex`, admin-only, mesmo padrão de tratamento de erro dos outros endpoints de `/admin/vector-base/*` (exceção genérica → 500 com mensagem sanitizada).
- **Frontend**: a UI para acionar isso tinha sido removida em algum momento antes desta sessão (busca em todo `frontend/` não encontrou nenhuma referência a "reindex") — recriada do zero, seguindo o mesmo padrão já usado para "Excluir": `frontend/lib/ragAdminApi.ts` (`reindexRagDocuments`), `frontend/hooks/useRagAdmin.ts` (`reindexItem`, estado `reindexingId`), `frontend/app/main/admin/page.tsx` (botão "Reindexar" por item, ao lado de "Excluir"), `frontend/types/rag-admin.ts` (`RagReindexResponse`).

## Capabilities

### New Capabilities
- `vector-file-reindex`: um administrador pode reprocessar (nova extração + chunking + embeddings) um ou mais arquivos já indexados, a partir do PDF original salvo no Storage, sem precisar re-enviar o arquivo.

## Impact

- **Código afetado**: `rag_service.py` (1 parâmetro novo, retrocompatível), `vector_admin_repository.py` (2 métodos novos + refatoração mínima de `delete_file`), `vector_admin_service.py` (1 método novo), `vector_admin_schemas.py` (3 modelos novos), `main.py` (1 endpoint novo).
- **Pré-requisito para reindexar um arquivo**: ele precisa ter `storage_bucket`/`storage_path` preenchidos (ou seja, o PDF original ainda está no Storage). Arquivos sem isso falham individualmente com uma mensagem clara, sem interromper o processamento dos demais.
- **Custo**: reindexar chama a mesma pipeline de ingestão normal (extração + embeddings via OpenAI) — mesmo custo/tempo de um upload novo, por arquivo.
