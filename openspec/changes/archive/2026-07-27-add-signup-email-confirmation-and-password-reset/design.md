## Context

Hoje `backend/app/main.py` tem uma única rota de auth (`POST /auth/login`, linhas 81-106) apoiada em `backend/app/auth/auth_service.py` (só o método `login()`). Usuários são criados exclusivamente por scripts admin (`create_user.py`, `criar_admin.py`) via `client.auth.admin.create_user(...)`. `public.users` só tem `id`, `email`, `role` (sem migrations no repo). O frontend não tem `@supabase/supabase-js` — toda interação com Supabase passa pelo FastAPI via `frontend/lib/api.ts` (proxy `/api-proxy/*`), exceto uma chamada REST direta em `middleware.ts` para checar `role`.

Descoberta feita durante o planejamento: a spec já existente `openspec/specs/supabase-client-isolation/spec.md` exige que chamadas de auth usem um cliente Supabase efêmero por requisição (não um singleton compartilhado), mas o `auth_service.py` atual usa o cliente módulo-level `supabase_auth` (`backend/app/database.py`) diretamente — a correção documentada nessa spec não sobreviveu à reconciliação de git feita anteriormente nesta sessão (o código veio de uma branch/versão diferente da que recebeu o fix original). Como esta mudança já reescreve `auth_service.py` para adicionar signup/reset, aplicamos o padrão de cliente efêmero em todas as chamadas de auth (novas e a existente `login`), fechando essa lacuna sem escopo adicional de exploração.

## Goals / Non-Goals

**Goals:**
- Cadastro público com confirmação de email obrigatória antes do primeiro login.
- Reenvio de confirmação e redefinição de senha via email, ambos sem vazar se um email existe na base (anti-enumeração).
- Preservar a arquitetura atual: nenhuma chamada direta do browser ao Supabase Auth; tudo passa pelo FastAPI.
- Fechar a lacuna de cliente compartilhado em `auth_service.py` (login + novas chamadas).

**Non-Goals:**
- Login social (OAuth/Google/etc.) — fora de escopo.
- Captcha/hCaptcha no signup — mencionado como possível melhoria futura, não implementado agora.
- Coletar nome/perfil estendido no signup — `public.users` continua só com `id/email/role`; não é criada nenhuma coluna nova (estado de confirmação vive só em `auth.users.email_confirmed_at` do Supabase).
- Auto-login a partir do link de redefinição de senha — após trocar a senha, o usuário faz login explícito de novo.

## Decisions

1. **Cliente efêmero por chamada de auth, não singleton.** Toda chamada GoTrue (`sign_in_with_password`, `sign_up`, `resend`, `reset_password_for_email`) cria um `create_client(SUPABASE_URL, SUPABASE_KEY)` novo e descartável. Alternativa rejeitada: continuar usando `supabase_auth` compartilhado (mais simples, mas é exatamente o padrão que a spec `supabase-client-isolation` já baniu por risco de vazamento de estado de auth entre requisições concorrentes).

2. **Exceção tipada `AuthError(code, message)` em vez de dict de resultado.** Compõe com o padrão `try/except HTTPException/except Exception` já usado em `main.py`; cada rota adiciona uma cláusula `except AuthError` antes do catch-all. Alternativa rejeitada: retornar `None`/dict com campo de erro (como o `login()` atual faz) — obriga todo chamador a lembrar de checar o campo, mais fácil de esquecer silenciosamente.

3. **Novo helper `get_session_scoped_client(access_token, refresh_token)` em `database.py`, sem tocar em `get_user_scoped_client` existente.** O helper existente só faz `client.postgrest.auth(access_token)` (autentica consultas de tabela via RLS) — insuficiente para `client.auth.update_user(...)`, que precisa de sessão GoTrue completa via `client.auth.set_session(access_token, refresh_token)`. Mantemos os dois helpers separados porque servem propósitos diferentes (consulta de tabela vs. mutação de sessão de auth) e `get_user_scoped_client` já tem outros usos consolidados (RLS de `fish_images`/`fish_analyses`) que não devem mudar de comportamento.

4. **Página única `/auth/callback` para os dois links de email** (confirmação de signup e redefinição de senha), ramificando pelo parâmetro `type` extraído de `window.location.hash`. Alternativa considerada e descartada: duas páginas separadas (`/auth/confirm` + `/auth/reset-password`) — tecnicamente mais simples por página, mas duplica o "parse de hash + tratamento de link inválido/expirado" sem necessidade; unificado por decisão do usuário durante a revisão do plano.

5. **Resposta sempre genérica em `resend-confirmation` e `forgot-password`, independente do estado real do email.** Evita enumeração de contas cadastradas. `signup` também retorna a mesma mensagem genérica tanto para email novo quanto já cadastrado (Supabase pode devolver um usuário com `identities=[]` para email já existente sem erro — tratado como sucesso genérico igual).

6. **`reset-password` (efetivação da troca) pode retornar erros específicos** (`400` link inválido/expirado, `422` senha fraca) — diferente dos dois acima, porque quem chama esse endpoint já possui um token só seu (não há enumeração possível).

7. **Middleware muda de nega-lista para permite-lista.** A regra "usuário já logado em `/auth/*` → redireciona pro hub" passa a valer só para `/auth/login` (e opcionalmente `/auth/signup`), não mais para todo `/auth/*` — para não expulsar alguém de `/auth/callback` que ainda tenha um cookie de sessão antigo.

## Risks / Trade-offs

- **[Risco] Formato exato da exceção de "email não confirmado" no gotrue instalado não está documentado** → Mitigação: testar empiricamente contra o projeto real antes de finalizar o `except` em `auth_service.login()` (criar usuário não confirmado, tentar login, inspecionar a exceção real).
- **[Risco] Mecanismo de entrega do link de email (fragmento `#access_token=...` vs. `?code=` PKCE) não confirmado pela documentação** → Mitigação: disparar de verdade os emails contra o projeto real e inspecionar a URL final antes de fechar a lógica de `callback/page.tsx`. Se for PKCE, a página precisará de um endpoint de troca adicional (reavaliar escopo nesse caso).
- **[Risco] `set_session(access_token, refresh_token)` — assinatura exata pode variar entre versões de `gotrue-py`** → Mitigação: confirmar contra a versão instalada (`requirements.txt`) e testar com um token real de recovery antes de considerar `reset-password` pronto.
- **[Risco] SMTP padrão do Supabase (~2 emails/hora) inviabiliza uso real** → Mitigação: configurar SMTP customizado no Dashboard antes de considerar a feature pronta para produção; sinalizado como bloqueador não-código.
- **[Trade-off] Anti-enumeração reduz a informação disponível para o usuário legítimo** (ex.: alguém que erra o email no forgot-password não recebe aviso de "email não encontrado") — aceito deliberadamente como prática de segurança padrão.

## Migration Plan

Sem dados existentes para migrar (nenhuma coluna nova em `public.users`, nenhuma mudança de schema). Deploy é aditivo: novas rotas, novos arquivos de frontend, uma variável de ambiente nova (`FRONTEND_URL`) e um ajuste de contrato de erro em `/auth/login` (mudança de 401 genérico para 401/403 diferenciado — não quebra o frontend porque o próprio frontend é atualizado na mesma mudança). Pré-requisitos manuais no Supabase Dashboard (Confirm email, Redirect URL, SMTP) devem ser feitos **antes** de testar ponta a ponta em produção, mas não bloqueiam o deploy do código em si (o código funciona localmente contra qualquer projeto Supabase configurado corretamente). Rollback: reverter o commit/PR; nenhuma migração de dados a desfazer.

## Open Questions

- Nenhuma pendente para o usuário — as incertezas técnicas (seção Risks) são verificações empíricas a fazer durante a implementação, não decisões de produto em aberto.
