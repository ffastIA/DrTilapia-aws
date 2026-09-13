## Why

`frontend/middleware.ts` decide se uma requisição pode acessar `/main/admin` lendo o cookie `user` (gravado pelo próprio navegador via `js-cookie`, não `httpOnly`) e comparando `JSON.parse(userCookie).role !== 'admin'` (linhas 36-46). Esse cookie é gravável por qualquer script no navegador (`document.cookie = 'user={"role":"admin"}'`) e o middleware nunca valida o token em si — a regra 1 (linha 24) só checa a **presença** do cookie `accessToken`, nunca sua assinatura ou expiração. Qualquer usuário pode passar o gate de UI do painel admin sem nunca ter feito login como admin.

O backend continua validando corretamente em cada endpoint (`get_current_admin_user` consulta `public.users.role` via `service_role`, comprovado nas mudanças anteriores desta sessão), então **dados não vazam** por essa falha — mas a UI admin fica visível/navegável para qualquer usuário autenticado, o que é uma falha de defesa em profundidade e pode confundir/expor a existência de funcionalidades administrativas.

## What Changes

- `frontend/middleware.ts`: a Regra 3 (checagem de `/main/admin`) deixa de confiar no conteúdo do cookie `user` e passa a validar o JWT do `accessToken` de forma verificável antes de decidir o `role`.
- A Regra 1 (token ausente) passa também a validar minimamente a estrutura/expiração do JWT, não apenas sua presença.
- Nenhuma mudança de contrato para o usuário final: o comportamento observável (admin vê `/main/admin`, não-admin é redirecionado para `/main/hub`) permanece o mesmo — só a fonte de verdade da decisão muda de "o que o cookie diz" para "o que o token realmente prova".

## Capabilities

### New Capabilities
- `frontend-admin-route-gate`: Garantia de que o gate de rota `/main/admin` no middleware do Next.js deriva a autorização de um JWT verificável (assinatura + expiração), nunca de um valor de cookie gravável pelo cliente sem verificação.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: `frontend/middleware.ts` apenas.
- **Dependências**: pode requerer uma biblioteca de verificação de JWT compatível com o Edge Runtime do Next.js (ex.: `jose`), já que o middleware roda no Edge, não em Node.js puro.
- **Backend**: nenhuma mudança — a validação real de autorização em cada endpoint já é feita corretamente hoje; esta mudança é só a camada de UX/gate de navegação no frontend.
- **Comportamento observável**: nenhum, para usuários legítimos. Para alguém tentando forjar o cookie `user`, o acesso à UI de `/main/admin` deixa de ser possível.
