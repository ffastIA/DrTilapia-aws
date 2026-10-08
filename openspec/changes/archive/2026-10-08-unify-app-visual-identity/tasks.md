## 1. Fundação de tokens

- [x] 1.1 Criar `frontend/lib/tokens.ts` com a paleta clara Dr. Tilap-IA (background, surface, card, foreground, muted-foreground, border, primary/hover/active/foreground/soft, ring, destructive/bg, success/bg), extraída verbatim de `dr-tilapia.module.css:7-46`.
- [x] 1.2 Reescrever `frontend/tailwind.config.ts` para importar `lib/tokens.ts`, expor os nomes semânticos que `consultoria/page.tsx` já usa (`background`, `card`, `foreground`, `border`, `destructive`, etc.), `fontFamily.heading`/`body` (Barlow Condensed/Barlow), `borderRadius.DEFAULT: '0'`, e os breakpoints `lp-lg`/`lp-md`/`lp-sm` (880/720/560px).
- [x] 1.3 Reescrever `frontend/styles/globals.css`: `:root` declara os mesmos valores de `lib/tokens.ts` como custom properties; `body` passa a `background`/`foreground` claros; scrollbar reescrita em cinzas neutros + accent; remover a classe `.glass-effect`.
- [x] 1.4 Em `frontend/app/layout.tsx`, trocar a fonte do `<body>` de Poppins para Barlow/Barlow Condensed (`${barlow.variable} ${barlowCondensed.variable} font-body`).
- [x] 1.5 Refatorar `frontend/styles/dr-tilapia.module.css`: o bloco `.theme` (linhas 7-54) deixa de declarar os valores das custom properties e passa a apenas consumi-las via `var(--x)` herdada de `:root` — sem renomear nenhuma classe ou remover nenhuma regra. (`--color-surface` e `--color-success`/`--color-success-bg` mantidos por herança direta do `:root`, já que têm o mesmo nome — redeclará-los seria auto-referência circular em CSS.)
- [x] 1.6 Remover `frontend/lib/colors.ts` (paleta escura duplicada, substituída por `lib/tokens.ts`) e limpar `inter`/`poppins` de `frontend/lib/fonts.ts` junto dos comentários `<br/>` vazados (linhas 7-8, 15-18).
- [x] 1.7 Remover os arquivos órfãos/quebrados: `frontend/app/globals.css` (scaffold Tailwind v4 não importado), `frontend/postcss.config.mjs` (conflita com `postcss.config.js`), `frontend/next.config.ts` (stub vazio), `frontend/components/DocumentCard.tsx` e `frontend/components/GlassContainer.tsx` (código morto, não compilam, sem uso).
- [x] 1.8 Checkpoint: `npx tsc --noEmit` não introduz nenhum erro novo (os 7 erros existentes — `consultoria/page.tsx` prop `size` do Button, `AuthProvider.tsx` var não usada, 5x `lib/ragAdminApi.ts` — são pré-existentes, em arquivos não tocados por esta fase, e ficam registrados na seção 7 para resolução: o de `size` é resolvido pela reescrita do `Button` na Fase 2/tarefa 2.2; os demais são bugs de tipagem em `ragAdminApi.ts`/`AuthProvider.tsx` fora do escopo visual desta change). `npm run build` completo só é possível depois que esses erros pré-existentes forem corrigidos — ver nova tarefa 7.0.

## 2. Kit de componentes + shell /main

- [x] 2.1 Criar `frontend/components/ui/CornerMarks.tsx`, extraído de `app/page.tsx:22-31`.
- [x] 2.2 Reescrever `frontend/components/Button.tsx` para os novos tokens e as 3 regras de design (raio 0, zero `box-shadow`, zero `transition`), replicando as variantes `.btn`/`.btnPrimary`/`.btnSecondary`/`.btnGhost`/`.btnBlock` de `dr-tilapia.module.css:348-393`. Adicionada também a prop `size` ('sm'/'md'), que resolve de graça o erro de tipo pré-existente em `consultoria/page.tsx`.
- [x] 2.3 Criar `frontend/components/ui/Card.tsx`, baseado em `.card`/`.cellFrame` (`dr-tilapia.module.css:207-228`, `:434-441`), com suporte opcional a `<CornerMarks>`.
- [x] 2.4 Criar `frontend/components/ui/Field.tsx` (label + `Input`), baseado em `.field`/`.input` (`dr-tilapia.module.css:396-422`).
- [x] 2.5 Criar `frontend/components/ui/Alert.tsx`, baseado em `.messageBox`/`.messageError`/`.messageSuccess` (`dr-tilapia.module.css:501-518`).
- [x] 2.6 Criar `frontend/components/ui/PageHeader.tsx` (kicker + regra + título), baseado em `.kicker`/`.captionRule`/`.splitTitle`.
- [x] 2.7 Criar `frontend/components/ui/Modal.tsx`, baseado em `.card`, para os modais de vídeo e admin.
- [x] 2.8 Criar `frontend/components/ui/BackButton.tsx` com `handleBack()` centralizado (`window.history.length > 1 ? router.back() : router.push('/main/hub')`).
- [x] 2.9 Criar `frontend/app/main/layout.tsx`: shell com `.wrap` (max 1200px, gutter `--edge`), nav com a marca. `<BackButton>` fica a critério de cada página (o hub não usa), não é forçado pelo layout.
- [x] 2.10 Atualizar `frontend/app/auth/layout.tsx` para o fundo claro da identidade (`bg-background`, Tailwind) em vez do gradiente `from-slate-900 via-slate-800 to-slate-900` — só visível atrás de signup/callback, já que login/forgot-password pintam seu próprio fundo opaco por cima.
- [x] 2.11 Atualizar `frontend/components/ChatMessage.tsx` para os novos nomes de token (`bg-primary`/`bg-surface`/`text-text-secondary` → tokens atuais).
- [x] 2.12 Checkpoint: `npx tsc --noEmit` sem erros novos (o erro de `size` na consultoria desapareceu — o `Button` reescrito já suporta a prop).

## 3. Páginas de autenticação restantes

- [x] 3.1 Migrar `frontend/app/auth/signup/page.tsx` para os tokens e o kit de componentes (`Field`, `Button`, `Alert`), preservando toda a lógica de validação e as chamadas existentes.
- [x] 3.2 Migrar `frontend/app/auth/callback/page.tsx` (4 estados: loading, email confirmado, link inválido, formulário de reset) da mesma forma, sem alterar nenhuma chamada ao Supabase.

## 4. Páginas /main — leves

- [x] 4.1 Migrar `frontend/app/main/consultoria/page.tsx` para o kit (`Button`, `PageHeader`/`BackButton`), aproveitando que os nomes de token já batem. Removido o `<header>` próprio (agora coberto pelo `app/main/layout.tsx`); a área de mensagens usa `max-h-[55vh] overflow-y-auto` em vez de `h-screen`/`flex-1`, já que a página passou a viver dentro do wrap com padding do layout compartilhado — mesma lógica de envio/limpeza/fontes, só o container de scroll mudou de estratégia de altura.
- [x] 4.2 Migrar `frontend/app/main/dashboard/page.tsx`.
- [x] 4.3 Migrar `frontend/app/main/hub/page.tsx`: `FeatureCard` interno passa a usar `Card` + `CornerMarks`.

## 5. Página /main/profile — conversão .ts → .tsx

- [x] 5.1 Renomear `frontend/app/main/profile/page.ts` para `page.tsx` e reescrever os 168 `React.createElement` como JSX equivalente, sem alterar o conteúdo exibido.
- [x] 5.2 Migrar o conteúdo para os tokens e o kit de componentes (`Card`, `PageHeader`/`BackButton`). De passagem, corrigido `components/LoadingSpinner.tsx:39`, que ainda referenciava o token antigo `text-text-secondary` (renomeado para `text-muted-foreground`).

## 6. Páginas /main — administração e mídia

- [x] 6.1 Migrar `frontend/app/main/admin/page.tsx` (upload de PDF, lista de documentos indexados, modal de exclusão, purga do banco) para os tokens e o kit (`Card`, `Field`, `Alert`, `Modal`, `Button`).
- [x] 6.2 Migrar `frontend/app/main/images/dashboard/_DashboardPage.tsx`, incluindo os hexes de SVG hardcoded (linhas 66-80, 261-301) para os tokens — eixos/labels via `var(--color-border)`/`var(--color-muted-foreground)`, linha/pontos via `var(--color-primary)` (suportado em atributos de apresentação SVG). Os 4 painéis (Kvol/Comprimento/Altura/Largura) deixam de ter uma cor própria (laranja/azul/teal/roxo) e passam a usar o mesmo accent, consistente com a identidade mono-accent.
- [x] 6.3 Migrar `frontend/app/main/images/_ImagesPage.tsx` (upload duplo lateral/superior, painel de resultados de biometria). Layout interno trocado de split fixo `height: calc(100vh-65px)` para um grid responsivo dentro do wrap compartilhado do `app/main/layout.tsx` — mesma lógica de upload/processamento/resultados, só a estratégia de altura mudou.
- [x] 6.4 Migrar `frontend/app/main/videos/_VideosPage.tsx`, remapeando `CATEGORY_THEME` para `CATEGORY_LABEL` (só rótulo, sem gradiente/badge por cor — identidade mono-accent) — sem concatenação dinâmica de classe em nenhum dos dois.

## 7. Limpeza e QA

- [x] 7.0 Corrigir os erros de tipo pré-existentes e não relacionados ao visual, descobertos no checkpoint 1.8, que bloqueiam `npm run build`: `frontend/components/AuthProvider.tsx:28` (variável `publicRoutes` não usada) e `frontend/lib/ragAdminApi.ts:35,200-201,250,254` (tipos de `Date`/união/retorno incorretos) — apenas correções de tipo, sem alterar comportamento. `npx tsc --noEmit` agora limpo (zero erros).
- [x] 7.1 `grep -rE "glass-effect|#00C853|purple-|bg-gray-900|rounded-xl|from-slate-900|from-blue-50" frontend/app frontend/components` e resolver todos os resíduos encontrados. Varredura ampliada (`bg-gray-*`, `text-gray-*`, `border-gray-*`, `bg-black`, `bg-white`, `bg-red/green/blue/yellow-*`, `shadow-*`, `backdrop-blur`, `from/via-gray-*`, `animate-ping`) também não encontrou resíduos em `app/` ou `components/`.
- [ ] 7.2 **Pendente — requer navegador.** Conferir os 3 breakpoints (880px, 720px, 560px) e o contraste do texto claro em cada uma das 12 páginas migradas. Não foi possível nesta sessão: a extensão Claude-in-Chrome não está conectada. Verificado por HTTP: `npm run dev` sobe sem erro, `/` e as 4 rotas de auth respondem 200, as 8 rotas `/main/*` respondem 307 redirecionando corretamente para `/auth/login?redirect=...` (gate de autenticação inalterado), e o HTML servido confirma as classes de fonte Barlow (`__variable_*`) e o token `bg-background` aplicados no `<body>`/spinner inicial.
- [ ] 7.3 **Pendente — requer navegador ou sessão autenticada.** Percorrer manualmente as 13 rotas confirmando que os fluxos funcionais (login válido/inválido + reenvio de confirmação, envio de pergunta com fontes na consultoria, upload de PDF no admin) continuam idênticos ao comportamento anterior. Nenhuma chamada de API/hook foi alterada nas migrações desta change (só JSX/className), risco de regressão funcional é baixo, mas a confirmação visual/interativa fica para o usuário ou para uma sessão com o Claude-in-Chrome conectado.
- [x] 7.4 `cd frontend && npm run build` final sem erros ou warnings novos — as 14 rotas compilam e prerenderizam como estático com sucesso.
