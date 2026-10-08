## Why

**Aviso de escopo, importante:** este item (M2 da auditoria, `docs/auditoria-fullstack.md`) descreve achados dos *advisors* de segurança do Supabase — estado ao vivo do banco, não código deste repositório. Nesta sessão, confirmamos por leitura direta de código que os itens C1–C5 (críticos) do mesmo relatório já estavam corrigidos, apesar de o relatório os listar como abertos — ou seja, o relatório está parcialmente desatualizado. Como não há acesso a uma ferramenta de advisors/CLI do Supabase neste ambiente para reverificar M2 ao vivo, **esta proposta assume que os achados abaixo ainda procedem, mas isso deve ser confirmado (via `supabase` MCP/dashboard/CLI, rodando os advisors de segurança novamente) antes de aplicar qualquer correção.**

Achados reportados (não reverificados nesta sessão):
- `public.rls_auto_enable()` é `SECURITY DEFINER` e executável via RPC (`/rest/v1/rpc/rls_auto_enable`) por `anon`/`authenticated` — uma função que roda com privilégios do dono, chamável por qualquer usuário autenticado ou anônimo.
- `insert_vector_batch` e `rpc_vector_search` (funções usadas pelo pipeline RAG) não têm `SET search_path` fixado, o que as expõe a um ataque de *search_path hijacking* caso um schema malicioso seja injetável na sessão.
- A extensão `vector` (pgvector) está instalada no schema `public` em vez de um schema dedicado.
- A proteção contra senhas vazadas (checagem via HaveIBeenPwned) está desabilitada nas configurações de Auth do projeto Supabase.

## What Changes

- `REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon, authenticated;` (manter executável apenas pelo `service_role`/dono, se ainda for necessária como RPC; caso não seja mais invocada via API, avaliar removê-la do schema RPC público inteiramente).
- Adicionar `SET search_path = public, pg_temp` (ou lista mínima equivalente) a `insert_vector_batch` e `rpc_vector_search`.
- Avaliar mover a extensão `vector` do schema `public` para um schema dedicado (ex.: `extensions`) — passo mais arriscado, que pode exigir recriar índices/tipos dependentes; tratar como tarefa separada com plano de rollback, não bloquear os itens acima.
- Habilitar a proteção de senha vazada (HaveIBeenPwned) nas configurações de Auth do projeto Supabase (mudança de configuração, não SQL).

## Capabilities

### New Capabilities
- `supabase-function-hardening`: as funções Postgres expostas via RPC do Supabase seguem o princípio de menor privilégio (sem `SECURITY DEFINER` executável por papéis não autorizados, `search_path` fixado) e a proteção de senha vazada está habilitada.

## Impact

- **Código afetado**: nenhum arquivo do repositório de aplicação — mudanças são migrações SQL no banco Supabase e configuração do painel de Auth.
- **Onde aplicar**: via migration SQL versionada (se o projeto usa alguma pasta de migrations do Supabase) ou diretamente pelo SQL editor do dashboard, documentando o script aplicado.
- **Pré-requisito**: reverificar os achados ao vivo antes de aplicar (ver seção "Why").
