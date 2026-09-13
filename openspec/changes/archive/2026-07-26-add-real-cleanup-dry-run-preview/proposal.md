## Why

O código atual de `/admin/vector-base/cleanup` (evoluído de forma independente em outro ambiente de desenvolvimento, já sincronizado neste repositório) tem um modo de simulação, mas ele é **decorativo**: `VectorAdminService.cleanup(confirmation_phrase: Union[str, bool])`, quando recebe `True` (disparado por `dry_run=true`/`confirmation_phrase="SIMULACAO"` em `main.py`), retorna um dicionário **fixo**, sempre `{'total_files_processed': 0, 'total_documents_deleted': 0, ...}`, com a mensagem `'Cleanup simulation executed.'` — independentemente do que realmente existe na base. Um admin que clique em "simular limpeza" hoje sempre vê "0 arquivos, 0 documentos", mesmo que existam dezenas de arquivos reais, tornando a simulação inútil para decidir se é seguro prosseguir com a limpeza real.

Isso já foi identificado como requisito em uma spec anterior (`vector-base-cleanup-dryrun`, de uma auditoria de segurança anterior deste mesmo projeto, feita antes de uma sincronização com 24 commits de outro ambiente de desenvolvimento que reescreveu esses arquivos). O requisito ainda é válido — só que a implementação atual não o cumpre mais, porque o código foi reescrito por outra via.

## What Changes

- `VectorAdminRepository`: novo método `preview_cleanup()`, não-destrutivo, que reaproveita `list_files()` para calcular contagens reais de quantos arquivos/documentos/objetos de storage seriam removidos, e faz uma contagem (via `SELECT ... count`, sem deletar) de quantos registros de `ingestion_logs`/`rag_ingestion_logs` seriam removidos.
- `VectorAdminService.cleanup(...)`: quando chamado em modo simulação (`confirmation_phrase=True`), passa a chamar `preview_cleanup()` em vez de retornar um dicionário fixo com zeros.
- `VectorAdminRepository.cleanup_vector_base` (execução real): passa a incluir explicitamente `dry_run: False` no retorno, para simetria com o novo `preview_cleanup()` (`dry_run: True`).
- `CleanupVectorBaseResponse` (schema): novo campo `dry_run: bool = False`, propagado por `_normalize_cleanup_response` em `main.py`.
- Nenhuma mudança de rota, payload de request, ou lógica de autenticação/autorização.

## Capabilities

### New Capabilities
(nenhuma)

### Modified Capabilities
- `vector-base-cleanup-dryrun`: o requisito "Cleanup dry-run must not delete any data" já existia; esta mudança faz a implementação atual do repositório voltar a cumpri-lo (hoje ela retorna zeros fixos em vez de contagens reais). Os cenários são atualizados para refletir a frase de confirmação real usada pelo código atual (`CONFIRMAR_LIMPEZA_TOTAL`, não mais `CONFIRMADO`).

## Impact

- **Código afetado**: `backend/app/vector_admin_repository.py` (novo método `preview_cleanup`), `backend/app/services/vector_admin_service.py` (`cleanup`), `backend/app/vector_admin_schemas.py` (`CleanupVectorBaseResponse`), `backend/app/main.py` (`_normalize_cleanup_response`).
- **Banco de dados**: nenhuma migration — `preview_cleanup` só faz leituras (`SELECT`), nunca `DELETE`.
- **Frontend**: nenhuma mudança de contrato; o campo novo `dry_run` na resposta é aditivo (default `False`), não quebra clientes existentes.
- **Comportamento observável**: chamar `/admin/vector-base/cleanup` com `dry_run=true` passa a retornar as contagens reais do que seria removido, sem apagar nada; a resposta explicita `dry_run: true`/`false` conforme o modo executado.
