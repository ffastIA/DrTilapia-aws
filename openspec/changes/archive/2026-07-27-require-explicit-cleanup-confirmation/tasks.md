## 1. Backend — schemas

- [x] 1.1 `CleanupVectorBaseRequest.validate_fields`: `confirmation_phrase` vazio/ausente agora resolve para `dry_run=True`/`"SIMULACAO"` — nunca mais para `"CONFIRMAR_LIMPEZA_TOTAL"`.
- [x] 1.2 `DeleteFileRequest.validate_fields`: `confirmation_phrase` vazio/ausente agora `raise ValueError(...)` (vira 422). Normalização `"CONFIRMADO"` → `"CONFIRMAR_EXCLUSAO"` mantida para o caso preenchido.

## 2. Backend — service

- [x] 2.1 `VectorAdminService.cleanup`: `bool=False` agora `raise ValueError(...)` em vez de sintetizar `"CONFIRMAR_LIMPEZA_TOTAL"`. `bool=True` continua indo para `preview_cleanup()`.
- [x] 2.2 `VectorAdminService.delete_file`: qualquer `bool` agora `raise ValueError(...)` — exige string explícita.

## 3. Frontend

- [x] 3.1 `frontend/hooks/useRagAdmin.ts:84`, `deleteSelectedItem`: payload agora inclui `confirmation_phrase: 'CONFIRMADO'`.

## 4. Verificação

- [x] 4.1 `py_compile` em `vector_admin_schemas.py`/`vector_admin_service.py` — sem erros.
- [x] 4.2 Backend real: `POST /admin/vector-base/cleanup` com corpo `{}` → `{"dry_run":true,...,"message":"Simulação concluída..."}`, `HTTP 200`. `GET /admin/vector-base/files` confirmou os 4 arquivos reais (49 chunks) intactos depois — antes desta correção, o mesmo corpo vazio apagava tudo.
- [x] 4.3 `POST /admin/vector-base/files/{id}/delete` com corpo `{}` → `HTTP 422` (`"confirmation_phrase é obrigatório para excluir um arquivo"`). Arquivos continuaram intactos.
- [x] 4.4 Fluxo real de exclusão individual testado de ponta a ponta com um arquivo descartável (upload de PDF de teste → exclusão com o payload exato que o frontend corrigido envia, `confirmation_phrase: 'CONFIRMADO'`) — `HTTP 200`, arquivo removido corretamente; os 4 arquivos reais não foram tocados.
- [x] 4.5 Fluxo real de limpeza total confirmado: `CleanupVectorBaseRequest(confirmation_phrase='CONFIRMADO')` normaliza para `"CONFIRMAR_LIMPEZA_TOTAL"`; `vector_admin_service.cleanup(...)` roteia corretamente para `cleanup_vector_base` (`dry_run: False`) — verificado com `delete_file` stubado (não-destrutivo) para não repetir a exclusão real contra os 4 arquivos de produção sem nova autorização explícita.
