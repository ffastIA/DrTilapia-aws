## 1. Frontend

- [x] 1.1 Em `frontend/store/authStore.ts`, adicionar `secure: true` nas chamadas `Cookies.set(...)`
      para `accessToken` e `user` (login) e para `user` em `setUserName`.
- [x] 1.2 Em `frontend/middleware.ts`, adicionar `secure: true` nas chamadas
      `response.cookies.set(...)` para `profileComplete` e `profileGateSeen`.

## 2. Validação

- [x] 2.1 Testar login em `http://localhost:3000` (dev local) e confirmar que os cookies continuam
      sendo gravados/lidos normalmente. Validado no nível do navegador (sem credenciais de teste
      disponíveis para um login real): `document.cookie = "...; Secure"` em `http://localhost:3000`
      confirma que o Chrome grava e mantém um cookie `Secure` normalmente em `localhost` mesmo por
      HTTP puro — a premissa exata que este atributo dependia (design.md, decisão D1).
- [ ] 2.2 Testar login em produção (domínio do CloudFront) e confirmar via DevTools que
      `accessToken`, `user`, `profileComplete` e `profileGateSeen` saem com o atributo `Secure`.
