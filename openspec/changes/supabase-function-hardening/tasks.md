## 0. Reverificação (obrigatória antes de qualquer alteração)

- [ ] 0.1 Rodar os advisors de segurança do Supabase novamente (dashboard ou CLI/MCP) e confirmar quais dos quatro achados abaixo ainda procedem no projeto atual.
- [ ] 0.2 `grep -rn "rls_auto_enable"` em `backend/` e `frontend/` — confirmar se a função ainda é invocada por algum caminho da aplicação antes de revogar seu acesso.

## 1. Revogar execução desnecessária

- [ ] 1.1 Se `rls_auto_enable()` não for mais invocada via RPC pública pela aplicação: `REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon, authenticated;`

## 2. Fixar search_path

- [ ] 2.1 `ALTER FUNCTION public.insert_vector_batch(...) SET search_path = public, pg_temp;` (ajustar a assinatura exata da função).
- [ ] 2.2 `ALTER FUNCTION public.rpc_vector_search(...) SET search_path = public, pg_temp;` (ajustar a assinatura exata da função).

## 3. Auth — proteção de senha vazada

- [ ] 3.1 Habilitar a checagem de senha vazada (HaveIBeenPwned) nas configurações de Auth do projeto Supabase (dashboard, sem SQL).

## 4. Avaliação separada (não bloqueante)

- [ ] 4.1 Avaliar o esforço/risco de mover a extensão `vector` do schema `public` para um schema dedicado — registrar decisão (fazer agora, adiar, ou não fazer) com a justificativa.

## 5. Verificação

- [ ] 5.1 Rodar os advisors de segurança do Supabase uma última vez após as mudanças — confirmar que os itens tratados não aparecem mais.
- [ ] 5.2 Testar o pipeline RAG (ingestão + busca) end-to-end após o `ALTER FUNCTION` nas duas funções — confirmar que `search_path` fixado não quebrou nenhuma referência não qualificada dentro das funções.
