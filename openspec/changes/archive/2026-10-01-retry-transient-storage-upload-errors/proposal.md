## Why

"Ao entrar na opção de Análise de Imagem por IA, após subir as imagens e clicar em processar, retorna erro 500."

Reproduzido via `docker compose logs backend`: o erro acontece em `POST /fish/images/upload`, na chamada de Storage:

```
storage3.exceptions.StorageApiError: {'statusCode': 429, 'error': too_many_connections, 'message': Too many connections issued to the database}
  File "backend/app/services/fish_image_service.py", line 126, in upload_image
    self.supabase_admin.storage.from_(self.bucket).upload(...)
```

Confirmado ao vivo (`pg_stat_activity` no projeto Supabase, no momento da investigação): apenas 7 conexões totais, nenhum vazamento do nosso lado. É um erro **transitório do lado do Supabase** — a API de Storage esbarrou momentaneamente no próprio pool interno de conexões com o Postgres do projeto. Evidência: das 5 tentativas de upload nos logs dessa sessão, só 2 falharam (`22:07:46` e `22:08:24`); as 3 tentativas seguintes (`22:08:53`, `22:09:00`, `22:09:11`) tiveram sucesso normal, sem nenhuma mudança de código/ambiente entre elas — o Supabase se recuperou sozinho em segundos.

O backend hoje não tenta de novo: qualquer 429/5xx transitório nessa chamada de Storage já propaga direto como um 500 genérico para o usuário (mensagem sanitizada pela change `error-response-sanitization`, mas ainda assim uma falha visível e evitável), obrigando o usuário a clicar em "Processar" de novo manualmente.

## What Changes

- `backend/app/services/fish_image_service.py`, método `upload_image`: a chamada de upload ao Storage passa a ter um retry com backoff curto (3 tentativas extras, ~0.5s/1.5s/3s) para os status tipicamente transitórios (`429`, `500`, `502`, `503`, `504`) de `storage3.exceptions.StorageApiError`. Status não-transitórios (`403`, `413`, etc.) continuam propagando na primeira tentativa, sem retry.
- Sem nova dependência (loop simples com `time.sleep`, sem `tenacity` ou similar).
- Se todas as tentativas falharem, o comportamento é o mesmo de hoje (500 genérico) — não estamos escondendo uma falha real/persistente, só absorvendo os blips transitórios já observados se autorresolverem em segundos.

## Capabilities

### New Capabilities
- `fish-image-upload-resilience`: o upload de imagens de peixe para o Storage tolera falhas transitórias do lado do Supabase sem expor um erro ao usuário.

## Impact

- **Código afetado**: `backend/app/services/fish_image_service.py` (só o método `upload_image` e um novo helper privado).
- **Fora de escopo** (mesma classe de risco, não tratada agora): chamadas equivalentes a `.storage.from_(...).upload/remove` em `backend/app/services/video_service.py` e `backend/app/vector_admin_repository.py` — candidatas a um follow-up separado se o mesmo tipo de erro transitório for observado ali.
- **Comportamento observável**: um upload que hoje falharia com 500 num blip transitório do Supabase passa a ter até ~5s extras de tentativa antes de ser considerado falho.
