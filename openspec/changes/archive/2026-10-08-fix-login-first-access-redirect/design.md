## Context

O login (`frontend/app/auth/login/page.tsx`) chama `POST /api-proxy/auth/login`, grava os cookies
`accessToken`/`user` via `authStore.setAuth` e, após 2 s, navega para `/main/hub`. O middleware
(`frontend/middleware.ts`) protege `/main/*`: sem `accessToken` redireciona para
`/auth/login?redirect=<rota>`; com token e perfil incompleto, a regra 3 (`profile-onboarding-gate`) empurra
o usuário para `/main/profile` uma vez por sessão (`profileGateSeen`).

Completude do cadastro = existência de linha em `user_profiles` (decisão 1 de
`add-profile-onboarding-gate`: as colunas obrigatórias são `NOT NULL`, então a linha só existe com os
obrigatórios preenchidos).

Decisão de produto desta change: **o cadastro é obrigatório**. A spec `profile-onboarding-gate` já exigia
que, depois do primeiro redirecionamento, uma nova tentativa de sair sem cadastro completo deslogasse o
usuário; o middleware, porém, apenas deixa passar. Esta change alinha o código à spec.

## Goals / Non-Goals

**Goals:**
- Primeiro acesso entra direto no cadastro; só quem já completou o cadastro entra no hub.
- A navegação pós-login nunca depende de cache de rota criado antes de autenticar.
- Quem tenta abandonar o cadastro depois do primeiro redirecionamento é deslogado de verdade (cookies e
  estado em memória), sem loops de redirecionamento.
- O gate não é acionado por prefetch.

**Non-Goals:**
- Honrar o parâmetro `?redirect=` depois do login.
- Mudar a regra de completude (continua sendo a existência da linha em `user_profiles`).
- Transformar o gate em controle de segurança: o cookie `profileComplete` continua gravável pelo navegador
  (ver Riscos).

## Decisions

### 1. O backend informa `profile_complete` na resposta do login
`auth_service.login` já consulta `public.users` com `supabase_admin` depois de autenticar
(`backend/app/auth/auth_service.py`). Acrescenta-se uma consulta a `user_profiles`
(`select user_id ... limit 1` filtrada pelo `user_id`) e o resultado vira `profile_complete` em
`LoginResponse` (`backend/app/main.py`). Se a consulta falhar, o erro é logado e o campo vale `false`:
o login não pode falhar por causa disso.

Alternativas descartadas:
- *Frontend chama `GET /profile` depois do login*: uma ida e volta a mais e um ponto de falha extra antes
  do redirecionamento, para obter uma informação que o backend já está em condição de dar no mesmo request.
- *Confiar só no gate do middleware (login sempre vai ao hub)*: o middleware consulta o Supabase a partir
  do servidor Next; se essa chamada falha, trata como "incompleto" e mandaria até um usuário com cadastro
  completo ao `/main/profile`. O backend é a fonte mais confiável.

### 2. Destino decidido na tela de login
`onSuccess` do `loginMutation` recebe `profile_complete`:
- `false` → `/main/profile`;
- `true` ou ausente (backend antigo) → `/main/hub`. No caso ausente o gate do middleware continua
  decidindo; o comportamento é idêntico ao atual.

### 3. Navegação completa e sem prefetch
`window.location.assign(destino)` no lugar de `router.push`: a página é pedida ao servidor com os cookies
já gravados, sem passar pelo Router Cache. Em complemento, `prefetch={false}` no `<Link href="/main/hub">`
do logo evita que o cache seja populado antes do login. A recarga completa reinicializa o `AuthProvider`,
que restaura a sessão a partir dos cookies (`authStore.restoreAuth`).

### 4. Cookie `profileComplete` no login
Quando `profile_complete === true`, o login grava `profileComplete=1` (`path=/`, `SameSite=lax`) com o
atributo `Secure` derivado do protocolo da página (`window.location.protocol === 'https:'`), o mesmo
critério de `authStore.setAuth`. Assim o middleware não precisa consultar o Supabase na primeira
navegação ao hub. Quando `false`, o cookie **não** é gravado (o middleware nunca cacheia "incompleto").

### 5. O login não grava `profileGateSeen`
Encaminhar o usuário ao cadastro pelo login não conta como o "primeiro redirecionamento" do gate. Sequência
resultante para quem tem cadastro incompleto: login → `/main/profile`; 1ª tentativa de abrir outra página de
`/main/*` → o gate o devolve a `/main/profile` (silencioso, grava `profileGateSeen`); 2ª tentativa → logout.

### 6. Logout por abandono no middleware
Na regra 3 de `frontend/middleware.ts`, quando o cadastro está incompleto e `profileGateSeen=1` já existe,
o middleware responde com redirecionamento para `/auth/login` e expira, na própria resposta
(`path=/`, `maxAge=0`), os cookies `accessToken`, `user`, `profileGateSeen` e `profileComplete`. A lista é a
mesma que `authStore.clearAuth` remove.

### 7. Nenhuma tela do cadastro faz prefetch de rotas protegidas
O Next.js 14.2 remove os cabeçalhos internos (`RSC`, `Next-Router-State-Tree`, `Next-Router-Prefetch`) da
requisição antes de entregá-la ao middleware (`next/dist/server/web/adapter.js`, "Parameters should only be
stripped for middleware"), e também o parâmetro `_rsc` da URL. Logo o middleware **não consegue** distinguir
prefetch de navegação. Verificado na prática: um teste com `Next-Router-Prefetch: 1` não foi reconhecido.

Em produção o `<Link>` do logo em `app/main/layout.tsx` (visível em `/main/profile`) seria pré-carregado
assim que a tela abrisse; esse prefetch passaria pelo gate, consumiria o "empurrão" único (`profileGateSeen`)
e um segundo prefetch deslogaria o usuário sem ele ter clicado em nada. Decisão: tratar toda requisição de
`/main/*` recebida pelo gate como tentativa real **e** garantir na origem que as telas acessíveis a quem tem
cadastro incompleto não geram prefetch (`prefetch={false}` no link do layout; `/main/profile` não tem links
para `/main/*`; `BackButton`/pós-salvamento usam navegação programática, que não faz prefetch).

Alternativa descartada: logout só em requisições de documento (`Sec-Fetch-Dest: document`) e, em navegação
client-side, devolver sempre ao cadastro. Distingue prefetch sem depender de `prefetch={false}`, mas muda a
regra aprovada (a 2ª tentativa por clique não deslogaria) e deixa o usuário sem saída na tela de cadastro, que
não tem botão de sair.

### 8. `AuthProvider` ressincroniza com os cookies em `/auth/login`
O redirecionamento do middleware para `/auth/login` é uma navegação client-side que preserva o layout, e
portanto o `AuthProvider` e o store em memória (`isAuthenticated: true`). Como o `AuthProvider` empurra
`/auth/login` para `/main/hub` quando `isAuthenticated`, sem tratamento haveria um loop (hub → middleware →
login → hub). Regra: ao navegar para `/auth/login`, `AuthProvider` chama `restoreAuth()` (a fonte da verdade
são os cookies); sem `accessToken`, o estado em memória é limpo.

## Risks / Trade-offs

- [Cookies `profileComplete` e `profileGateSeen` são graváveis pelo navegador] → o gate continua sendo de
  completude de dados, não de segurança (mesmo risco aceito em `add-profile-onboarding-gate`). Quem forjar
  `profileComplete=1` usa o sistema sem cadastro; nenhum dado de outro usuário fica exposto.
- [Mudança de comportamento: usuários que hoje escapam do cadastro passam a ser deslogados] → é a decisão
  de produto; precisa constar na comunicação do deploy.
- [Fragilidade da decisão 7] Um futuro `<Link>` para `/main/*` em `/main/profile` ou no layout, com prefetch
  ativo (o padrão), reintroduziria o logout espontâneo. Mitigação: comentários em `middleware.ts` e em
  `app/main/layout.tsx`, e o requisito correspondente na spec.
- [Consulta REST do middleware falha] `hasCompletedProfile` devolve `false` quando o Supabase não responde;
  com a decisão 6 isso poderia deslogar um usuário que tem cadastro. Mitigação: o login grava
  `profileComplete=1` para quem tem cadastro (decisão 4), de modo que o caminho "consulta REST" só ocorre em
  quem não tem o cookie (outro navegador/dispositivo). Registrar em log a falha da consulta para diagnóstico.
- [Inconsistência existente] `frontend/app/main/profile/page.tsx` grava `profileComplete` sem `Secure`,
  enquanto `auth-cookie-security` exige `Secure` nesses cookies. Fora do escopo; o novo código do login já
  segue o critério correto.
