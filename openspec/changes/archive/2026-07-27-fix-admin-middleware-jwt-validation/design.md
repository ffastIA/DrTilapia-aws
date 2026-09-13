## Context

`frontend/middleware.ts` (Edge Runtime, roda antes de cada request nas rotas do `matcher`):
```ts
const token      = request.cookies.get('accessToken')?.value;
const userCookie = request.cookies.get('user')?.value;
...
if (pathname.startsWith('/main/admin') && token) {
  try {
    const user = JSON.parse(userCookie ?? '{}') as { role?: string };
    if (user?.role !== 'admin') {
      return NextResponse.redirect(new URL('/main/hub', request.url));
    }
  } catch {
    return NextResponse.redirect(new URL('/main/hub', request.url));
  }
}
```
`userCookie` é gravado pelo próprio cliente (`frontend/store/authStore.ts`, `Cookies.set('user', JSON.stringify(user), ...)`, sem `httpOnly`) — o middleware está confiando em um dado que o navegador do próprio usuário controla, sem nenhuma verificação criptográfica.

Importante: o **papel (admin/user) não vem embutido no JWT de sessão do Supabase** — o JWT emitido pelo GoTrue traz `role: "authenticated"` (um conceito de role do Postgres, igual para todo usuário logado), `sub` (user id), `exp`, etc., mas não a coluna `public.users.role` da aplicação. Essa é a razão de `backend/app/dependencies.py:32` fazer uma consulta separada a `public.users` para descobrir o papel — o mesmo vale aqui: não dá para inferir "é admin" só decodificando o JWT sem verificação adicional, é preciso confirmar contra o banco.

Esta sessão já corrigiu (`isolate-login-client-and-fix-users-rls`, arquivada) uma lacuna de RLS em `public.users`: hoje existe a policy `users_select_own` (`to authenticated using (auth.uid() = id)`), que permite que qualquer usuário autenticado leia **a própria linha** de `public.users` — incluindo o próprio `role` — usando seu próprio token, sem precisar de `service_role`. O endpoint REST do Supabase (`{SUPABASE_URL}/rest/v1/users`) já valida a assinatura e expiração do JWT internamente antes de aplicar RLS — ou seja, delegar a pergunta "este usuário é admin?" para uma chamada real a essa API **já resolve verificação de assinatura + expiração + autorização** em uma única chamada, sem precisar reimplementar verificação de JWT no Edge Runtime.

## Goals / Non-Goals

**Goals:**
- O gate de `/main/admin` no middleware nunca decide com base em um valor que o cliente pode escrever livremente.
- A verificação usa a mesma fonte de verdade que o backend já usa (`public.users.role`), sem duplicar lógica de decisão de autorização.
- Nenhuma dependência nova de verificação de JWT é necessária.

**Non-Goals:**
- Não implementar cache/memoização da checagem no middleware nesta mudança (cada request a `/main/admin/*` faz uma chamada de rede à API REST do Supabase) — otimização de performance fica para uma iteração futura, se o custo de latência se mostrar relevante.
- Não alterar a Regra 1 (presença de `accessToken`) nem a Regra 2 (redirecionar usuário logado para longe de `/auth/login`) — ambas permanecem como estão; o escopo é só a Regra 3 (checagem de admin).
- Não mudar o backend — `get_current_admin_user` já está correto.

## Decisions

1. **Middleware chama a API REST do Supabase diretamente (`GET {SUPABASE_URL}/rest/v1/users?select=role`) com `Authorization: Bearer <accessToken>` e `apikey: <anon key>`, e usa o `role` retornado.**
   - Sem filtro por `id` na query — a policy `users_select_own` já restringe o resultado à própria linha do usuário autenticado pelo token, então não há necessidade (nem risco) de decodificar o JWT para extrair o `sub` no middleware.
   - Se a resposta não vier 200 com exatamente uma linha contendo `role: "admin"`, redireciona para `/main/hub` — cobre token inválido, expirado, ou usuário não-admin, todos com o mesmo tratamento seguro (nega por padrão).
   - Alternativa considerada: verificar a assinatura do JWT localmente no middleware com uma lib como `jose` + `JWT_SECRET` compartilhado. Rejeitada — exigiria expor o segredo de assinatura do Supabase ao bundle do middleware (ainda que só server-side, é superfície extra), adicionaria uma dependência nova, e mesmo assim não resolveria sozinho a pergunta "é admin", que depende de `public.users` de qualquer forma. Chamar a API REST resolve as duas perguntas (token válido? é admin?) em uma única requisição, reaproveitando RLS já existente.
   - Alternativa considerada: expor um endpoint no backend FastAPI (`GET /auth/me`) e chamar esse em vez da API REST do Supabase diretamente. Rejeitada por adicionar uma dependência de rede a mais (frontend → backend → Supabase) quando frontend → Supabase direto já é suficiente e mais simples, e o frontend já tem a `anon key` disponível como configuração pública.
2. **A `anon key` do Supabase precisa estar disponível ao middleware.** Hoje o frontend não expõe `SUPABASE_URL`/`SUPABASE_ANON_KEY` como env vars (`frontend/.env.local` só tem `NEXT_PUBLIC_API_BASE_URL`/`NEXT_PUBLIC_APP_NAME`). Adicionar `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_ANON_KEY` (chave pública por natureza, segura para expor) — necessárias para o middleware montar a chamada REST.

## Risks / Trade-offs

- **[Trade-off] Latência extra por requisição a `/main/admin/*`** — uma chamada de rede síncrona no middleware antes de renderizar a página. Aceitável: só afeta rotas administrativas, não o app inteiro.
- **[Risco] Se a API REST do Supabase estiver indisponível, admins legítimos são redirecionados para `/main/hub`** (fail-closed) → aceitável e desejável do ponto de vista de segurança (nega acesso em caso de dúvida, em vez de abrir).
- **[Trade-off] Expor `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`** — a `anon key` é projetada para ser pública (é a mesma usada por `supabase-js` no navegador em qualquer app Supabase); não é o segredo `service_role`. Confirmar que nenhum outro código já espera esses nomes de variável com valores diferentes.
