## Why

O backend usa o cliente Supabase `service_role` (`supabase_admin`, `backend/app/database.py:54,57`) para **todas** as operações, inclusive dados pertencentes a um usuário específico (`fish_images`, `fish_analyses`). `service_role` ignora RLS por definição — então, embora existam policies corretas em produção (confirmado ao vivo: `fish_images_select_own`, `fish_images_insert_own`, `fish_images_update_own`, `fish_images_delete_own`, `fish_analyses_select_own/insert_own/update_own/delete_own`, todas `to authenticated using (user_id = auth.uid())`), **elas nunca são de fato aplicadas**, porque o backend nunca as consulta como o usuário autenticado — sempre como `service_role`.

Isso significa que o isolamento entre usuários existe **só** por checagem manual em Python: `backend/app/services/fish_image_service.py:240-241` (`if row["user_id"] != user_id: raise PermissionError`) e trechos equivalentes em `main.py:426-434`. Se um desses `if` for esquecido em um novo endpoint (ou tiver um bug), não há uma segunda camada de defesa — a policy de RLS que existe no banco simplesmente nunca roda. Isso já aconteceu de forma análoga nesta sessão (a mudança `isolate-login-client-and-fix-users-rls` corrigiu exatamente esse padrão para `public.users`).

## What Changes

- `backend/app/services/fish_image_service.py`: os métodos que operam sobre dados de um usuário (`list_images`, `list_analyses`, `upload_image`, `delete_image`, `delete_analysis`, `download_image_bytes`) passam a usar um **cliente Supabase autenticado como o próprio usuário** (token do chamador, via `anon key` + `postgrest.auth(access_token)`), em vez de `supabase_admin`. Isso ativa de fato as policies de RLS já existentes em `fish_images`/`fish_analyses`.
- As checagens de propriedade já existentes em Python (`if row["user_id"] != user_id: raise PermissionError`) **permanecem** — passam a ser defesa em profundidade, não a única barreira.
- `backend/app/main.py`: os endpoints `/fish/*` passam a repassar o `access_token` do usuário atual (já disponível via `Depends(get_current_user)`, que retorna `access_token` desde `dependencies.py:44`) para o serviço.
- `backend/app/services/video_service.py` e o restante do backend (`vector_admin_repository.py`, `rag_service.py`, `dependencies.py`) **continuam usando `service_role`** — fora do escopo desta mudança (ver Non-Goals no design). `videos` é um recurso compartilhado entre todos os usuários autenticados por design (sem RLS por usuário na tabela), diferente de `fish_images`/`fish_analyses`, que já têm policies de posse individual definidas e inertes.

## Capabilities

### New Capabilities
- `fish-data-rls-enforcement`: Garantia de que operações sobre `fish_images`/`fish_analyses` são executadas com um cliente Supabase autenticado como o usuário chamador, ativando as policies de RLS de posse (`*_select_own`, `*_insert_own`, `*_update_own`, `*_delete_own`) como camada real de isolamento entre usuários, em vez de depender só de checagens manuais em Python.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: `backend/app/services/fish_image_service.py`, `backend/app/main.py` (endpoints `/fish/*`).
- **Banco de dados**: nenhuma migration — as policies de RLS relevantes já existem e estão corretas; esta mudança só faz o backend efetivamente respeitá-las.
- **Frontend**: nenhuma mudança de contrato.
- **Comportamento observável**: nenhuma mudança para uso legítimo (cada usuário já só via/mexia nos próprios dados, graças às checagens em Python). Se algum bug futuro pular a checagem manual em um endpoint, a RLS agora barra o acesso de qualquer forma — hoje ela não bloquearia nada.
- **Fora de escopo** (documentado como próximo passo possível, não incluído aqui): aplicar o mesmo padrão a `videos` (recurso compartilhado, sem RLS de posse hoje) e à base RAG (`documents`, já protegida só por `service_role`/admin, sem conceito de "dono" individual).
