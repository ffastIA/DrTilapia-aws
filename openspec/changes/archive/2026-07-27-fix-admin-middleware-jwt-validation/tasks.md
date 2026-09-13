## 1. Expor configuração pública necessária

- [x] 1.1 `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` adicionadas a `frontend/.env.local` (mesmo projeto/anon key já usados pelo backend).
- [x] 1.2 `frontend/.env.example` criado, documentando as duas variáveis.

## 2. Corrigir o middleware

- [x] 2.1 `frontend/middleware.ts`: Regra 3 agora faz `fetch` a `${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/users?select=role` com `Authorization: Bearer <token>` e `apikey: <anon key>`, em vez de ler o cookie `user`.
- [x] 2.2 Resposta tratada: não-200, array vazio, ou `role !== 'admin'` → redireciona para `/main/hub`. Erros de rede/parsing também redirecionam (fail-closed).
- [x] 2.3 `middleware` agora é `async function`, usa `await fetch(...)`.

## 3. Verificação

- [x] 3.1 Rodei o frontend (`npm run dev`) e o backend reais; login como admin de teste real; `curl` com o cookie `accessToken` real em `/main/admin` → **HTTP 200**, sem redirect.
- [x] 3.2 Login como usuário comum de teste; mesmo teste → **HTTP 307** redirecionando para `/main/hub`.
- [x] 3.3 **Teste crítico**: token real de usuário comum + cookie `user` forjado (`{"role":"admin"}`) em `/main/admin` → continua **HTTP 307** para `/main/hub`. O cookie forjado não tem mais nenhum efeito (o middleware nem o lê mais).
- [x] 3.4 Decodificado o JWT usado em `NEXT_PUBLIC_SUPABASE_ANON_KEY`: `{"role": "anon", ...}` — confirmado que é a chave pública `anon`, nunca `service_role`.
- Usuários de teste temporários removidos ao final.
