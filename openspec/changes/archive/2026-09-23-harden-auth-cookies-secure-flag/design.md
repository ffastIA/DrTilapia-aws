## Context

Cookies de autenticação/estado de UI são gravados em dois pontos do frontend:
- `frontend/store/authStore.ts` (client-side, via `js-cookie`): `accessToken` e `user` no login,
  `user` em `setUserName`.
- `frontend/middleware.ts` (server-side, `NextResponse`): `profileComplete` e `profileGateSeen`.

Nenhuma dessas chamadas define `secure`. Todas usam `path: '/'` e `sameSite: 'Lax'`/`'lax'`. Local
de desenvolvimento roda em `http://localhost:3000` (sem HTTPS) — motivo original, ainda que nunca
declarado explicitamente no código, para não marcar `secure` desde o início.

## Goals / Non-Goals

**Goals:**
- Marcar `secure: true` em todo cookie de autenticação/estado de UI escrito pela aplicação, sem
  quebrar o fluxo de desenvolvimento local.

**Non-Goals:**
- Não migra os cookies para `httpOnly` (exigiria mover a leitura do token do `js-cookie`
  client-side para um mecanismo server-side — fora de escopo, mudança maior de arquitetura de auth).
- Não adiciona o atributo `domain` explícito (não há necessidade de compartilhar o cookie entre
  subdomínios hoje).

## Decisions

### D1 — `secure: true` incondicional, sem branch por ambiente
Como o dev local roda em `http://localhost:3000`, marcar `secure: true` faz o browser recusar
enviar o cookie de volta em desenvolvimento (HTTP puro) — mas navegadores modernos (Chrome, Firefox,
Edge) tratam `localhost` como um "contexto seguro" mesmo por HTTP, e aceitam cookies `Secure`
gravados/lidos em `http://localhost`. Não é necessário nenhum branch condicional por `NODE_ENV`.
Alternativa descartada: condicionar `secure: process.env.NODE_ENV === 'production'` — adiciona
complexidade sem necessidade, já que `localhost` já é exceção nativa do browser.

## Risks / Trade-offs

- **[Risco] Se algum ambiente de desenvolvimento/teste rodar a aplicação por HTTP num hostname que
  não seja `localhost` (ex. IP da rede local, domínio interno sem TLS), os cookies deixam de ser
  enviados e o login para de funcionar nesse ambiente.** → Mitigação: nenhum ambiente documentado no
  repositório (dev local, produção via CloudFront) se encaixa nesse caso; se surgir, resolver com um
  branch por ambiente na hora, não preventivamente.

## Migration Plan

1. Editar as chamadas em `frontend/store/authStore.ts` e `frontend/middleware.ts`.
2. Testar login local (`http://localhost:3000`) e confirmar que os cookies continuam sendo gravados
   e lidos normalmente (navegador trata `localhost` como contexto seguro).
3. Testar login em produção (via domínio do CloudFront) e confirmar no DevTools que os cookies saem
   com o atributo `Secure`.

**Rollback**: reverter a mudança é remover `secure: true` das mesmas chamadas — sem efeito colateral
em dados persistidos (cookies não versionam estado no servidor).

## Open Questions

Nenhuma.
