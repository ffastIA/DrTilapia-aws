## 1. Isolar o cliente usado no login

- [x] 1.1 Em `backend/app/main.py`, no endpoint `/auth/login`, criar um cliente Supabase efêmero (`create_client(SUPABASE_URL, SUPABASE_KEY)`) local à função, e usá-lo apenas para `sign_in_with_password`. Não usar `supabase_admin` nem o singleton `supabase_auth`.
- [x] 1.2 Importar `create_client` e as constantes `SUPABASE_URL`/`SUPABASE_KEY` de `app.database` em `backend/app/main.py` (já eram constantes de módulo em `database.py`, só precisou do import).
- [x] 1.3 Confirmar que a busca de perfil (`_load_public_user_profile`) continua usando `supabase_admin` (não alterado).
- [x] 1.4 Confirmado por busca no repositório: `supabase_auth` só é usado em `backend/app/auth/auth_service.py` (classe `AuthService`, não usada pelo endpoint ativo) e nunca para `.table()`/`.storage()`/`.rpc()`. Nenhum código depende do privilégio do cliente efêmero criado no login.

## 2. Adicionar policy de RLS em public.users

- [x] 2.1 Migration `users_select_own_row` aplicada via `apply_migration` no projeto `tfdripphcwbjiveksuet`: `create policy "users_select_own" on public.users for select to authenticated using (auth.uid() = id);`
- [x] 2.2 `get_advisors(type="security")` rodado após aplicar — nenhum alerta novo relacionado à policy; os warnings existentes (search_path mutável, extensão vector em public, funções SECURITY DEFINER, leaked password protection) são pré-existentes e não relacionados.

## 3. Verificação

- [x] 3.1 Backend reiniciado via `backend/.venv` com o código corrigido, conectado ao projeto Supabase real (`tfdripphcwbjiveksuet`, reativado nesta sessão).
- [x] 3.2 Login usuário comum → depois login admin: resposta do admin retornou `role: "admin"` corretamente (bug original reproduzido e confirmado corrigido).
- [x] 3.3 Ordem inversa (login admin → login usuário comum) e então `/admin/vector-base/files` com token do admin: **200 OK**, listou os 4 arquivos reais da base (antes retornava 401 "Usuário não encontrado").
- [x] 3.4 Token do usuário comum em `/admin/vector-base/files`: **403** "Acesso negado: apenas administradores...". Validado.
- [x] 3.5 Token do usuário comum em `/consultoria/chat`: passou pela autenticação (não 401/403) e chegou ao pipeline RAG — validando a camada de autorização. Encontrado bug **pré-existente e não relacionado**: a chamada retornou 500 porque `rag_service.py` invoca a função RPC `match_documents`, que não existe no banco (existe `rpc_vector_search`, com nome/assinatura diferentes). Registrado como achado novo, fora do escopo desta mudança.
- [x] 3.6 Usuários de teste temporários removidos: `auth.admin.delete_user()` para os dois (com cascade automático removendo as linhas de `public.users`). Confirmado via `execute_sql` que não sobraram linhas de teste.
