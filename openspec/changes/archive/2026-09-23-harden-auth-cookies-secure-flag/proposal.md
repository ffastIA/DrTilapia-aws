## Why

Nenhum cookie da aplicação (`accessToken`, `user`, `profileComplete`, `profileGateSeen`) marca o
atributo `Secure` — nem os gravados no browser via `js-cookie` em `frontend/store/authStore.ts`, nem
os gravados pelo middleware em `frontend/middleware.ts`. Isso nunca foi corrigido porque, até agora,
não havia garantia de que o usuário só acessaria a aplicação por HTTPS. Com a arquitetura de deploy
confirmada (CloudFront como única porta de entrada pública, `Viewer Protocol Policy = Redirect HTTP
to HTTPS`, já documentado em `deploy/README.md`), o usuário final **sempre** chega à aplicação por
HTTPS — não há mais motivo para os cookies aceitarem ser enviados por uma conexão HTTP, e marcá-los
como `Secure` fecha essa lacuna sem custo funcional.

## What Changes

- `frontend/store/authStore.ts`: adicionar `secure: true` em todas as chamadas `Cookies.set(...)`
  (`accessToken`, `user` no login, `user` em `setUserName`).
- `frontend/middleware.ts`: adicionar `secure: true` nas duas chamadas
  `response.cookies.set(...)` (`profileComplete`, `profileGateSeen`).
- Nenhuma mudança em `Cookies.remove(...)` (remoção de cookie não depende do atributo `secure` para
  funcionar).

## Capabilities

### New Capabilities
- `auth-cookie-security`: define os atributos de segurança (`Secure`, `SameSite`, `path`) que os
  cookies de autenticação/estado de UI da aplicação devem carregar.

### Modified Capabilities
(nenhuma — nenhum spec existente em `openspec/specs/` cobre atributos de cookie; o spec mais próximo,
`frontend-admin-route-gate`, trata do modelo de confiança de autorização admin, não dos atributos do
cookie em si)

## Impact

- Código afetado: `frontend/store/authStore.ts`, `frontend/middleware.ts`.
- Sem dependência de outras changes — pode ser aplicada a qualquer momento, independente de
  `add-two-ec2-deploy-topology` e `fix-frontend-backend-buildtime-url`.
- Sem mudança de comportamento observável para o usuário em produção (a aplicação já só é acessada
  via HTTPS); só reduz a superfície de exposição do cookie caso algum caminho HTTP direto mal
  configurado venha a existir.
