## 1. Corrigir a fachada do serviço

- [x] 1.1 Em `backend/app/services/vector_admin_service.py`, método `get_file_diagnosis`: adicionado `'diagnose_file_recovery'` à lista de nomes tentados no repositório (`['get_file_diagnosis', 'diagnose_file_recovery', 'diagnose_file', 'get_diagnosis']`).

## 2. Corrigir os mocks de teste

- [x] 2.1 `test_list_vector_files_success`: monkeypatch de `list_files` → `get_files`.
- [x] 2.2 `test_recover_vector_file_content_success`: monkeypatch de `recover_file_content` → `get_file_content`.
- [x] 2.3 `test_diagnose_vector_file_recovery_success`: monkeypatch de `diagnose_file_recovery` → `get_file_diagnosis`.

## 3. Verificação

- [x] 3.1 Suíte `pytest`: **132 passed, 1 failed, 11 skipped** — a única falha restante é `test_reindex_vector_files_success` (fora de escopo, feature não implementada). As 3 falhas deste change (`list_files`/`recover_file_content`/`diagnose_file_recovery`) foram embora.
- [x] 3.2 Rebuild do container backend (`docker compose up -d --build backend`) — concluído, container saudável (`GET /health` 200).
- [x] 3.3 Verificação de resolução do alias (em vez de chamada HTTP completa, que exigiria um admin/arquivo reais): script ad-hoc confirmou que `vector_admin_service.repository` tem `diagnose_file_recovery` (não tem `get_file_diagnosis`/`diagnose_file`/`get_diagnosis`) e que a ordem de busca do `_call_repo_method` resolve corretamente para `diagnose_file_recovery` — a mesma checagem que antes retornava `False` para todos os 4 nomes (causando `NotImplementedError`) agora encontra o nome real na 2ª posição da lista.
