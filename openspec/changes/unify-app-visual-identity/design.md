## Context

O sistema tem três paletas de design concorrentes hoje:

1. **Dr. Tilap-IA** (`frontend/styles/dr-tilapia.module.css`) — clara, azul-ardósia `#5980a6`,
   Barlow/Barlow Condensed, raio 0, zero sombra, zero transição. Escopada em `.theme`, usada só
   por `app/page.tsx`, `auth/login`, `auth/forgot-password`.
2. **Legada escura** — verde `#00C853` / fundo `#1A1A1A` / Poppins, declarada em três lugares
   redundantes (`styles/globals.css:5-19`, `tailwind.config.ts:15-27`, `lib/colors.ts`), com
   glassmorphism (`.glass-effect`). Usada por hub, dashboard, profile, videos.
3. **Tailwind ad-hoc** — gradientes azul/índigo (signup, callback) e cinza/slate (admin, images).
   Sem token compartilhado com nada.

Há ainda uma quarta convenção **referenciada mas não definida**: `consultoria/page.tsx` usa nomes
de token shadcn-style (`bg-background`, `text-foreground`, `bg-destructive/10`) que não existem no
Tailwind config — a página está visualmente quebrada em produção agora.

## Goals / Non-Goals

**Goals:**
- Uma única fonte de tokens de design, consumida por Tailwind e pelo CSS Module da landing.
- Todas as páginas da aplicação usam a paleta clara "Dr. Tilap-IA" (não uma variante escura dela).
- Nomenclatura de token compatível com o que `consultoria/page.tsx` já espera, resolvendo esse bug
  como efeito colateral em vez de reescrevê-lo.
- Um shell/layout compartilhado para `/main/*` elimina a duplicação de `handleBack()` e do botão
  "Voltar" em 6 páginas.
- Landing e login continuam pixel-idênticos ao estado atual — eles são a fonte, não o alvo.

**Non-Goals:**
- Não introduz dark mode / theming alternável. A decisão (confirmada com o usuário) é que o app
  inteiro adota o tema claro da landing; não há necessidade de suportar os dois.
- Não migra páginas Tailwind para CSS Modules. O CSS Module da landing continua exclusivo dela e
  das telas de auth já migradas; as demais páginas continuam em Tailwind, apenas apontando para os
  novos tokens.
- Não altera nenhuma chamada de API, hook de dados, mutation, rota ou lógica de autenticação.
- Não resolve o bug pré-existente e não relacionado do `QueryClientProvider` nunca montado em
  `app/providers.tsx` (achado durante a exploração, fica fora de escopo).

## Decisions

### 1. Tokens vivem em `frontend/lib/tokens.ts`, não só em CSS

**Decisão**: criar um módulo TypeScript (`lib/tokens.ts`) com a paleta como objeto exportado, e
importá-lo tanto em `tailwind.config.ts` quanto em `styles/globals.css` (via `:root`, valores
copiados manualmente — CSS não importa TS).

**Alternativa considerada**: declarar os tokens só em `:root` de `globals.css` e ler via
`var(--x)` dentro do Tailwind config usando `withOpacityValue`. Rejeitada porque
`consultoria/page.tsx` já usa modificadores de opacidade do Tailwind (`bg-destructive/10`,
`border-destructive/30`), que exigem que a cor seja um **hex/rgb literal** no config, não uma
`var()` — o Tailwind precisa do valor bruto para gerar `rgb(... / 0.1)`. Hex literal no
`tailwind.config.ts` foi a única opção que preserva esse uso já existente sem reescrever
`consultoria`.

**Trade-off aceito**: os valores existem fisicamente em dois lugares (`lib/tokens.ts` e o `:root`
de `globals.css`) porque CSS não pode importar TS. Mitigado com um comentário em cada arquivo
apontando para o outro.

### 2. Nomenclatura de token semântica (shadcn-like), não os nomes da marca

**Decisão**: os tokens do Tailwind se chamam `background`, `surface`, `card`, `foreground`,
`muted-foreground`, `border`, `primary` (com `.hover`/`.active`/`.foreground`/`.soft`), `ring`,
`destructive` (`.DEFAULT`/`.bg`), `success` (`.DEFAULT`/`.bg`) — não `accent`/`slate-blue`/etc.

**Porquê**: essa é exatamente a convenção que `consultoria/page.tsx` já usa. Adotá-la resolve a
página quebrada sem tocar nela, e dá ao restante do app um vocabulário família-agnóstico (qualquer
página que use `bg-card`/`text-foreground` funciona, independente de qual for a cor por trás).

### 3. `app/main/layout.tsx` novo, mas sem forçar redesign de conteúdo

**Decisão**: o layout novo cobre só o que é estrutural e duplicado — wrapper `.wrap` (max-width
1200px), nav com marca, e `handleBack()` centralizado exposto via um pequeno client component
(`BackButton`) que cada página usa. Não tenta unificar o conteúdo específico de cada página (ex.:
os cards do hub, os gráficos do dashboard).

**Alternativa considerada**: layout "burro" que só passa `children`, mantendo cada página com seu
próprio header. Rejeitada — é exatamente o estado atual que produz 6 botões "Voltar" diferentes;
o ponto desta change é eliminar essa duplicação.

### 4. Ordem de migração: fundação → kit → páginas, não página por página do zero

**Decisão**: as duas primeiras fases (tokens + kit de componentes) são pré-requisito bloqueante
para a terceira (varredura de páginas). Migrar uma página isolada antes da fundação existir
significaria hardcodar os mesmos hexes de novo, só que uma página por vez.

**Risco aceito**: a Fase 0/1 tem um checkpoint de build único que toca `globals.css`,
`tailwind.config.ts` e `app/layout.tsx` — arquivos que **todas** as páginas herdam. Um erro aqui
quebra a aplicação inteira simultaneamente, não incrementalmente. Mitigado exigindo
`npm run build` limpo e comparação visual da landing/login antes de prosseguir para a Fase 1.

### 5. `main/profile/page.ts` → `page.tsx`

**Decisão**: o arquivo é `.ts` hoje só porque foi escrito inteiramente com `React.createElement`
(TypeScript não permite JSX em arquivos `.ts`). Para usar o kit de componentes (`<Card>`,
`<PageHeader>`) ele precisa de JSX, logo precisa ser `.tsx`. Convertido integralmente nesta change
em vez de deixado como está, porque não há caminho para adotar o kit de componentes em
`React.createElement` sem o mesmo esforço de reescrita.

## Risks / Trade-offs

- **[Risco] Fundação de tokens (Fase 0/1) tem blast radius total — toda página herda
  `globals.css`/`tailwind.config.ts`/`app/layout.tsx`.**
  → Mitigação: checkpoint de build + comparação visual da landing/login imediatamente após a Fase 0,
  antes de tocar qualquer página do `/main/*`.

- **[Risco] `CATEGORY_THEME` em `_VideosPage.tsx` mapeia categorias para classes Tailwind
  dinamicamente; o Tailwind não tem `safelist` configurado.**
  → Mitigação: ao remapear as cores, manter cada entrada como uma string de classe **completa e
  literal** (ex. `'bg-primary/10 text-primary'`), nunca construída por concatenação/template —
  mesma disciplina que o código já segue hoje, só trocando os literais.

- **[Risco] Regressão visual silenciosa na landing/login**, já que os tokens que eles consomem
  passam a vir de fonte compartilhada em vez de serem hardcoded localmente.
  → Mitigação: `dr-tilapia.module.css` mantém os **mesmos nomes de custom property**
  (`--color-bg`, `--color-accent`, etc.) dentro de `.theme`; só a fonte dos valores muda de literal
  para `var(--x)` herdada de `:root`. Nenhuma classe do CSS Module muda de nome ou de regra.

- **[Trade-off] `borderRadius.DEFAULT: '0'` no Tailwind é uma mudança agressiva** — qualquer
  `rounded` (sem sufixo) em qualquer página do app muda de raio.
  → Aceito deliberadamente: é o efeito pretendido (unificar em cantos retos). Classes explícitas
  como `rounded-lg`/`rounded-xl`/`rounded-full` continuam funcionando com os valores padrão do
  Tailwind até serem removidas página por página na Fase 2 — não quebram, só ficam sinalizadas
  para limpeza.

## Migration Plan

1. Fase 0 (fundação) e Fase 1 (kit + layout) são pré-requisito de qualquer página — sem rollback
   parcial possível depois que uma página começa a depender do kit.
2. Fase 2 (páginas) é migrada e commitada uma página por vez — cada página é independente das
   outras depois que a fundação existe, permitindo revisão/rollback incremental sem afetar as
   demais.
3. Rollback: como é uma feature branch local sem deploy contínuo, rollback é `git revert` do(s)
   commit(s) da fase afetada; não há migração de dados ou schema envolvida.

## Open Questions

Nenhuma — direção (tema único claro em todo o app) e profundidade (tokens + kit de componentes)
já confirmadas com o usuário antes desta proposta.
