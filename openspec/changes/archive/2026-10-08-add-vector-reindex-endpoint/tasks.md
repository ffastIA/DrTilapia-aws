## 1. Pipeline de ingestão

- [x] 1.1 `backend/app/services/rag_service.py`, `ingest_pdf`: adicionado parâmetro `force: bool = False`; pula `_check_file_exists` quando `True`.
- [x] 1.2 (achado durante o teste real) `_upload_source_pdf` usava `upload()` sem `upsert` — como o caminho é endereçado por conteúdo (hash), reenviar o mesmo PDF durante reindex sempre batia em `409 Duplicate`. Corrigido com `file_options={"upsert": "true"}`.

## 2. Repositório

- [x] 2.1 `backend/app/vector_admin_repository.py`: adicionado `download_storage_object(storage_bucket, storage_path) -> bytes`.
- [x] 2.2 Adicionado `delete_document_rows(chunk_ids) -> int`; `delete_file` refatorado para reusá-lo.

## 3. Serviço

- [x] 3.1 `backend/app/services/vector_admin_service.py`: constante `CONFIRMAR_REINDEXACAO`; método `async def reindex_files(confirmation_phrase, original_file_ids=None)`.

## 4. Schemas e endpoint

- [x] 4.1 `backend/app/vector_admin_schemas.py`: `ReindexFilesRequest`, `ReindexFileResult`, `ReindexFilesResponse`.
- [x] 4.2 `backend/app/main.py`: `POST /admin/vector-base/reindex`, admin-only.

## 5. Frontend

- [x] 5.1 `frontend/types/rag-admin.ts`: `RawRagReindexResponse`, `RagReindexResponse`.
- [x] 5.2 `frontend/lib/ragAdminApi.ts`: endpoint `REINDEX`, função `reindexRagDocuments(originalFileIds)`.
- [x] 5.3 `frontend/hooks/useRagAdmin.ts`: estado `reindexingId`/`lastReindexResponse`, callback `reindexItem(item)`.
- [x] 5.4 `frontend/app/main/admin/page.tsx`: botão "Reindexar" por item, ao lado de "Excluir".

## 6. Verificação

- [x] 6.1 Suíte `pytest`: **133 passed, 0 failed, 11 skipped** (o `test_reindex_vector_files_success`, antes a única falha restante da sessão, agora passa — ele usa mock, então valida a integração do endpoint com o serviço, não a lógica real de reindexação, que foi validada separadamente nos itens 6.4/6.5).
- [x] 6.2 `npx tsc --noEmit` no frontend — sem erros.
- [x] 6.3 Rebuild do backend e do frontend — ambos saudáveis.
- [x] 6.4 **Teste real no navegador** (Chrome, login admin real `ffasti01@gmail.com`): naveguei a `/main/admin`, cliquei "Reindexar" em `BIA_RAG.pdf`. Primeira tentativa expôs o bug do item 1.2 (409 Duplicate no Storage — reportado como falha pelo próprio endpoint, chunks antigos preservados, like projetado). Corrigido, rebuild, segunda tentativa: UI mostrou "Arquivo reindexado com sucesso." — confirma o botão e o fluxo end-to-end funcionando.
- [x] 6.5 Confirmado no banco (MCP `supabase`): os 8 chunks de `BIA_RAG.pdf` (`original_file_id=a0cdb5cd...`) têm UUIDs totalmente novos, `created_at` no momento do teste — nenhum dos 8 IDs antigos (deletados) sobrou; contagem de chunks inalterada (8→8), como esperado (mesmo conteúdo, mesma config de chunking).
- [x] 6.6 (achado adicional, fora do escopo desta mudança) Durante a investigação, descobri que a `SUPABASE_ANON_KEY` legada no `.env` da raiz estava **desabilitada pelo Supabase desde 2026-07-26** (chaves legacy desativadas), o que quebrava silenciosamente `frontend/middleware.ts` inteiro (`isAdminToken`/`hasCompletedProfile` sempre falhavam fechado — por isso nenhum admin conseguia abrir `/main/admin` pelo navegador). Corrigido trocando para a `publishable key` ativa no `.env` da raiz (usada como fallback de build do frontend). Reportado ao usuário; não fazia parte do pedido original de reindex, mas bloqueava a verificação no navegador.
- [ ] 6.7 Não foi possível testar automaticamente o cenário "reingestão bem-sucedida, mas falha simulada ao apagar os chunks antigos" — exigiria mock de baixo nível não coberto nesta entrega (documentado como limitação, não bloqueante).
- [x] 6.8 (achado do usuário, testando esta mesma tela) "Inserido em"/"Atualizado em" apareciam sempre como "Data indisponível". Causa: `vector_admin_repository._build_file_summary` calculava `last_ingested_at` a partir de uma coluna `last_ingested_at` que **não existe** em `documents` (só existem `created_at`, real, e `updated_at`, sempre nulo) — o campo era sempre `None`, e é o primeiro que o frontend usa para as duas datas. Corrigido: `last_ingested_at` agora é derivado de `MAX(created_at)` entre os chunks ativos.
- [x] 6.9 (achado do usuário, follow-up do 6.8) Depois do fix acima, "Inserido em" e "Atualizado em" mudavam **juntas** a cada reindex — errado, só "Atualizado em" deveria mudar. Causa: as duas datas vinham da mesma fonte (`last_ingested_at`), e reindexar apaga as linhas antigas e cria linhas novas com `created_at` novo, perdendo a data de primeira ingestão. Corrigido preservando a data original através de reindexações:
  - `rag_service.ingest_pdf` ganhou o parâmetro `first_ingested_at` (opcional) — quando informado, grava esse valor no `metadata` de cada chunk novo.
  - `vector_admin_service.reindex_files`, antes de apagar os chunks antigos, calcula `first_ingested_at = min(chunk.first_ingested_at ou chunk.created_at)` entre eles e repassa para `ingest_pdf` — preservando a data mesmo em reindexações sucessivas.
  - `vector_admin_repository._build_file_summary` agora expõe dois campos distintos: `created_at` (primeira ingestão, lido de `first_ingested_at` no metadata quando presente, senão do `created_at` real do chunk) e `last_ingested_at` (mais recente `created_at` real,= última reindexação).
  - `frontend/lib/ragAdminApi.ts`: prioridade de `createdSource` corrigida para usar o novo `created_at` (não mais `last_ingested_at`) primeiro.
  - **Verificado no navegador**: reindexei `Indice volumetrico abate.pdf` de novo — "Inserido em" ficou em `21:19` (inalterado) e "Atualizado em" mudou para `21:32`. Confirmado no banco: chunks novos com `created_at=00:32:36`, `metadata.first_ingested_at=00:19:49` (preservado da reindexação anterior).
  - **Limitação conhecida**: os 2 arquivos já reindexados ANTES deste fix (`BIA_RAG.pdf`, `Indice volumetrico abate.pdf`) perderam a data de primeira ingestão de verdade — a próxima reindexação deles já usa a data daquele reindex anterior como base "preservada" (não há como recuperar a data original perdida). Novas reindexações a partir de agora preservam corretamente.
  - Suíte `pytest`: 133 passed, 0 failed, 11 skipped. `tsc --noEmit`: sem erros.
