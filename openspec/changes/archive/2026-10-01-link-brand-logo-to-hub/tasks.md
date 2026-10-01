## 1. Envolver a marca com Link nas 5 páginas

- [x] 1.1 `frontend/app/page.tsx` (L37-40): trocar `<span className={styles.navBrand}>` por `<Link href="/main/hub" className={styles.navBrand}>` (fechando com `</Link>`), mantendo `Image` + texto inalterados.
- [x] 1.2 `frontend/app/auth/login/page.tsx` (~L96-97): mesmo padrão (aplicado no `<div className={styles.cardBrand}>`, virou `<Link>`).
- [x] 1.3 `frontend/app/auth/signup/page.tsx` (~L73-74): mesmo padrão (aplicado no `<div className="flex items-center gap-2 mb-6">`, virou `<Link>`).
- [x] 1.4 `frontend/app/auth/forgot-password/page.tsx` (~L67-68): mesmo padrão (`cardBrand`).
- [x] 1.5 `frontend/app/auth/callback/page.tsx` (~L98-99): mesmo padrão (`flex items-center gap-2 mb-6`).
- [x] 1.6 Confirmar import de `Link` de `next/link` em cada arquivo. Já estava importado nos 5 arquivos antes desta mudança — nenhum import novo foi necessário.

## 2. Verificação

- [x] 2.1 `npx tsc --noEmit` no frontend — sem erros. `docker compose up -d --build frontend` — build do Next.js concluído sem erros, container saudável. Testado via Chrome (Claude in Chrome): na landing (`/`) e na página de login, clicar na marca "Dr. Tilap-IA" navega para `/main/hub`, que o middleware corretamente redireciona para `/auth/login?redirect=%2Fmain%2Fhub` (sessão anônima) — comportamento esperado, confirma que o link está funcionando (antes, clicar não fazia nada). Não testado logado (exigiria uma sessão real); o destino (`/main/hub`) é o mesmo já usado com sucesso em `main/layout.tsx`.
- [x] 2.2 Conferido visualmente via screenshot: layout/espaçamento da marca inalterado nas páginas testadas (landing, login) — só a navegação foi adicionada.
