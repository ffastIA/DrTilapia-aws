## Context

`frontend/app/main/layout.tsx` já resolve isso corretamente para o shell autenticado (`/main/*`): a marca é um `<Link href="/main/hub">`. As páginas públicas/de auth (landing, login, signup, forgot-password, callback) foram implementadas depois/separadamente e replicaram só a parte visual (Image + texto), sem o link.

## Goals / Non-Goals

**Goals:**
- Clicar na marca "Dr. Tilap-IA", em qualquer página onde ela aparece, navega para `/main/hub`.

**Non-Goals:**
- Não mudar o destino do link em `frontend/app/main/layout.tsx` (já correto).
- Não redesenhar a marca/estilo visual — só adicionar a navegação, preservando classes/estilos atuais de cada página.
- Não adicionar lógica condicional de destino (ex.: `/` para deslogado vs `/main/hub` para logado) — usar sempre `/main/hub`, deixando o `middleware.ts` existente decidir o redirecionamento para `/auth/login` quando não autenticado, exatamente como qualquer outro link para uma rota protegida já funciona hoje.

## Decisions

1. **Sempre linkar para `/main/hub`, mesmo em páginas públicas.** Alternativa considerada: linkar para `/` (home) na landing pública e para `/main/hub` só no shell autenticado — rejeitada por criar dois comportamentos diferentes para o mesmo elemento visual em páginas diferentes, e por já existir tratamento de autenticação no middleware que faz o destino "certo" acontecer sozinho (`/main/hub` → `/auth/login` se deslogado).

## Risks / Trade-offs

- Nenhum risco relevante — mudança puramente aditiva (envolver markup existente em `<Link>`), sem alterar lógica de autenticação/negócio.
