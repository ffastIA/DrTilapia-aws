## Why

Hoje o DrTilápIA só permite login (`POST /auth/login`); toda conta é criada manualmente por um admin via script. Não existe cadastro público, nem confirmação de email, nem forma de recuperar uma senha esquecida — qualquer usuário que esqueça a senha fica bloqueado sem alternativa além de pedir a um admin para recriar a conta.

## What Changes

- Novo endpoint `POST /auth/signup`: cadastro público (email/senha), cria o usuário no Supabase Auth e a linha correspondente em `public.users` (`role="user"`), e dispara o email de confirmação do Supabase.
- Novo endpoint `POST /auth/resend-confirmation`: reenvia o email de confirmação de cadastro.
- Novo endpoint `POST /auth/forgot-password`: dispara o email de redefinição de senha do Supabase.
- Novo endpoint `POST /auth/reset-password`: recebe os tokens do link de redefinição + nova senha, e efetiva a troca.
- `POST /auth/login` passa a distinguir "credenciais inválidas" de "email ainda não confirmado" (hoje ambos retornam o mesmo 401 genérico) — **BREAKING** para qualquer consumidor que dependa do formato de erro atual do login (nenhum existe hoje além do próprio frontend, que será atualizado junto).
- Novas páginas no frontend: `/auth/signup`, `/auth/forgot-password`, `/auth/callback` (landing única para os dois links de email — confirmação de cadastro e redefinição de senha, ramificando pelo parâmetro `type`).
- `frontend/middleware.ts`: regra de redirecionamento para usuário já logado passa a ser uma lista de permissão (só `/auth/login`), em vez de cobrir todo `/auth/*`, para não expulsar um usuário de `/auth/callback` ou `/auth/forgot-password`.
- Correção de uma lacuna de segurança pré-existente (não introduzida por esta mudança, mas tocada pelo mesmo arquivo): `backend/app/auth/auth_service.py` hoje reutiliza um cliente Supabase compartilhado (`supabase_auth`) para `sign_in_with_password`, quando a spec `supabase-client-isolation` já exige um cliente efêmero por requisição (correção que existia numa versão anterior do código e não sobreviveu a uma reconciliação de git posterior). Esta mudança aplica o padrão de cliente efêmero também a `login()`, e a todas as novas chamadas de auth (`signup`, `resend`, `reset`).

## Capabilities

### New Capabilities
- `user-signup`: cadastro público de usuários com confirmação de email obrigatória antes do primeiro login, incluindo reenvio de confirmação.
- `password-reset`: fluxo de redefinição de senha via link enviado por email.

### Modified Capabilities
- `supabase-client-isolation`: `POST /auth/login` (e as novas chamadas de auth) passam a usar um cliente Supabase efêmero por requisição para todas as chamadas ao GoTrue (`sign_in_with_password`, `sign_up`, `resend`, `reset_password_for_email`), em vez de um cliente módulo-level compartilhado (`supabase_auth`) — fechando uma lacuna já identificada na spec existente mas ausente do código atual.

## Impact

- `backend/app/auth/auth_service.py` (reescrita: `AuthError`, `signup`, `resend_confirmation`, `send_password_reset`, `reset_password`, cliente efêmero em `login`).
- `backend/app/main.py` (4 rotas novas + ajuste no tratamento de erro de `/auth/login`).
- `backend/app/database.py` (novo helper `get_session_scoped_client`).
- `backend/.env` / `backend/.env.example` (nova variável `FRONTEND_URL`).
- `frontend/app/auth/signup/page.tsx`, `frontend/app/auth/forgot-password/page.tsx`, `frontend/app/auth/callback/page.tsx` (novas), `frontend/app/auth/login/page.tsx` (ajuste pontual).
- `frontend/hooks/useSignupMutation.ts`, `useResendConfirmationMutation.ts`, `useForgotPasswordMutation.ts`, `useResetPasswordMutation.ts` (novos).
- `frontend/middleware.ts` (regra de redirecionamento ajustada).
- Dependência externa (fora do código): Supabase Dashboard precisa ter "Confirm email" ativado, a Redirect URL `FRONTEND_URL/auth/callback` cadastrada, e SMTP customizado configurado (o envio padrão do Supabase é limitado a ~2 emails/hora, inviável em produção).
