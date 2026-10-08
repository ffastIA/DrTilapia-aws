## Why

A identidade "Dr. Tilap-IA" (paleta clara, tipografia Barlow/Barlow Condensed, cantos retos, bordas
hairline) hoje só existe na landing page e nas telas de login/esqueci-senha. O restante do sistema
(12 páginas, ~3.044 linhas) roda em três paletas Tailwind concorrentes e não relacionadas: verde
`#00C853`/fundo escuro `#1A1A1A` (hub, dashboard, profile, videos, admin, images), gradiente
azul/índigo (signup, callback) e glassmorphism roxo. O CSS Module da landing
(`frontend/styles/dr-tilapia.module.css`) declara isso explicitamente: seus tokens são escopados
"so it never leak into /main/*". O usuário quer que todas as páginas compartilhem o mesmo padrão
de cores e estilo da landing.

Duas issues concretas tornam isso mais que estética: `frontend/app/main/consultoria/page.tsx` já
referencia tokens Tailwind semânticos (`bg-background`, `bg-card`, `text-foreground`,
`border-border`, `focus:ring-ring`, `bg-destructive/10`) que não existem em `tailwind.config.ts` —
a página renderiza sem fundo, borda ou cor de card hoje. E a ausência de um `app/main/layout.tsx`
faz com que 6 páginas dupliquem `handleBack()` e cada uma exiba um botão "Voltar" diferente.

## What Changes

- **BREAKING (visual, não funcional)**: promove os tokens de cor/tipografia/raio da landing
  (`frontend/styles/dr-tilapia.module.css:7-54`) de escopo local (`.theme`) para `:root` global,
  via uma nova fonte única `frontend/lib/tokens.ts` espelhada em `tailwind.config.ts` e
  `styles/globals.css`. Isso substitui a paleta escura atual (verde/`#1A1A1A`) em todas as rotas
  `/main/*` e nas telas `auth/signup`/`auth/callback` pela paleta clara azul-ardósia da landing.
- Corpo do app troca de Poppins para Barlow/Barlow Condensed (`app/layout.tsx`).
- Novo kit de componentes compartilhado (`frontend/components/ui/`: Button, Card, CornerMarks,
  Field/Input, Alert, PageHeader, Modal) que replica as regras de design da landing (raio 0, zero
  `box-shadow`, zero `transition`) e substitui os estilos ad-hoc espalhados pelas páginas.
- Novo `frontend/app/main/layout.tsx` com shell e `handleBack()` centralizados, removendo a
  duplicação em hub, dashboard, consultoria, admin, profile e videos.
- As 12 páginas fora da landing/login são migradas para os novos tokens/componentes — sem alterar
  nenhuma chamada de API, hook, rota ou lógica de autenticação/negócio.
- `frontend/app/main/profile/page.ts` renomeado para `page.tsx` e convertido de
  `React.createElement` para JSX (pré-condição para usar o kit de componentes).
- `frontend/app/main/consultoria/page.tsx` passa a renderizar corretamente como efeito colateral
  de os tokens `background`/`card`/`foreground`/`border`/`destructive` passarem a existir.
- Remoção de arquivos órfãos/quebrados que competem com esta identidade: `frontend/app/globals.css`
  (scaffold Tailwind v4 não importado por ninguém), `postcss.config.mjs` (conflita com
  `postcss.config.js`), `next.config.ts` (stub vazio), `frontend/lib/colors.ts` (paleta escura
  duplicada), `frontend/components/DocumentCard.tsx` e `frontend/components/GlassContainer.tsx`
  (código morto que não compila — não usados por nenhuma página).
- A landing (`/`) e as telas `auth/login`/`auth/forgot-password` permanecem visualmente idênticas
  ao estado atual: são a fonte da identidade, não o alvo da migração.

## Capabilities

### New Capabilities
Nenhuma.

### Modified Capabilities
- `dr-tilapia-visual-identity`: o requisito atual "Other routes are unaffected" (rotas `/main/*` e
  `auth/signup`/`auth/callback` mantêm tema próprio) é invertido — todas as rotas da aplicação
  SHALL compartilhar os mesmos tokens de design (cor, tipografia, espaçamento, raio) da landing,
  com equivalência comportamental preservada em toda a superfície de autenticação, não só
  login/forgot-password.

## Impact

- Tokens/config: `frontend/lib/tokens.ts` (novo), `frontend/tailwind.config.ts`,
  `frontend/styles/globals.css`, `frontend/styles/dr-tilapia.module.css` (bloco `.theme` passa a
  consumir tokens globais em vez de declará-los), `frontend/app/layout.tsx`, `frontend/lib/fonts.ts`.
- Novo diretório `frontend/components/ui/` e `frontend/app/main/layout.tsx`.
- Reescrita visual de 12 arquivos de página: `auth/signup`, `auth/callback`, `main/hub`,
  `main/consultoria`, `main/dashboard`, `main/profile` (renomeado `.ts`→`.tsx`), `main/admin`,
  `main/images` (`_ImagesPage.tsx`), `main/images/dashboard` (`_DashboardPage.tsx`), `main/videos`
  (`_VideosPage.tsx`), `frontend/app/auth/layout.tsx`, `frontend/components/ChatMessage.tsx`,
  `frontend/components/Button.tsx`.
- Remoção: `frontend/app/globals.css`, `frontend/postcss.config.mjs`, `frontend/next.config.ts`,
  `frontend/lib/colors.ts`, `frontend/components/DocumentCard.tsx`,
  `frontend/components/GlassContainer.tsx`.
- Spec: `openspec/specs/dr-tilapia-visual-identity/spec.md` (requisito de escopo invertido).
- Nenhum arquivo de `backend/` é afetado; nenhuma rota, hook de dados, mutation ou fluxo de
  autenticação muda de comportamento.
