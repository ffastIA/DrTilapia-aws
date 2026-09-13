## Why

`backend/app/vector_admin_schemas.py:54-63` (`CleanupVectorBaseRequest.validate_fields`) reescreve automaticamente um `confirmation_phrase` vazio/ausente para `"CONFIRMAR_LIMPEZA_TOTAL"` sempre que `dry_run` não for explicitamente `True`:
```python
if not self.confirmation_phrase or self.confirmation_phrase.strip() == "":
    if self.dry_run is True:
        self.confirmation_phrase = "SIMULACAO"
    else:
        self.confirmation_phrase = "CONFIRMAR_LIMPEZA_TOTAL"
```
Isso significa que `POST /admin/vector-base/cleanup` com corpo `{}` (ou qualquer corpo sem esses dois campos) **executa a limpeza real e apaga todos os documentos e objetos de storage da base RAG** — a validação de "frase de confirmação" que existe no repositório (`vector_admin_repository.py:401-403`, `if confirmation_phrase != self.CONFIRMAR_LIMPEZA_TOTAL: raise ValueError`) nunca falha, porque o schema já preencheu a frase certa antes de chegar lá. O mesmo padrão existe em `DeleteFileRequest` (`vector_admin_schemas.py:29-35`) para exclusão de um único arquivo, e em `VectorAdminService.delete_file`/`cleanup` (`vector_admin_service.py:81-95`), que sintetizam a frase de confirmação a partir de um `bool`. O efeito prático: a "confirmação" nunca precisa ser fornecida pelo chamador — ela é sempre auto-preenchida com o valor que autoriza a ação destrutiva.

## What Changes

- `CleanupVectorBaseRequest.validate_fields`: deixa de sintetizar `"CONFIRMAR_LIMPEZA_TOTAL"` quando `confirmation_phrase` vem vazio. Um corpo sem frase de confirmação explícita passa a ser tratado como **dry-run** (comportamento seguro por padrão), não como confirmação de exclusão total.
- `DeleteFileRequest.validate_fields`: mesma correção — não sintetizar `"CONFIRMAR_EXCLUSAO"` a partir de um campo vazio.
- `VectorAdminService.delete_file`/`cleanup`: remover a coerção que transforma um `bool` recebido no parâmetro de confirmação na frase mágica correspondente; a frase precisa vir do chamador (via `confirmation_phrase` explícito), não ser inferida de um tipo.
- **`frontend/hooks/useRagAdmin.ts`**: a exclusão individual de arquivo (`deleteSelectedItem`) hoje chama `deleteRagDocument({ ids: [...], delete_chunks: true })` **sem enviar `confirmation_phrase`** — depende inteiramente do auto-preenchimento que está sendo removido. Precisa passar a enviar `confirmation_phrase: 'CONFIRMADO'` explicitamente, senão a exclusão individual pelo painel admin para de funcionar.
- O fluxo de limpeza total (`clearRagDatabase`) já envia a frase explicitamente hoje e não precisa de mudança.

## Capabilities

### New Capabilities
- `destructive-action-explicit-confirmation`: Garantia de que operações destrutivas administrativas (exclusão de arquivo, limpeza total da base vetorial) só executam a ação real quando o chamador envia explicitamente a frase de confirmação correta — nunca por normalização automática de um campo vazio/ausente ou de um valor booleano.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: `backend/app/vector_admin_schemas.py` (`CleanupVectorBaseRequest`, `DeleteFileRequest`), `backend/app/services/vector_admin_service.py` (`cleanup`, `delete_file`).
- **Frontend**: `frontend/hooks/useRagAdmin.ts` precisa passar a enviar `confirmation_phrase: 'CONFIRMADO'` na exclusão individual (hoje implícito via auto-preenchimento no backend). O fluxo de limpeza total (`ragAdminApi.ts:233-234, 259`) já envia a frase explicitamente e não muda.
- **Comportamento observável**: um `POST /admin/vector-base/cleanup` com corpo `{}` (ou sem `confirmation_phrase`) deixa de apagar dados — passa a se comportar como simulação. Um `POST /admin/vector-base/files/{id}/delete` com corpo `{}` deixa de apagar o arquivo — retorna erro de validação (422) pedindo a frase de confirmação. Exclusão/limpeza reais continuam funcionando pela UI, agora exigindo `confirmation_phrase` explicitamente correto no corpo da requisição.
