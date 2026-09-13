## Why

Testando ao vivo (após reativar o projeto Supabase e criar usuários de teste admin/comum), o login de admin passou a retornar `role: "user"` e, logo em seguida, `/admin/vector-base/files` com o token do admin passou a retornar `401 Usuário não encontrado na tabela 'users'` — mesmo com a linha correta (`role='admin'`) confirmada diretamente no banco. Causa raiz identificada e reproduzida: `backend/app/main.py`'s `/auth/login` chama `supabase_admin.auth.sign_in_with_password(...)` usando o **cliente compartilhado de service_role** (`backend/app/database.py:supabase_admin`), que também é usado por `dependencies.py`, `vector_admin_repository.py` e `rag_service.py` para todas as operações privilegiadas do backend. A biblioteca `supabase-py` registra internamente um listener (`_listen_to_auth_events`) que, a cada evento `SIGNED_IN`/`TOKEN_REFRESHED`/`SIGNED_OUT`, **substitui o header de autorização usado por `.table()`/`.storage()` daquele cliente pelo token do usuário recém-logado** — derrubando permanentemente o privilégio de `service_role` para o nível daquele usuário, para **todas** as chamadas seguintes de **qualquer** requisição, até o próximo evento de auth.

Investigando o banco (via skills `supabase` e `supabase-postgres-best-practices`), confirmei um segundo problema que agrava o primeiro: `public.users` tem RLS habilitado (`relrowsecurity=true`) mas **nenhuma policy** definida — ou seja, deny-by-default para qualquer papel que não seja o verdadeiro `service_role` do Postgres. Assim que o cliente compartilhado perde o privilégio de service_role (pelo bug acima), qualquer leitura de `users` (inclusive a de outro usuário, como o admin) retorna vazia, e código que depende de ler o próprio papel (como a policy existente `videos_delete_admin`/`videos_insert_admin`, que faz `SELECT role FROM users WHERE id = auth.uid()`) também quebra.

Em produção, isso significa que **toda vez que qualquer pessoa faz login, o backend inteiro perde acesso privilegiado ao banco** (upload, RAG, limpeza de base, tudo que depende de bypass de RLS) de forma não determinística, até o próximo evento de autenticação — um bug mais grave que os dois já corrigidos anteriormente (`secure-admin-endpoints-and-fix-cleanup-dryrun`).

## What Changes

- `backend/app/main.py`: o endpoint `/auth/login` passa a autenticar usuários usando `supabase_auth` (cliente já existente em `database.py`, criado com a chave `anon`/padrão, dedicado a operações de auth de usuário final) em vez de `supabase_admin`. `supabase_admin` deixa de receber qualquer evento de login, preservando seu privilégio de service_role para todas as outras requisições concorrentes.
- A busca do `role` do usuário logado (`_load_public_user_profile`) continua usando `supabase_admin`, que a partir desta mudança nunca mais tem seu header de autorização rebaixado por um login de usuário final.
- Adicionar uma policy de RLS em `public.users` permitindo que um usuário autenticado leia **apenas a própria linha** (`auth.uid() = id`), como defesa em profundidade: mesmo que algum código futuro use a chave `anon`/`authenticated` para ler `users` (em vez de `service_role`), a leitura do próprio papel continua funcionando em vez de falhar silenciosamente por ausência total de policy.

## Capabilities

### New Capabilities
- `supabase-client-isolation`: Garantia de que o cliente Supabase usado para autenticar usuários finais (`sign_in_with_password`) é isolado do cliente privilegiado (`service_role`) usado para as demais operações do backend, de modo que um login nunca rebaixe o privilégio efetivo de outras requisições concorrentes.
- `users-table-rls-self-read`: Policy de RLS em `public.users` permitindo que um usuário autenticado leia a própria linha (incluindo o próprio `role`), como defesa em profundidade complementar ao isolamento de clientes.

### Modified Capabilities
(nenhuma — não há specs existentes para este comportamento)

## Impact

- **Código afetado**: `backend/app/main.py` (`/auth/login`), sem mudança de assinatura de request/response.
- **Banco de dados**: nova migration em `public.users` adicionando uma policy `SELECT` para o papel `authenticated` restrita a `auth.uid() = id`. Nenhuma tabela, coluna ou policy existente é removida ou alterada.
- **Frontend**: nenhuma mudança — o contrato de `/auth/login` (payload e resposta) permanece o mesmo.
- **Comportamento observável**: após esta mudança, fazer login como um usuário não deve mais afetar a capacidade de outras requisições concorrentes/subsequentes de ler dados via `service_role`; `/auth/login` deve continuar retornando o `role` correto do usuário autenticado de forma consistente e repetível.
