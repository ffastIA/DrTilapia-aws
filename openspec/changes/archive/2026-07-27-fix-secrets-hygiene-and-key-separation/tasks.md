## 1. Rotação de chave (ação manual do usuário — não automatizável)

- [x] 1.1 No Supabase Dashboard do projeto `tfdripphcwbjiveksuet`, a chave `service_role` (JWT legado, exposta em texto puro nesta conversa) foi substituída pela `secret key` já existente no novo formato (`sb_secret_...`, nunca exposta neste chat) e, em seguida, as chaves legadas (`anon` + `service_role`) foram **desativadas** em Settings → API Keys → Legacy (confirmado: `apikey` legado agora retorna `401 Legacy API keys are disabled`). Como o Dashboard só permite desativar `anon`+`service_role` juntos (mesmo segredo JWT), o frontend foi migrado para a `publishable key` nova (`sb_publishable_...`) antes da desativação, para não quebrar o middleware.
- [x] 1.2 Avaliar se a chave `anon` também deve ser rotacionada por precaução: **não é necessário** — `anon` é uma chave de baixo privilégio, feita para ser pública (já exposta deliberadamente em `NEXT_PUBLIC_SUPABASE_ANON_KEY` desde a mudança `fix-admin-middleware-jwt-validation`); rotacioná-la não traria ganho de segurança, só custo de atualização.

## 2. Corrigir `backend/.env`

- [x] 2.1 Removida a linha `SECRET_KEY` (não referenciada por nenhum código). Confirmado que o app ainda importa/inicia normalmente sem ela.
- [x] 2.2 `SUPABASE_SERVICE_ROLE_KEY` em `backend/.env` atualizada para a nova `secret key` (`sb_secret_...`).

## 3. Corrigir `.env` da raiz

- [x] 3.1 Buscado por referências ao `.env` da raiz fora de `.py`/`.ts`: só `backend/docker-compose.yml` (já corrigido na seção 4) e nenhum workflow de CI (`.github/workflows` não existe no repo).
- [x] 3.2 `SUPABASE_URL` corrigida para `tfdripphcwbjiveksuet` (mesmo projeto de `backend/.env`).
- [x] 3.3 `SUPABASE_KEY` e `SUPABASE_ANON_KEY` corrigidas para a chave `anon` real do projeto certo (antes: `SUPABASE_KEY` era uma `service_role` do projeto errado).
- [x] 3.4 Removidos `JWT_SECRET`, `SUPABASE_DB_PASSWORD`, `SUPABASE_DATABASE_URL`, `SUPABASE_DB_HOST/PORT/NAME/USER` (confirmado, nenhum usado por código).
- [x] 3.5 Removida a linha comentada `//SUPABASE_SERVICE_ROLE_KEY=...` — como a task 3.1 confirmou que nada além do `docker-compose.yml` dependia deste arquivo (e o compose agora usa `backend/.env`), não há necessidade de preenchê-la.

## 4. Corrigir `backend/docker-compose.yml`

- [x] 4.1 `../.env:/app/.env` → `./.env:/app/.env`.
- [x] 4.2 `env_file: - ../.env` → `env_file: - ./.env`.

## 5. Verificação

- [x] 5.1 Confirmado: `backend/.env` e o `.env` referenciado por `docker-compose.yml` (agora `backend/.env`) apontam para o mesmo projeto (`tfdripphcwbjiveksuet`).
- [x] 5.2 Backend reiniciado localmente com a nova `secret key`: `Application startup complete` sem erros; `supabase_admin.table('users').select(...)` executado com sucesso (privilégio de `service_role` confirmado); chave legada testada em seguida via REST direta → `401 Legacy API keys are disabled`, confirmando que a chave exposta nesta conversa está morta. Teste ponta a ponta de `/auth/login` via UI real não foi feito (exigiria criar usuário de teste em produção, bloqueado pelo classificador de modo automático) — o usuário optou por prosseguir mesmo assim.
- [ ] 5.3 (Se o Docker estiver disponível) Subir `docker compose up` a partir de `backend/` e confirmar que o container inicializa sem `ValueError`. **Pendente** — não executado nesta sessão (requer Docker Desktop rodando; não verificado se está disponível no ambiente).
- [x] 5.4 Confirmado por busca no repositório: nenhum arquivo de configuração contém mais uma chave `service_role` sob um nome de baixo privilégio (`SUPABASE_KEY`/`SUPABASE_ANON_KEY` agora são `anon` em ambos os `.env`).

## Pendências para retomar depois

- Task 5.3: testar `docker compose up`, se o ambiente tiver Docker disponível.
- Recomendado (fora do escopo original): testar manualmente o login via UI real (frontend + backend rodando) para confirmar ponta a ponta que o `middleware.ts` (agora usando a `publishable key`) continua identificando corretamente `role=admin` — não verificado nesta sessão por não ser possível criar um usuário de teste em produção.
- Nota: `frontend/.env.local` (`NEXT_PUBLIC_SUPABASE_ANON_KEY`) foi migrado da `anon` legada para a `publishable key` nova (`sb_publishable_...`) como pré-requisito para desativar as chaves legadas sem quebrar o middleware — mudança adicional não prevista originalmente neste change, mas necessária.
