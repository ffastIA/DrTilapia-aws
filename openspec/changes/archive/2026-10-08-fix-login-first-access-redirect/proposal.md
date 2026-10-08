## Why

Depois de criar a conta e confirmar o e-mail, o login mostra "Login realizado com sucesso!
Redirecionando..." e volta para `/auth/login?redirect=%2Fmain%2Fhub`, em vez de entrar no sistema. O
cookie `accessToken` é gravado corretamente e o middleware/CloudFront/nginx o aceitam (verificado com
requisições reais ao CloudFront); o que falha é a navegação:

- `frontend/app/auth/login/page.tsx` tem `<Link href="/main/hub">` (logo). O Next.js 14 faz prefetch
  desse link ao abrir a tela de login, ainda sem cookie. O middleware (`frontend/middleware.ts`, regra 1)
  responde com redirecionamento para `/auth/login?redirect=%2Fmain%2Fhub`, e o Router Cache guarda esse
  resultado.
- Após o login, `router.push('/main/hub')` reaproveita o resultado guardado e volta à tela de login sem
  fazer nenhuma requisição ao servidor.

Além do defeito, o destino pós-login hoje é sempre `/main/hub`. O usuário em primeiro acesso só chega ao
cadastro (`/main/profile`) por um redirecionamento posterior do middleware (`profile-onboarding-gate`),
que depende de o servidor Next alcançar o Supabase (se a consulta falha, trata o cadastro como
incompleto). O requisito de produto é outro: no primeiro acesso o usuário vai **direto** ao cadastro, onde
completa suas informações; o login só leva ao hub quando **não** é o primeiro acesso.

## What Changes

- `POST /auth/login` passa a devolver `profile_complete: bool` (campo aditivo, compatível com clientes
  atuais), verdadeiro quando existe linha em `user_profiles` para o usuário autenticado.
- A tela de login decide o destino: `profile_complete === false` → `/main/profile`; caso contrário →
  `/main/hub`.
- A navegação pós-login passa a ser uma navegação completa de página (`window.location.assign`), nunca
  `router.push`, para não reutilizar respostas de rota geradas antes de autenticar.
- Páginas de `/auth/*` deixam de fazer prefetch de rotas protegidas (`prefetch={false}` no link do logo da
  tela de login).
- Quando `profile_complete` é verdadeiro, o login grava o cookie `profileComplete=1` (a mesma semântica
  que `frontend/app/main/profile/page.tsx` já usa), evitando uma consulta REST redundante do middleware na
  primeira navegação ao hub.
- O gate do middleware passa a **cumprir** o que a spec `profile-onboarding-gate` já exige (decisão do
  produto: o cadastro é obrigatório): depois do primeiro redirecionamento ao cadastro, uma nova tentativa
  real de sair sem cadastro completo **desloga** o usuário (hoje `frontend/middleware.ts` só deixa passar).
- O middleware do Next 14 não distingue prefetch de navegação (remove `RSC`/`Next-Router-Prefetch` antes de
  chamá-lo). Para o logout por abandono não disparar sozinho, o link da marca em `app/main/layout.tsx`
  passa a usar `prefetch={false}`; nenhuma tela de quem tem cadastro incompleto pode pré-carregar `/main/*`.
- `AuthProvider` volta a sincronizar a sessão em memória com os cookies ao navegar para `/auth/login`,
  para que um logout feito pelo middleware (redirecionamento) não deixe o estado em memória "logado" e não
  provoque um novo loop de redirecionamento.

## Capabilities

### New Capabilities
- `login-navigation`: como o frontend navega após um login bem-sucedido e o que as telas de autenticação
  podem ou não pré-carregar.

### Modified Capabilities
- `profile-onboarding-gate`: o login passa a encaminhar o primeiro acesso diretamente ao cadastro, o
  backend informa no login se o cadastro está completo, telas do cadastro não disparam prefetch e o logout por abandono
  passa a limpar a sessão por completo.

## Impact

- Backend: `backend/app/main.py` (modelo `LoginResponse` e rota `/auth/login`),
  `backend/app/auth/auth_service.py` (consulta a `user_profiles`), testes em `backend/tests/`.
- Frontend: `frontend/app/auth/login/page.tsx`, `frontend/hooks/useLoginMutation.ts`,
  `frontend/store/authStore.ts` (gravação do cookie `profileComplete`), `frontend/middleware.ts` (logout
  por abandono), `frontend/app/main/layout.tsx` (`prefetch={false}`), `frontend/components/AuthProvider.tsx` (ressincronização com os cookies).
- Comportamento: usuários que hoje escapam do cadastro na 2ª tentativa passam a ser deslogados.
- Deploy: exige rebuild e redeploy do **backend e do frontend** (o campo novo vem do backend).
- Edições já feitas e ainda não commitadas em `frontend/app/auth/login/page.tsx` (navegação completa e
  `prefetch={false}`) fazem parte desta change.
