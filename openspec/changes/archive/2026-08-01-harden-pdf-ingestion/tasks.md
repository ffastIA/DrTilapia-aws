## 1. Persistência do PDF original

- [x] 1.1 Bucket dedicado `rag-source-pdfs` criado no Supabase Storage (privado). Confirmado via `storage.buckets`/`storage.objects`: os 4 PDFs de origem estão fisicamente presentes, tamanhos batendo com os arquivos reais.
- [x] 1.2 `ingest_pdf`: upload do arquivo para o Storage via `_upload_source_pdf` (mesmo padrão `storage.from_(bucket).upload(...)` de `fish_image_service.py`/`video_service.py`), rodando em `asyncio.to_thread` antes de gravar os chunks.
- [x] 1.3 `storage_bucket`/`storage_path` populados nas colunas reais via `_backfill_top_level_columns` — confirmado nos 4 documentos existentes na base.
- [x] 1.4 Confirmado por leitura de código: `vector_admin_repository.delete_file` já lê `storage_bucket`/`storage_path` do `file_summary` e chama `storage.from_(...).remove([storage_path])` quando `hard_delete=True` — funciona corretamente agora que essas colunas são populadas de verdade.

## 2. Identidade por conteúdo

- [x] 2.1 `original_file_id = hashlib.sha256(file_bytes).hexdigest()` — hash do conteúdo, lido de `open(file_path, "rb")` antes de qualquer processamento.
- [x] 2.2 **Decisão executada: reingestão completa dos 4 documentos**, não migração in-place. Confirmado via SQL: os 4 `original_file_id` na base são SHA-256 de 64 hex chars (não mais MD5 do nome), com `storage_bucket`/`storage_path` populados — consistente com uma reingestão pelo caminho novo, não um `UPDATE` recalculando o hash a partir do `content` armazenado.
- [x] 2.3 `_check_file_exists` inalterado na lógica (mesmo filtro `metadata->>original_file_id`); funciona com o novo id porque o valor gravado no metadata passou a ser o hash de conteúdo — confirmado pela reingestão bem-sucedida dos 4 documentos sem duplicatas.

## 3. Ingestão resiliente a falha parcial

- [x] 3.1 `_cleanup_failed_ingestion`: se `add_documents`/`_backfill_top_level_columns` falhar, deleta por `metadata->>original_file_id` todas as linhas já inseridas e remove o PDF do Storage antes de propagar o erro.
- [x] 3.2 Confirmado por leitura de código: a limpeza roda em `except Exception: self._cleanup_failed_ingestion(...); raise`, executada ANTES do retorno de erro — como `_check_file_exists` consulta a mesma tabela/coluna que a limpeza esvazia, uma nova tentativa não encontra `already_exists`.

## 4. Não bloquear o event loop

- [x] 4.1 `_load_pdf_with_fallback` (cascata pypdf → pdfplumber → Tesseract → Vision) roda via `await asyncio.to_thread(...)` em vez de síncrono dentro da corrotina.
- [x] 4.2 **Gap encontrado e corrigido durante a implementação**: a extração já estava em thread, mas `self.vectorstore.add_documents(splits)` (chamada de rede síncrona à API de embeddings da OpenAI, um lote por ingestão — dezenas de chunks em documentos maiores) e `_backfill_top_level_columns` rodavam direto na corrotina, sem `asyncio.to_thread` — ou seja, o bloqueio do event loop não estava limitado ao OCR. Extraído para `_persist_chunks` e movido para `asyncio.to_thread`, junto da extração.

## 5. Código órfão

- [x] 5.1 Decidido com o usuário: **remover** (não consertar). `POST /admin/vector-base/reindex` sempre levantava `NotImplementedError` (`VectorAdminService.reindex_files` procurava métodos que não existem em `VectorAdminRepository`); nada usava com sucesso.
- [x] 5.2 Executado: removidos `clean_reindex_service.py`, o endpoint `/admin/vector-base/reindex` e `_normalize_reindex_response` em `main.py`, `ReindexFileRequest`/`ReindexFileResponse` em `vector_admin_schemas.py`, `reindex_files`/`_call_repo_method_async` (órfão após a remoção) em `vector_admin_service.py`, e a exportação de `CleanReindexService` em `services/__init__.py`. `insert_vector_batch` já não existia mais no código (só citado em changes arquivadas). No frontend: removida toda a UI/estado de reindexação (`useRagAdmin.ts`, `ragAdminApi.ts`, `types/rag-admin.ts`, botão "Reindexar Base" em `app/main/admin/page.tsx`). Também removido `frontend/components/admin/` (page.tsx duplicado + ConfirmActionModal/RagUploadPanel/RagDocumentsList) — cluster órfão não importado por nenhuma rota real, que quebraria `tsc --noEmit` ao perder os campos de reindex do hook.

## 6. Verificação

- [x] 6.1 Já provado pelos 4 documentos reingeridos na base real: PDF recuperável do Storage (bucket `rag-source-pdfs`, 4 objetos confirmados), `original_file_id` = SHA-256 do conteúdo, `storage_bucket`/`storage_path` preenchidos em 100% das linhas.
- [x] 6.2 Testado com um PDF sintético descartável e falha injetada logo após `add_documents` (chunks reais já gravados): `ingest_pdf` retornou `status=error`, 0 linhas remanescentes para o `original_file_id` após a limpeza, e uma segunda tentativa (retry) do mesmo arquivo completou com `status=success` — não foi bloqueada como `already_exists`. Base de produção confirmada limpa depois (0 linhas de teste, nenhum objeto extra no bucket `rag-source-pdfs`).
- [x] 6.3 Medido diretamente: enquanto `ingest_pdf` rodava (extração + gravação de embeddings, ambos agora em `asyncio.to_thread` — ver 4.2), um `asyncio.sleep(0.05)` concorrente manteve intervalos de ~50-86ms entre ticks, sem nenhum salto que indicasse o event loop bloqueado. Não forçou OCR real especificamente (Tesseract não está instalado neste ambiente, e evitar custo/latência de Vision), mas o mecanismo (`asyncio.to_thread`) libera o event loop independente do que roda dentro da thread — a mesma garantia vale para o estágio de OCR.
- [x] 6.4 `python test_phase6_post_reindex_success_manual.py` → ✅ APROVADO (5/5 docs, contexto 7460 chars, resposta com 4 fontes reais citadas).
