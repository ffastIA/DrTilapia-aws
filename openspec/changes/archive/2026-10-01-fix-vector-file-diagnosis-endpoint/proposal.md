## Why

Ao avaliar as 4 falhas restantes da suíte `pytest` (H3 da auditoria original), reexaminei o código com mais cuidado e descobri que **3 das 4 não são o que a auditoria original supôs**:

`VectorAdminService` (`backend/app/services/vector_admin_service.py`) é uma fachada sobre `VectorAdminRepository` — cada método público tenta uma lista de nomes alternativos no repositório via `_call_repo_method`, para tolerar nomes diferentes entre as duas camadas:

- `get_files()` procura `['get_files', 'list_files', ...]` → o repositório tem `list_files` → **funciona hoje**. O teste só monkeypatcha o nome errado (`vector_admin_service.list_files`, que não existe na fachada).
- `get_file_content()` procura `['get_file_content', 'recover_file_content', ...]` → o repositório tem `recover_file_content` → **funciona hoje**. Mesmo problema: teste monkeypatcha o nome errado.
- `get_file_diagnosis()` procura `['get_file_diagnosis', 'diagnose_file', 'get_diagnosis']` → **NÃO inclui `'diagnose_file_recovery'`**, que é o nome real implementado em `vector_admin_repository.py:269`. Resultado: `NotImplementedError` toda vez que `GET /admin/vector-base/files/{id}/diagnosis` é chamado → 500. **Este é um bug real de produção**, não um problema de teste — confirma o achado H3 original ("`GET /admin/vector-base/files/{id}/diagnosis` → sempre 500").
- `reindex_files`: não existe rota, método de serviço nem de repositório sob nenhum nome — feature genuinamente não implementada, fora do escopo desta mudança (é trabalho de feature nova, não uma correção pontual).

## What Changes

- `backend/app/services/vector_admin_service.py`, método `get_file_diagnosis`: adicionar `'diagnose_file_recovery'` à lista de nomes tentados no repositório, para que o endpoint pare de falhar com `NotImplementedError`/500.
- `backend/tests/test_backend_api.py`: corrigir 2 mocks que testavam nomes que nunca existiram na fachada do serviço (sem nenhuma mudança de comportamento de produção nesses dois pontos, já funcionavam):
  - `test_list_vector_files_success`: monkeypatch de `list_files` → `get_files`.
  - `test_recover_vector_file_content_success`: monkeypatch de `recover_file_content` → `get_file_content`.
  - `test_diagnose_vector_file_recovery_success`: monkeypatch de `diagnose_file_recovery` → `get_file_diagnosis` (agora que o bug real foi corrigido, este teste passa a validar o caminho real, não mais um método inexistente).

## Capabilities

### New Capabilities
- `vector-file-diagnosis-recovery`: o endpoint de diagnóstico de arquivo do painel admin (`GET /admin/vector-base/files/{id}/diagnosis`) retorna um diagnóstico real em vez de falhar sempre com 500.

## Impact

- **Código afetado**: `backend/app/services/vector_admin_service.py` (1 linha — lista de aliases). `backend/tests/test_backend_api.py` (3 correções de mock, sem lógica de produção nova).
- **Fora de escopo**: `reindex_files`/`POST /admin/vector-base/reindex` — feature ausente, não uma correção de nome; seguiria como um item separado do H3 original se o produto quiser priorizá-lo.
- **Comportamento observável**: `GET /admin/vector-base/files/{id}/diagnosis` passa a retornar `200` com o diagnóstico real em vez de `500`.
