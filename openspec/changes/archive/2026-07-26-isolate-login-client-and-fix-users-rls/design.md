## Context

`backend/app/database.py` já cria dois clientes Supabase distintos:
- `supabase_auth: Client = create_client(SUPABASE_URL, auth_key)` — usando `SUPABASE_KEY` (chave `anon`), pensado para operações de autenticação de usuário final.
- `supabase_admin: Client = create_client(SUPABASE_URL, admin_key)` — usando `SUPABASE_SERVICE_ROLE_KEY`, para operações privilegiadas (bypass de RLS).
- `supabase: Client = supabase_admin` — alias de compatibilidade retroativa, usado em `dependencies.py`, `vector_admin_repository.py` etc.

Existe até uma classe `AuthService` em `backend/app/auth/auth_service.py` cujo método `login` já usa corretamente `supabase_auth.auth.sign_in_with_password(...)` — mas o endpoint real `POST /auth/login` em `backend/app/main.py` **não usa essa classe**; ele reimplementa a lógica de login inline, chamando `supabase_admin.auth.sign_in_with_password(...)` diretamente. Ou seja, a separação de clientes já existia no código, mas o endpoint ativo não a utiliza.

A biblioteca `supabase-py` (`SyncClient`) registra `self.auth.on_auth_state_change(self._listen_to_auth_events)` na construção do cliente. Esse listener, em qualquer evento `SIGNED_IN`/`TOKEN_REFRESHED`/`SIGNED_OUT`, substitui `self._auth_token` (o header usado por `.table()`/`.storage()`/`.rpc()` daquele cliente) pelo token da sessão do evento. Como `supabase_admin` é um **singleton no nível do módulo**, compartilhado por todas as requisições concorrentes do processo FastAPI, uma chamada a `sign_in_with_password` nele afeta imediatamente todas as outras requisições em andamento ou futuras que usem `supabase`/`supabase_admin`, até o próximo evento de auth.

Confirmado ao vivo nesta sessão: após dois logins sequenciais (`/auth/login` para um usuário admin de teste, depois para um usuário comum de teste), uma chamada subsequente a `/admin/vector-base/files` com o token do **admin** retornou `401 Usuário não encontrado`, porque `dependencies.get_current_user` fez `supabase.table('users').select(...).eq('id', admin_uid)` usando o cliente `supabase_admin`, cujo header de autorização já havia sido rebaixado para o token do usuário comum pelo login mais recente.

Investigação complementar via `execute_sql` (skills `supabase` / `supabase-postgres-best-practices`) mostrou que `public.users` tem `relrowsecurity=true` mas **nenhuma policy** cadastrada em `pg_policies` — deny-by-default para qualquer role que não seja o verdadeiro `service_role` do Postgres. Isso explica por que o sintoma foi um bloqueio total (0 linhas) em vez de um vazamento parcial de dados: qualquer papel que não seja `service_role` (incluindo `authenticated` rebaixado pelo bug do cliente) não enxerga nenhuma linha de `users`.

## Goals / Non-Goals

**Goals:**
- Login de qualquer usuário nunca deve alterar o privilégio efetivo do cliente `supabase_admin` usado pelo resto do backend.
- `/auth/login` deve continuar retornando o `role` correto e de forma consistente/repetível, independentemente de quantos outros logins tenham ocorrido antes.
- Adicionar uma policy de RLS mínima e correta (`to authenticated using (auth.uid() = id)`) em `public.users`, como defesa em profundidade, seguindo o padrão recomendado pela skill `supabase-postgres-best-practices` (RLS com predicado de posse, não apenas `to authenticated`).

**Non-Goals:**
- Não migrar a lógica de `/auth/login` para reusar `auth_service.AuthService.login` nesta mudança — o fix mínimo e cirúrgico é trocar o cliente usado dentro do handler existente. Consolidar os dois pontos de login (`main.py` inline vs. `auth_service.py`) é uma limpeza técnica separada, fora de escopo aqui.
- Não adicionar policies de INSERT/UPDATE/DELETE em `public.users` para `authenticated` — usuários finais não devem poder alterar seu próprio `role` (isso continua sendo uma operação exclusiva de `service_role`/admin). Apenas SELECT da própria linha.
- Não revisar/consolidar as policies duplicadas encontradas em `public.documents` (`"Enable read for service_role"` vs. `"service_role can read documents"`, etc.) — redundantes mas não incorretas, e não relacionadas a este bug.

## Decisions

1. **Criar um cliente Supabase efêmero (novo `create_client(SUPABASE_URL, SUPABASE_KEY)`), descartável, a cada requisição de `/auth/login`, e usá-lo apenas para `sign_in_with_password`.** Nem `supabase_admin` nem o singleton `supabase_auth` são usados para autenticar o usuário final.
   - **Decisão revista após pergunta do usuário sobre concorrência entre múltiplos logins simultâneos.** A alternativa inicialmente escolhida (reusar o singleton `supabase_auth`) resolve o bug reproduzido, mas deixa um risco latente: `supabase_auth` continua sendo um único cliente compartilhado sujeito ao mesmo `_listen_to_auth_events`; hoje é inofensivo porque nada mais lê dados através dele, mas qualquer código futuro que adicione uma chamada `.table()`/`.storage()` nesse mesmo cliente reintroduziria a mesma classe de bug. Um cliente efêmero por requisição elimina essa possibilidade de vez: não existe nenhum estado de sessão compartilhado relacionado a login, nem hoje nem no futuro.
   - Custo aceito: uma conexão HTTP nova por chamada de login (não há connection pooling reaproveitado entre requisições de login). Irrelevante para um endpoint de baixa frequência relativa como `/auth/login` — não é um hot path chamado por request como `/consultoria/chat` ou os endpoints `/admin/*`.
   - Alternativa considerada: reusar o singleton `supabase_auth` (decisão original). Rejeitada nesta revisão por deixar o risco latente descrito acima.
   - Alternativa considerada: usar `auth_service.AuthService.login` (que já usa `supabase_auth` corretamente) no lugar da lógica inline. Rejeitada (non-goal abaixo) para manter o fix cirúrgico; além disso herdaria o mesmo risco do singleton `supabase_auth` que estamos eliminando aqui.
   - A busca do papel (`_load_public_user_profile`) continua usando `supabase_admin` — precisa do bypass de RLS para ler o perfil de QUALQUER usuário (não só o que acabou de logar), o que é exatamente o caso de uso legítimo de `service_role`. `supabase_admin` nunca é tocado por nenhuma etapa do login.
   - Resposta à pergunta "cada autenticação concorrente mantém seu próprio nível de acesso?": sim — com cliente efêmero por requisição, não existe NENHUM estado mutável compartilhado entre logins simultâneos de usuários diferentes (cada um usa sua própria instância de cliente, descartada ao final da requisição), e `supabase_admin` (usado por todas as outras requisições para calcular o nível de acesso via `get_current_user`/`get_current_admin_user`) nunca é afetado por nenhum login. O nível de acesso de cada usuário é sempre recalculado do zero, a cada requisição, direto do banco.

2. **Adicionar uma migration de RLS em `public.users`**: `create policy "users_select_own" on public.users for select to authenticated using (auth.uid() = id);`
   - Segue o padrão da skill `supabase-postgres-best-practices` (`security-rls-basics.md`): `to authenticated` combinado com predicado de posse (`auth.uid() = id`), não apenas `to authenticated` sozinho (que seria autenticação sem autorização).
   - Aplicada via `apply_migration` (projeto hospedado real, não desenvolvimento local com Supabase CLI) — cria uma entrada de migration versionada e rastreável, ao contrário de `execute_sql` solto.
   - Depois de aplicar, rodar `get_advisors(type="security")` para confirmar que nenhum novo alerta foi introduzido.

## Risks / Trade-offs

- **[Risco] Esquecer de também trocar chamadas futuras de login que alguém adicione usando `supabase_admin`** → Mitigação: a policy de RLS (item 2) é uma defesa em profundidade justamente para esse cenário — mesmo que um bug de cliente compartilhado se repita de outra forma no futuro, a leitura da própria linha em `users` não ficará mais totalmente bloqueada.
- **[Trade-off] Uma conexão HTTP nova por login, em vez de reaproveitar um cliente/pool existente** → aceito deliberadamente: elimina por completo a classe de bug (estado de sessão mutável compartilhado), e o custo de uma conexão extra em um endpoint de login é desprezível.
- **[Risco] A nova policy de SELECT permite que qualquer usuário autenticado veja seu próprio `role`** → aceitável e necessário: um usuário já recebe seu próprio `role` na resposta de `/auth/login`; a policy apenas torna essa mesma informação legível via a Data API também, sem expor linhas de outros usuários.
- **[Trade-off] Não resolvemos a duplicação de responsabilidade entre `main.py`'s `/auth/login` inline e `auth_service.AuthService.login`** — ambos continuam existindo; deixado como dívida técnica registrada, não bloqueia a correção do bug crítico.
