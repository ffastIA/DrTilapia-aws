## 1. Implementar a prévia real de limpeza

- [x] 1.1 `_count_ingestion_logs(original_file_id)` adicionado em `backend/app/vector_admin_repository.py`: conta (via `SELECT ... count='exact'`, sem deletar) linhas em `ingestion_logs`/`rag_ingestion_logs`.
- [x] 1.2 `preview_cleanup()` adicionado: reaproveita `list_files()`, soma `total_chunks`, conta arquivos com storage, soma `_count_ingestion_logs` por arquivo. Retorna `dry_run: True`.
- [x] 1.3 `cleanup_vector_base` (execução real) agora inclui `'dry_run': False` no retorno.
- [x] 1.4 `VectorAdminService.cleanup`: branch `confirmation_phrase=True` agora chama `preview_cleanup()` em vez de retornar zeros fixos.
- [x] 1.5 `CleanupVectorBaseResponse`: campo `dry_run: bool = False` adicionado.
- [x] 1.6 `_normalize_cleanup_response` em `main.py`: `dry_run` propagado em ambos os branches.

## 2. Verificação

- [x] 2.1 `py_compile` em todos os arquivos alterados — sem erros.
- [x] 2.2 Backend rodando (venv reconstruído com as versões atuais de `supabase`/`langchain`/`langgraph` do `requirements.txt` atual, sobrepostas localmente sem tocar no Python global) contra o Supabase real: `POST /admin/vector-base/cleanup` com `dry_run=true` retornou `{"total_files_processed":4,"total_documents_deleted":49,"total_ingestion_logs_deleted":0,"total_storage_deleted":0,"dry_run":true,...}` — contagens reais, não mais zeros fixos.
- [x] 2.3 Confirmado via `GET /admin/vector-base/files`: os 4 arquivos (49 chunks) continuam intactos após o dry-run.
- [x] 2.4 Confirmado **sem tocar em dados reais**: `delete_file` foi substituído por um stub em um script isolado, e `cleanup_vector_base('CONFIRMAR_LIMPEZA_TOTAL')` chamado diretamente — a resposta incluiu `dry_run: False` corretamente. Reconfirmado via API que os 4 arquivos reais permanecem intactos (49 chunks).
