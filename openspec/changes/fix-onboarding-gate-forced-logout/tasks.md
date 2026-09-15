## 1. Middleware — remover logout forçado

- [x] 1.1 Em `frontend/middleware.ts`, regra 3 (bloco `if (!alreadySeen) { ... } else { ... }`): removido o branch `else` que chamava `clearSessionCookies(response)` + redirecionava para `/auth/login`. Agora, quando `alreadySeen` é verdadeiro, o bloco simplesmente não retorna uma resposta antecipada — a função continua e cai no `NextResponse.next()` final, deixando a navegação seguir normalmente para a página originalmente pedida.
- [x] 1.2 Confirmado: `profileGateSeen` continua sendo lido/setado normalmente no branch de primeiro acesso (`!alreadySeen`) — nenhuma mudança ali.
- [x] 1.3 (achado durante a implementação, fora da lista original) A função `clearSessionCookies()` ficou sem nenhum chamador depois da remoção do branch — removida do arquivo (código morto), e o comentário de cabeçalho do arquivo (regras 1-4) atualizado para descrever o novo comportamento da regra 3.

## 2. Logout normal — paridade de limpeza de cookies

- [x] 2.1 Em `frontend/store/authStore.ts`, `clearAuth()`: adicionado `Cookies.remove('profileGateSeen', { path: '/' })` e `Cookies.remove('profileComplete', { path: '/' })`, junto aos `Cookies.remove` existentes de `accessToken`/`user`.

## 3. Verificação

- [x] 3.0 `npx tsc --noEmit` no frontend (inclui `middleware.ts` e `authStore.ts`) — sem erros. `docker compose up -d --build frontend` — build e start sem erros, container saudável.
- [ ] 3.1 Cenário "primeiro acesso": usuário sem perfil faz login → é redirecionado para `/main/profile` (comportamento inalterado). **Não testado nesta sessão** (exigiria um usuário de teste com perfil incompleto); a lógica desse branch não foi tocada pela mudança.
- [ ] 3.2 Cenário do bug 1: nesse mesmo usuário (perfil ainda incompleto), navegar manualmente para `/main/hub` → deve permitir o acesso normal ao hub, sem logout. **Não testado nesta sessão** (mesmo motivo). Verificado por leitura de código: o branch que fazia `clearSessionCookies`+redirect foi removido; a função agora só retorna respostas antecipadas nos ramos "perfil completo" e "primeiro acesso", caindo no `NextResponse.next()` final em qualquer outro caso.
- [ ] 3.3 Cenário do bug 2: clicar em "Voltar" (`BackButton`) em `/main/profile` sem ter salvado o cadastro → deve navegar normalmente, sem deslogar. **Não testado nesta sessão** — mesma lógica do item 3.2, já que o `BackButton` não foi alterado (o problema estava inteiramente no middleware).
- [ ] 3.4 Cenário de regressão: usuário com perfil completo continua tendo acesso irrestrito a `/main/*`. **Não testado nesta sessão**; branch `profileCompleteCookie`/`hasCompletedProfile()` não foi tocado.
- [ ] 3.5 Cenário de regressão: completar o cadastro em `/main/profile` continua redirecionando para `/main/hub`. **Não testado nesta sessão**; fora do arquivo alterado (fica em `frontend/app/main/profile/page.tsx`, não tocado).
- [ ] 3.6 Logout normal seguido de novo login (perfil ainda incompleto) → reinicia o ciclo de "primeiro acesso" sem `profileGateSeen` obsoleto. **Não testado nesta sessão** (exigiria fluxo de login/logout real com usuário de teste); a mudança em `clearAuth()` foi verificada por leitura de código (mesmo padrão de `Cookies.remove` já usado para `accessToken`/`user`).

**Recomendação:** os itens 3.1-3.6 exigem um usuário de teste real com perfil incompleto para validar ponta a ponta (login → gate → segunda navegação/voltar → hub; logout → login de novo → gate reaparece). Ficam como QA manual recomendado antes de considerar esta mudança totalmente encerrada.
