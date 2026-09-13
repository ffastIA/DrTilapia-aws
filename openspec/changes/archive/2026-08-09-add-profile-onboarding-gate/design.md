## Context

`frontend/middleware.ts` já protege `/main/*` (sem token → login) e `/main/admin/*` (sem `role=admin` → hub), consultando a API REST do Supabase diretamente com o token do próprio usuário — nunca confiando em cookies graváveis pelo navegador para decisões de acesso restrito. Este design estende o mesmo middleware com uma nova regra: perfil incompleto (`add-user-profile`) bloqueia o acesso a qualquer página de `/main/*` exceto `/main/profile`.

O requisito do usuário descreve dois comportamentos distintos que a princípio parecem conflitantes:
1. "No primeiro acesso... redirecionado para a tela de cadastro **automaticamente**" — uma ação silenciosa, não punitiva.
2. "Caso saia sem preencher os campos obrigatórios, o sistema deve **deslogá-lo**" — uma ação punitiva.

A diferença entre os dois é *se o usuário já teve a chance de completar o cadastro antes de tentar sair*. O design abaixo resolve isso com uma máquina de estados simples de duas etapas.

## Goals / Non-Goals

**Goals:**
- Garantir que nenhum usuário use a área autenticada (além do próprio cadastro) sem antes completar os campos obrigatórios do perfil.
- Redirecionar automaticamente e sem atrito na primeira vez.
- Deslogar (não apenas re-redirecionar) quem tenta contornar o cadastro depois dessa primeira chance.
- Trocar a saudação por email pela saudação por nome em `/main/hub` assim que o nome existir.

**Non-Goals:**
- Não adiciona uma flag `onboarding_completed` no banco — a completude é inferida pela existência da linha em `user_profiles` (cujas colunas obrigatórias são `NOT NULL`), evitando uma segunda fonte de verdade que poderia dessincronizar do perfil real.
- Não altera o endpoint de login nem o fluxo de signup/confirmação de email.
- Não estende a substituição de email→nome a outras páginas (ex. `/main/dashboard` mostra "Usuário Logado"); fica restrito à página principal (`/main/hub`), conforme pedido.
- Não é um controle de segurança contra usuários mal-intencionados (ver Risco de cache abaixo) — é um gate de completude de dados, não uma barreira de autorização como a de admin.

## Decisions

### 1. Sinal de completude = existência da linha em `user_profiles`
Como `full_name`, `phone`, `farming_type` e `annual_production_tons` são `NOT NULL` (decisão de `add-user-profile`), uma linha só existe em `user_profiles` se todos os obrigatórios já foram preenchidos. Checar completude vira uma única pergunta booleana ("existe linha para este `user_id`?"), reaproveitando a RLS `user_profiles_select_own` já criada — sem precisar reimplementar a lista de campos obrigatórios no frontend/middleware.

### 2. Máquina de estados com dois cookies, resolvida no middleware
Dois cookies novos, não-`httpOnly` (mesmo padrão de `accessToken`/`user` já usados por `authStore.ts`), com escopo de sessão:

- `profileGateSeen`: marca que o usuário já recebeu o redirecionamento automático uma vez nesta sessão.
- `profileComplete`: cache positivo — só é gravado quando o middleware confirma (via REST) que a linha existe. Nunca cacheia o estado "incompleto", para que, assim que o usuário salvar o perfil, a próxima navegação já reflita a completude sem esperar expirar um cache negativo.

Fluxo em `middleware.ts` para requests a `/main/*` com token válido:
1. Se `pathname === '/main/profile'` → deixa passar sempre (o usuário precisa poder chegar lá para se cadastrar).
2. Se cookie `profileComplete=1` presente → deixa passar (fast path, sem chamada de rede).
3. Senão, consulta `GET {SUPABASE_URL}/rest/v1/user_profiles?select=user_id&limit=1` com o token do usuário (mesmo padrão de `isAdminToken`).
   - Se retornar 1 linha → seta `profileComplete=1` na resposta e deixa passar.
   - Se retornar 0 linhas (perfil incompleto):
     - Se cookie `profileGateSeen` **ausente** → seta `profileGateSeen=1` e redireciona para `/main/profile` (comportamento 1: silencioso).
     - Se cookie `profileGateSeen` **presente** → trata como abandono: limpa `accessToken`, `user`, `profileGateSeen` (todos os cookies de sessão) e redireciona para `/auth/login` (comportamento 2: logout).

### 3. Redirecionamento pós-salvamento é responsabilidade do frontend, não do middleware
`PUT /profile` é uma chamada à API do backend (origem diferente do Next.js), o middleware não participa dela. Ao receber sucesso, `frontend/app/main/profile/page.tsx` seta `profileComplete=1` via `js-cookie` (mesma lib já usada em `authStore.ts`) e navega para `/main/hub` com `router.push`. Isso evita uma chamada REST redundante ao Supabase logo em seguida, no primeiro request à página principal.

### 4. Nome no header vem de um novo campo `name` no `authStore`, populado ao carregar o perfil
`frontend/types/auth.ts` já declara `name?: string` em `User` (não usado hoje); `frontend/store/authStore.ts` duplica a interface `User` sem esse campo — alinhar as duas. Nova action `setUserName(name: string)` em `authStore` atualiza `user.name` in-memory e no cookie `user` (mantendo o padrão existente de persistir o objeto `user` inteiro em cookie). É chamada pelo hook `useProfile` (de `add-user-profile`) sempre que um perfil com `full_name` preenchido é carregado — tanto na página de perfil quanto (se necessário) em qualquer outro componente que precise do nome. `frontend/app/main/hub/page.tsx` passa a exibir `user?.name || user?.email`.

### 5. Gate aplica-se a todos os papéis, inclusive `admin`
Nada no pedido do usuário exclui administradores; um admin sem perfil completo também é redirecionado/deslogado nas mesmas condições. `/main/admin/*` continua exigindo `role=admin` *depois* de passar pelo gate de perfil (as duas regras são independentes e cumulativas).

## Risks / Trade-offs

- [`profileComplete=1` é um cookie comum, gravável pelo próprio navegador — um usuário poderia forjá-lo para pular o gate sem nunca completar o perfil] → Aceitável e documentado: este gate existe para garantir *completude de dados de cadastro*, não é uma fronteira de segurança (diferente do gate de `role=admin`, que sempre revalida contra a API mesmo com cookie `user` presente). Pior caso de burla: o usuário usa o sistema com perfil incompleto — mesmo resultado de hoje, antes desta change existir.
- [Chamada REST extra em toda navegação `/main/*` até o perfil ser completado] → Mitigado pelo cache `profileComplete`; o custo só existe enquanto o perfil estiver incompleto (esperado ser breve, já que o próprio gate empurra o preenchimento).
- [Usuário fecha a aba/perde conexão exatamente entre o redirecionamento silencioso e a tentativa seguinte] → Comportamento aceito: só a *próxima* navegação a `/main/*` (nova aba, próxima visita) aciona a checagem; não há como o servidor detectar o fechamento da aba em si.
- [Cookies novos (`profileGateSeen`, `profileComplete`) somem se o usuário limpar cookies do navegador no meio da sessão] → Sem impacto funcional: na pior hipótese o usuário recebe o redirecionamento silencioso de novo (não é punido por isso, já que `profileGateSeen` também some).

## Migration Plan

1. Aplicar depois (ou junto) de `add-user-profile` estar implementada — depende de `user_profiles` e de `GET/PUT /profile` existirem.
2. Deploy do middleware atualizado e das páginas alteradas — sem migration de banco nesta change.
3. Rollback: reverter `middleware.ts`, `hub/page.tsx`, `authStore.ts`/`types/auth.ts` e a lógica de redirecionamento em `profile/page.tsx` ao estado anterior; nenhum dado é perdido (a tabela `user_profiles` e os perfis já preenchidos permanecem intactos).

## Open Questions

- Nenhuma pendente — o comportamento para os dois casos citados pelo usuário (primeiro acesso vs. abandono) está resolvido pela máquina de estados de dois cookies acima.
