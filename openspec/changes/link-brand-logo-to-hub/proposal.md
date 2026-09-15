## Why

"Ao clicar no DrTilapia que fica ao lado do favicon, não direciona para o hub principal do sistema. Nada acontece."

Investigado: a marca "Dr. Tilap-IA" (imagem `LogoTAI.jpeg` + texto), que aparece ao lado do ícone no topo de várias páginas, é renderizada como um `<span>` puro — sem `<Link>`, `<a href>` ou `onClick` — em 5 lugares:

- `frontend/app/page.tsx` (L37-40, landing pública)
- `frontend/app/auth/login/page.tsx` (~L96-97)
- `frontend/app/auth/signup/page.tsx` (~L73-74)
- `frontend/app/auth/forgot-password/page.tsx` (~L67-68)
- `frontend/app/auth/callback/page.tsx` (~L98-99)

Por isso, clicar não faz nada nesses lugares — é markup puramente decorativo. O padrão correto já existe em `frontend/app/main/layout.tsx` (L14-17), usado no shell autenticado:

```tsx
<Link href="/main/hub" className="...">
  <Image src="/LogoTAI.jpeg" alt="Dr. Tilap-IA" width={28} height={23} />
  Dr. Tilap-IA
</Link>
```

## What Changes

- Aplicar o mesmo padrão (`<Link href="/main/hub">` envolvendo a mesma `Image` + texto, mantendo classes/estilos visuais atuais) nos 5 arquivos listados acima — troca mecânica de `<span>` por `<Link href="/main/hub">`, sem nenhuma lógica nova.
- Para um visitante não autenticado, `/main/hub` é protegido pelo `middleware.ts` (regra 1) e redireciona para `/auth/login` normalmente — comportamento seguro e esperado, igual ao de qualquer link para uma rota protegida.

## Capabilities

### New Capabilities
- `link-brand-logo-to-hub`: a marca "Dr. Tilap-IA" exibida ao lado do ícone da aplicação é sempre um link clicável para o hub principal, em qualquer página onde aparece.

## Impact

- **Código afetado**: `frontend/app/page.tsx`, `frontend/app/auth/login/page.tsx`, `frontend/app/auth/signup/page.tsx`, `frontend/app/auth/forgot-password/page.tsx`, `frontend/app/auth/callback/page.tsx`.
- **Comportamento observável**: clicar na marca/logo em qualquer uma dessas páginas navega para `/main/hub` (ou para `/auth/login`, se não autenticado, via middleware existente) — em vez de não fazer nada.
