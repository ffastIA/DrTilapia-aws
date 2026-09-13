## 1. Backend — `database.py`

- [x] 1.1 Adicionar `get_session_scoped_client(access_token, refresh_token) -> Client` (cliente anon-key novo + `client.auth.set_session(access_token, refresh_token)`), sem alterar `get_user_scoped_client` existente.
- [x] 1.2 Verificado via `inspect.signature` na venv instalada (`supabase 2.31.0` / `gotrue 2.9.1`): `SyncGoTrueClient.set_session(self, access_token: str, refresh_token: str) -> AuthResponse` — assinatura confirmada, sem ajuste necessário.

## 2. Backend — `auth_service.py`

- [x] 2.1 Adicionada classe `AuthError(Exception)` com `code: str` e `message: str`.
- [x] 2.2 `login()` reescrito para usar `_fresh_auth_client()` (cliente efêmero anon-key) por chamada em vez do singleton `supabase_auth`; lógica de busca de role em `public.users` mantida.
- [x] 2.3 `login()` distingue "email não confirmado" de "credenciais inválidas" via `_is_email_not_confirmed()` (checa `AuthApiError.code == "email_not_confirmed"` com fallback por substring na mensagem). **Confirmado empiricamente pelo usuário (2026-07-27, task 9.3)**: conta real criada e não confirmada retorna de fato o erro de email não confirmado, e a UI exibe a mensagem distinta com o botão "Reenviar confirmação". A implementação inicial foi baseada no código-fonte instalado (`gotrue.errors.AuthApiError` expõe `.code`/`.status`) e na documentação do GoTrue; o teste ao vivo validou essa suposição.
- [x] 2.4 Adicionado `signup(email, password, email_redirect_to)`: cliente efêmero, `sign_up({"email","password","options":{"email_redirect_to":...}})`.
- [x] 2.5 Adicionado `resend_confirmation(email, email_redirect_to)`: cliente efêmero, `resend({"type":"signup","email":...,"options":{"email_redirect_to":...}})`; exceções engolidas internamente (só logadas).
- [x] 2.6 Adicionado `send_password_reset(email, redirect_to)`: cliente efêmero, `reset_password_for_email(email, {"redirect_to":...})`; mesmo padrão de engolir erro.
- [x] 2.7 Adicionado `reset_password(access_token, refresh_token, new_password)`: usa `get_session_scoped_client` + `client.auth.update_user({"password": new_password})`.

## 3. Backend — `main.py`

- [x] 3.1 Adicionado `FRONTEND_URL` (env var, default `http://localhost:3000`), usado para montar `redirect_to`/`email_redirect_to`.
- [x] 3.2 `POST /auth/login` modificado: `AuthError(code="email_not_confirmed")` → `403 {"detail":"email_not_confirmed"}`; `AuthError(code="invalid_credentials")` → `401 {"detail":"invalid_credentials"}`.
- [x] 3.3 Adicionado `POST /auth/signup` (`SignupRequest{email,password}`): chama `auth_service.signup`, upsert em `public.users`, retorna `201` com mensagem genérica — idêntica mesmo se o email já existir (erros de `AuthError`/exceção genérica engolidos, resposta genérica sempre retornada).
- [x] 3.4 Adicionado `POST /auth/resend-confirmation` (`{email}`): sempre `200` com mensagem genérica.
- [x] 3.5 Adicionado `POST /auth/forgot-password` (`{email}`): sempre `200` com mensagem genérica.
- [x] 3.6 Adicionado `POST /auth/reset-password` (`{access_token, refresh_token, new_password}`): `200` em sucesso; `400` token inválido/expirado; `422` para `AuthError(code="reset_failed")`.

## 4. Backend — configuração

- [x] 4.1 Adicionado `FRONTEND_URL=` em `backend/.env.example` (comentado) e `backend/.env` (`http://localhost:3000`). **Achado adicional fora do escopo original**: `backend/.env`'s `SUPABASE_KEY` ainda apontava para a chave `anon` legada, desativada na sessão anterior (C5) — corrigido para a `publishable key` nova (`sb_publishable_...`), confirmado via teste real (`sign_in_with_password` com senha errada agora retorna `400 invalid_credentials`, não mais `401 Legacy API keys are disabled`).

## 5. Frontend — hooks novos

- [x] 5.1 `frontend/hooks/useSignupMutation.ts` criado — mesmo padrão de `useLoginMutation.ts`.
- [x] 5.2 `frontend/hooks/useResendConfirmationMutation.ts` criado.
- [x] 5.3 `frontend/hooks/useForgotPasswordMutation.ts` criado.
- [x] 5.4 `frontend/hooks/useResetPasswordMutation.ts` criado. **Extra**: `useLoginMutation.ts` ganhou uma classe `LoginError` (com `.code`) e um mapa `KNOWN_ERROR_MESSAGES` para traduzir os códigos estáveis do backend (`invalid_credentials`/`email_not_confirmed`) em mensagens amigáveis, necessário para a tarefa 6.4 poder checar `error.code==="email_not_confirmed"` sem depender de string solta.

## 6. Frontend — páginas novas

- [x] 6.1 `frontend/app/auth/signup/page.tsx` criado.
- [x] 6.2 `frontend/app/auth/forgot-password/page.tsx` criado.
- [x] 6.3 `frontend/app/auth/callback/page.tsx` criado — ramifica por `type` (`signup`/`email_change` → confirmado; `recovery` com tokens → formulário; caso contrário → link inválido com links de saída).
- [x] 6.4 `frontend/app/auth/login/page.tsx` ajustado: erro `email_not_confirmed` mostra botão "Reenviar confirmação"; adicionados links "Criar conta" e "Esqueci minha senha".

## 7. Frontend — `middleware.ts`

- [x] 7.1 Regra trocada para permite-lista: só `/auth/login` e `/auth/signup` redirecionam para o hub se já logado; `/auth/callback` e `/auth/forgot-password` ficam sempre fora.

## 8. Verificação empírica (parcialmente concluída — ver notas)

- [x] 8.1 (parcial) Testado `sign_in_with_password` real contra o projeto (senha errada para um email inexistente): confirma `AuthApiError` com `.code=="invalid_credentials"`, `.status==400`, mensagem "Invalid login credentials". O cenário real de "email não confirmado" foi **confirmado depois pelo usuário (2026-07-27, task 9.3)**: criar conta via `/auth/signup` sem confirmar e tentar logar produz o erro específico esperado, validando `_is_email_not_confirmed()` (checa `.code=="email_not_confirmed"` com fallback por substring "not confirmed") — que até então era só uma suposição baseada na documentação do GoTrue.
- [x] 8.2 **CONFIRMADO pelo usuário (2026-07-27)** — fluxo de reset executado de ponta a ponta com um link de email real: solicitar redefinição → receber o email → abrir o link → redefinir a senha com sucesso. Isso confirma empiricamente que **a entrega é via fragmento de URL** (`#access_token=...&refresh_token=...&type=recovery`), como `callback/page.tsx` assumiu — e **não** via PKCE (`?code=`). Se fosse PKCE, a página teria exibido "Link inválido ou expirado" e o reset teria falhado. Nenhum endpoint adicional de troca de código é necessário.
- [x] 8.3 (parcial) `set_session(access_token, refresh_token)` confirmado via `inspect.signature` (tarefa 1.2) e exercitado de fato contra o projeto real com tokens inválidos: um token sem formato JWT gera `IndexError` (capturado pelo `except Exception` genérico → `AuthError(code="reset_failed")`); um token com formato JWT mas conteúdo inválido gera `pydantic.ValidationError` na decodificação local (mesmo caminho de erro). **CONFIRMADO (2026-07-27)**: o usuário completou a redefinição de senha usando um link de recovery real — ou seja, `get_session_scoped_client` → `set_session(access_token, refresh_token)` → `update_user({"password": ...})` funciona de fato contra o projeto real, com a assinatura implementada.

## 9. Verificação ponta a ponta

- [x] 9.1 **Validado pelo usuário (2026-07-27)**: cadastro de conta nova via `/auth/signup` → perfil criado em `public.users` com `role="user"` → email de confirmação recebido → confirmação concluída → login funcionando com a role correta.
- [x] 9.2 **Validado pelo usuário (2026-07-27)**: cadastro repetido com email já existente devolve resposta idêntica à de um email novo — anti-enumeração confirmada na prática.
- [x] 9.3 **Validado pelo usuário (2026-07-27)**: login antes de confirmar o email retorna o erro específico de email não confirmado, e a UI exibe a mensagem distinta com o botão "Reenviar confirmação"; após a confirmação, o login passa a funcionar. Isso confirma empiricamente a detecção implementada em `_is_email_not_confirmed()` (task 2.3), que até então era baseada só na documentação do GoTrue.
- [x] 9.4 Testado via HTTP real contra o backend rodando: `POST /auth/resend-confirmation` e `POST /auth/forgot-password` com emails inexistentes retornam `200` com a mensagem genérica esperada. (Envio efetivo para um endereço existente não testado, para não disparar emails reais desnecessários.)
- [x] 9.5 **Fluxo de redefinição de senha validado ponta a ponta pelo usuário (2026-07-27)**: `POST /auth/forgot-password` → Supabase `/auth/v1/recover` 200 OK → email entregue (SMTP Gmail da task 10.3) → link aberto em `/auth/callback` → nova senha definida com sucesso. Todo o caminho `forgot-password` → `callback` → `reset-password` está confirmado funcionando com dados reais.
- [x] 9.6 Testado via HTTP real: `POST /auth/reset-password` com token malformado retorna `422 {"detail":"reset_failed"}` — erro claro, não sucesso enganoso.
- [x] 9.7 Testado via curl com cookie `accessToken` fake contra o frontend rodando: `/auth/login` e `/auth/signup` redirecionam (`307 → /main/hub`); `/auth/callback` e `/auth/forgot-password` respondem `200` sem redirecionar.
- [x] 9.8 Não afetado por nenhuma mudança desta sessão (nenhum arquivo relacionado a `create_user.py`/`criar_admin.py` foi tocado); confirmado por revisão, não reexecutado.
- [x] 9.9 **Validado pelo usuário (2026-07-27)**: logins concorrentes de usuários diferentes seguidos de checagem de role admin, sem vazamento de estado entre os clientes efêmeros — confirma na prática a spec `supabase-client-isolation` ampliada por esta mudança.

## 10. Pré-requisitos manuais (Supabase Dashboard — não automatizável, comunicar ao usuário)

- [x] 10.1 "Confirm email" confirmado ativo em Authentication → Sign In / Providers (já estava ligado antes desta sessão).
- [x] 10.2 Redirect URL `http://localhost:3000/auth/callback` cadastrada em Authentication → URL Configuration (confirmado: "Successfully added 1 URL"). URL de produção ainda pendente de cadastro quando o domínio de produção existir.
- [x] 10.3 SMTP customizado configurado em Authentication → Emails → SMTP Settings, usando **Gmail SMTP** (não Resend — ver nota abaixo): host `smtp.gmail.com`, porta `465`, usuário/sender `ffasti.iot01@gmail.com`, senha = App Password gerada (2FA ativado na conta para permitir isso). Confirmado: "Successfully updated settings".

**Nota de desvio do plano original**: a ideia inicial era usar Resend + subdomínio de `enginetecnologia.com.br`, mas o Microsoft 365 admin center (que hospeda o DNS desse domínio) não oferece nenhuma forma de adicionar registros DNS customizados/avulsos (confirmado por exploração ao vivo em `admin.cloud.microsoft` e `admin.microsoft.com`, e descartada a hipótese de zona Azure DNS — sem assinatura Azure). O usuário optou por usar Gmail SMTP como solução imediata em vez de migrar o DNS do domínio corporativo para outro provedor. Limitações aceitas: remetente `ffasti.iot01@gmail.com` (não um domínio próprio), limite de ~500 emails/dia do Gmail.
