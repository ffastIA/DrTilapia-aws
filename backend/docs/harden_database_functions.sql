-- ============================================================
-- DrTilapIA — Endurecimento de funções do banco (SEC-11)
-- 1) Rode os Security Advisors (Dashboard → Advisors) e confira o resultado.
-- 2) Revise e execute o que se aplicar. Não foi possível verificar o banco real.
-- ============================================================

-- Funções SECURITY DEFINER do schema public não devem ser chamáveis via API:
REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
ALTER FUNCTION public.rls_auto_enable() SET search_path = public, pg_temp;

-- Lista as demais funções SECURITY DEFINER / sem search_path fixo, para revisão:
SELECT n.nspname, p.proname, p.prosecdef AS security_definer, p.proconfig
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND (p.prosecdef OR p.proconfig IS NULL OR NOT EXISTS (
        SELECT 1 FROM unnest(p.proconfig) c WHERE c LIKE 'search_path=%'));
-- Para cada função listada:
--   REVOKE EXECUTE ON FUNCTION public.<nome>(<args>) FROM PUBLIC, anon, authenticated;
--   ALTER FUNCTION public.<nome>(<args>) SET search_path = public, pg_temp;
