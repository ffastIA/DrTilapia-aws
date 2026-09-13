## 1. Middleware — gate de perfil

- [x] 1.1 Em `frontend/middleware.ts`, adicionar `hasCompletedProfile(token)` (mesmo padrão de `isAdminToken`): `GET {SUPABASE_URL}/rest/v1/user_profiles?select=user_id&limit=1` com o token do usuário; retorna `true` se veio 1 linha
- [x] 1.2 Adicionar a nova regra: para `pathname` iniciando com `/main/` e diferente de `/main/profile`, com `token` presente:
  - [x] 1.2.1 Se cookie `profileComplete=1` → deixar passar
  - [x] 1.2.2 Senão, chamar `hasCompletedProfile`; se `true` → setar `profileComplete=1` na resposta e deixar passar
  - [x] 1.2.3 Se `false` e cookie `profileGateSeen` ausente → setar `profileGateSeen=1` e redirecionar para `/main/profile`
  - [x] 1.2.4 Se `false` e cookie `profileGateSeen` presente → limpar `accessToken`, `user`, `profileGateSeen` e redirecionar para `/auth/login`
- [x] 1.3 Garantir que `/main/profile` nunca é redirecionado por esta regra (sempre acessível a quem tem token)
- [x] 1.4 Confirmar que a regra existente de `/main/admin` (checagem de `role=admin`) continua rodando normalmente depois do gate de perfil (as duas regras são independentes e cumulativas)

## 2. Frontend — redirecionamento pós-cadastro

- [x] 2.1 Em `frontend/app/main/profile/page.tsx` (de `add-user-profile`), após `PUT /profile` retornar sucesso na primeira criação do perfil, setar cookie `profileComplete=1` (via `js-cookie`, mesmo padrão de `authStore.ts`) e navegar para `/main/hub` (`router.push`/`router.replace`)
- [x] 2.2 Em edições subsequentes (perfil já completo), manter o usuário na própria página após salvar (sem redirecionar), já que o gate não se aplica mais a ele

## 3. Frontend — nome no lugar do email

- [x] 3.1 Alinhar `frontend/store/authStore.ts`: adicionar `name?: string` à interface `User` local (já existe em `frontend/types/auth.ts`, mas está ausente aqui)
- [x] 3.2 Adicionar action `setUserName(name: string)` em `authStore` que atualiza `user.name` em memória e persiste o cookie `user` atualizado
- [x] 3.3 No hook `useProfile` (de `add-user-profile`), ao carregar um perfil com `full_name` preenchido, chamar `setUserName(profile.full_name)`
- [x] 3.4 Em `frontend/app/main/hub/page.tsx`, trocar `Bem-vindo, {user?.email}!` por `Bem-vindo, {user?.name || user?.email}!` — hub também chama `useProfile()` para que o nome apareça já na primeira visita, não só após editar o perfil

## 4. Verificação

- [x] 4.1 Criar um usuário de teste sem perfil, logar e confirmar redirecionamento silencioso para `/main/profile` ao tentar acessar `/main/hub` — confirmado via curl (307 → `/main/profile`, cookie `profileGateSeen=1`) e no navegador (fluxo real de login)
- [x] 4.2 A partir de `/main/profile`, tentar navegar para outra página de `/main/*` sem salvar e confirmar que o sistema desloga (cookies removidos, redirecionado para `/auth/login`) — confirmado via curl (segunda tentativa com `profileGateSeen=1` → 307 para `/auth/login`, `accessToken`/`user`/`profileGateSeen`/`profileComplete` expirados) e reproduzido no navegador
- [x] 4.3 Logar de novo, completar os campos obrigatórios e salvar; confirmar redirecionamento para `/main/hub` e que a saudação mostra o nome cadastrado — confirmado no navegador ("BEM-VINDO, GATE COMPLETO!")
- [x] 4.4 Confirmar que um usuário com perfil já completo navega livremente por `/main/*` sem nenhum redirecionamento — confirmado (200 direto em `/main/hub`, cookie `profileComplete=1` setado)
- [x] 4.5 Confirmar que um admin sem perfil completo também é bloqueado por este gate antes mesmo de chegar em `/main/admin` — confirmado via curl (admin sem perfil, acesso a `/main/admin` → 307 para `/main/profile`)
