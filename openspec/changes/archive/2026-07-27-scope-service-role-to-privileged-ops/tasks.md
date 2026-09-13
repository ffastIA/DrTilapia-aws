## 1. Utilitário de cliente escopado ao usuário

- [x] 1.1 `get_user_scoped_client(access_token)` adicionado em `backend/app/database.py`: cliente novo por chamada, chave `anon`, `.postgrest.auth(access_token)`.

## 2. Atualizar `FishImageService`

- [x] 2.1 `self.supabase` renomeado para `self.supabase_admin` (Storage apenas).
- [x] 2.2 `upload_image`: aceita `access_token`; insert via cliente escopado; Storage via `supabase_admin`.
- [x] 2.3 `list_images`: aceita `access_token`; select via cliente escopado; signed URL via `supabase_admin`.
- [x] 2.4 `list_analyses`: mesma mudança (analyses + images associadas via cliente escopado).
- [x] 2.5 `delete_image`: aceita `access_token`; select/delete via cliente escopado; checagem `user_id` mantida; Storage via `supabase_admin`.
- [x] 2.6 `delete_analysis`: mesma mudança.
- [x] 2.7 `download_image_bytes`: mantido em `supabase_admin` (Storage).

## 3. Atualizar as rotas em `backend/app/main.py`

- [x] 3.1 `upload_fish_image`: passa `access_token=current_user["access_token"]`.
- [x] 3.2 `list_fish_images`: passa `access_token=current_user["access_token"]`.
- [x] 3.3 `delete_fish_image`: passa `current_user["access_token"]`.
- [x] 3.4 `list_fish_analyses`: passa `access_token=current_user["access_token"]`.
- [x] 3.5 `delete_fish_analysis`: passa `current_user["access_token"]`.
- [x] 3.6 **Achado adicional**: `_sync_process_fish_analysis`/`process_fish_analysis` (`/fish/analyses/process`) acessavam `fish_image_service.supabase` diretamente (nome que deixou de existir após 2.1) — corrigido para receber `access_token` e usar `get_user_scoped_client(access_token)` em todas as leituras/escritas de `fish_images`/`fish_analyses` (incluindo o bloco de tratamento de erro que marca imagens como `processing_status: error`).

## 4. Verificação

- [x] 4.1 `py_compile` em `database.py`, `fish_image_service.py`, `main.py` — sem erros.
- [x] 4.2 Backend real + dois usuários de teste (Alice, Bob): Alice fez upload de uma imagem; `GET /fish/images` como Alice retornou `total: 1`; como Bob retornou `total: 0` — isolamento confirmado via RLS, não só por filtro de aplicação.
- [x] 4.3 Ponta a ponta confirmado: upload (`POST /fish/images/upload`) e exclusão da própria imagem (`DELETE /fish/images/{id}`) funcionaram normalmente para a dona dos dados (Alice).
- [x] 4.4 Bob tentou `DELETE /fish/images/{id}` na imagem da Alice → **404** (RLS tornou a linha invisível para Bob antes mesmo da checagem Python de propriedade rodar) — imagem da Alice confirmada intacta depois.
- [x] 4.5 Usuários de teste (Alice, Bob) removidos ao final.
