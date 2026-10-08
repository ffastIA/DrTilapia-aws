## 0. Reverificação (obrigatória antes de qualquer alteração)

- [x] 0.1 Rodar os advisors de segurança do Supabase novamente (dashboard ou CLI/MCP) e confirmar quais dos quatro achados abaixo ainda procedem no projeto atual. Reverificado em 2026-09-14 via MCP `get_advisors` + consulta direta a `pg_proc`: `rls_auto_enable` (SECURITY DEFINER executável por `anon`/`authenticated`), extensão `vector` em `public` e proteção de senha vazada desabilitada **ainda procedem**. `insert_vector_batch` e `rpc_vector_search` **já tinham `search_path=public` fixado** (a suposição original desta proposta estava errada). Em vez disso, uma função criada depois da auditoria original — `set_user_profiles_updated_at` (trigger de `updated_at` em `user_profiles`, migration `20260809185314`) — apareceu com `search_path` mutável (`proconfig` nulo) e precisou do mesmo tratamento.
- [x] 0.2 `grep -rn "rls_auto_enable"` em `backend/` e `frontend/` — confirmar se a função ainda é invocada por algum caminho da aplicação antes de revogar seu acesso. Confirmado: zero ocorrências em `backend/`/`frontend/`; só aparece em `openspec/` e `docs/auditoria-fullstack.md`. Seguro revogar.

## 1. Revogar execução desnecessária

- [x] 1.1 Se `rls_auto_enable()` não for mais invocada via RPC pública pela aplicação: `REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon, authenticated;` Aplicado, mas **não teve efeito na primeira tentativa**: o `EXECUTE` estava concedido via o grant implícito de `PUBLIC` (`proacl` continha `=X/postgres`), que `anon`/`authenticated` herdam mesmo sem grant direto — revogar desses dois papéis especificamente é um no-op quando o grant é via `PUBLIC`. Corrigido com `REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC;`. Verificado com `has_function_privilege(...)`: `anon`/`authenticated` → `false`; `service_role` → `true` (continua utilizável internamente).

## 2. Fixar search_path

- [x] 2.1 `insert_vector_batch(jsonb)` — reverificado: já tinha `proconfig = {search_path=public}` antes desta mudança. Nenhuma ação necessária.
- [x] 2.2 `rpc_vector_search(jsonb, integer)` — reverificado: já tinha `proconfig = {search_path=public}` antes desta mudança. Nenhuma ação necessária.
- [x] 2.3 (achado novo, fora do escopo original) `ALTER FUNCTION public.set_user_profiles_updated_at() SET search_path = public, pg_temp;` — aplicado. Confirmado via `pg_proc` que `proconfig` deixou de ser nulo.

## 3. Auth — proteção de senha vazada

- [ ] 3.1 Habilitar a checagem de senha vazada (HaveIBeenPwned) nas configurações de Auth do projeto Supabase (dashboard, sem SQL). **Não aplicado nesta sessão** — não há ferramenta MCP que exponha essa configuração; requer acesso manual ao dashboard (Authentication → Sign In / Providers → Password → "Leaked password protection").

## 4. Avaliação separada (não bloqueante)

- [x] 4.1 Avaliar o esforço/risco de mover a extensão `vector` do schema `public` para um schema dedicado — registrar decisão (fazer agora, adiar, ou não fazer) com a justificativa. **Decisão: adiar.** Mover exigiria recriar os índices HNSW (`documents_embedding_hnsw_idx`) e possivelmente outros tipos/colunas dependentes do tipo `vector`; risco desproporcional ao benefício (o achado é nível WARN, não CRÍTICO) para este lote de correções.

## 5. Verificação

- [x] 5.1 Rodar os advisors de segurança do Supabase uma última vez após as mudanças — confirmar que os itens tratados não aparecem mais. Uma primeira chamada a `get_advisors` foi bloqueada pelo classificador de permissões do Claude Code (auto mode) logo após os writes; verificado nesse intervalo via consulta direta (`has_function_privilege`, `pg_proc`). Uma segunda chamada a `get_advisors` (security) teve sucesso e confirmou: `anon_security_definer_function_executable`/`authenticated_security_definer_function_executable` (`rls_auto_enable`) e `function_search_path_mutable` (`set_user_profiles_updated_at`) **não aparecem mais**. Restam apenas `extension_in_public` (item 4.1, adiado) e `auth_leaked_password_protection` (item 3.1, manual/dashboard).
- [x] 5.2 Testar o pipeline RAG (ingestão + busca) end-to-end após o `ALTER FUNCTION` nas duas funções — confirmar que `search_path` fixado não quebrou nenhuma referência não qualificada dentro das funções. `insert_vector_batch`/`rpc_vector_search` não foram alteradas nesta sessão (já estavam corretas) — nada a testar ali. A única `ALTER FUNCTION` real foi em `set_user_profiles_updated_at`; inspecionado via `pg_get_functiondef`: o corpo só referencia `NEW.updated_at`/`NOW()` (sem nenhuma tabela/schema não qualificado), portanto `search_path = public, pg_temp` não pode quebrar nada nela — verificação por inspeção, sem necessidade de um `UPDATE` real em dados de produção.
