## 1. Backend

- [x] 1.1 `backend/app/auth/auth_service.py` (`login`): depois de autenticar, consultar `user_profiles`
      (`select user_id`, filtro por `user_id`, `limit 1`) com `supabase_admin` e incluir `profile_complete`
      no retorno; em qualquer exceção, logar e usar `False` (não impede o login).
- [x] 1.2 `backend/app/main.py`: adicionar `profile_complete: bool = False` a `LoginResponse` e preenchê-lo
      na rota `/auth/login`. Não incluir o campo nas respostas de erro.
- [x] 1.3 Testes em `backend/tests/` (padrão de `test_backend_api.py`): perfil ausente ⇒ `false`;
      perfil presente ⇒ `true`; consulta a `user_profiles` falha ⇒ 200 com `false`; credenciais inválidas ⇒
      erro existente, sem `profile_complete`.

## 2. Frontend

- [x] 2.1 `frontend/app/auth/login/page.tsx`: `window.location.assign` no lugar de `router.push` e remoção de
      `useRouter` (feito, ainda não commitado).
- [x] 2.2 `frontend/app/auth/login/page.tsx`: `prefetch={false}` no `<Link href="/main/hub">` do logo
      (feito, ainda não commitado).
- [x] 2.3 `frontend/hooks/useLoginMutation.ts`: incluir `profile_complete?: boolean` em `LoginResponse`.
- [x] 2.4 `frontend/store/authStore.ts`: helper que grava `profileComplete=1` (`path=/`, `SameSite=lax`,
      `Secure` quando `window.location.protocol === 'https:'`).
- [x] 2.5 `frontend/app/auth/login/page.tsx`: no `onSuccess`, `profile_complete === false` ⇒
      `/main/profile`; caso contrário (verdadeiro ou ausente) ⇒ `/main/hub`; gravar `profileComplete`
      quando verdadeiro; não gravar `profileGateSeen`; manter o atraso de 2 s da mensagem de sucesso.

## 3. Gate obrigatório (opção A: cadastro obrigatório)

- [x] 3.1 `frontend/app/main/layout.tsx`: `prefetch={false}` no link da marca; comentário no `middleware.ts`
      explicando que o Next 14 não permite distinguir prefetch (verificado) e que as telas do cadastro não
      podem pré-carregar `/main/*`.
- [x] 3.2 `frontend/middleware.ts` (regra 3): com `profileGateSeen=1` e cadastro incompleto, em navegação real,
      redirecionar para `/auth/login` expirando `accessToken`, `user`, `profileGateSeen` e `profileComplete`
      (`path=/`, `maxAge=0`); atualizar o comentário que hoje diz "não desloga o usuário".
- [x] 3.3 `frontend/middleware.ts`: logar (sem dados sensíveis) quando `hasCompletedProfile` falhar por erro
      de rede/HTTP, para diferenciar "sem cadastro" de "consulta falhou".
- [x] 3.4 `frontend/components/AuthProvider.tsx`: ao navegar para `/auth/login`, chamar `restoreAuth()`
      (cookies são a fonte da verdade) antes de decidir o redirecionamento a `/main/hub`.

## 4. Verificação e deploy

- [ ] 4.1 `pytest` dos testes novos e da suíte existente de login; `npx tsc --noEmit` em `frontend/`.
      Feito: `tsc` limpo; `tests/test_login_profile_complete.py` (6 testes) passa; gate do middleware
      exercitado com `curl` contra `next dev` + Supabase falso (1ª tentativa, 2ª tentativa/logout, cadastro
      acessível, `profileComplete`). Pendente: os 3 testes novos de endpoint em `tests/test_backend_api.py`
      não rodaram localmente (falta `slowapi` no Python local); rodar onde as dependências do backend estão
      instaladas.
- [ ] 4.2 Rebuild do backend **e** do frontend (`.\deploy\build-and-push.ps1 -Platform arm64 -Builder
      desktop-linux`, um alvo por vez) e `docker pull` + recriação dos containers nas duas EC2.
- [ ] 4.3 Validar em produção (CloudFront, janela anônima): conta nova ⇒ login cai direto em
      `/main/profile`; salvar o cadastro ⇒ `/main/hub`; conta com cadastro completo ⇒ login cai em
      `/main/hub`; ao abrir `/auth/login` não há requisição a `/main/hub`; `POST /api-proxy/auth/login`
      devolve `profile_complete`.
- [ ] 4.4 Validar o gate obrigatório em produção, com conta nova: login → `/main/profile`; abrir `/main/hub`
      → volta a `/main/profile`; abrir `/main/hub` de novo → cai em `/auth/login` já deslogado e sem loop;
      conferir em Application → Cookies que os 4 cookies foram removidos; abrir `/main/profile` não
      dispara deslogamento por prefetch.
