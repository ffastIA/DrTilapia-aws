## 1. Banco de dados

- [x] 1.1 Criar `backend/docs/setup_user_profiles.sql` com a tabela `user_profiles` (colunas conforme design.md), `sequential_id GENERATED ALWAYS AS IDENTITY UNIQUE`, `CHECK` de `farming_type`, `CHECK` de `address_state` (26 UFs + DF), `CHECK` de `annual_production_tons >= 0`
- [x] 1.2 Adicionar RLS (`ENABLE ROW LEVEL SECURITY`) e policies `select_own`/`insert_own`/`update_own` (sem `delete`), seguindo o padrão de `setup_fish_images.sql`
- [x] 1.3 Adicionar `GRANT` para `service_role` (ALL) e `authenticated` (SELECT, INSERT, UPDATE)
- [x] 1.4 Adicionar trigger `BEFORE UPDATE` para atualizar `updated_at = NOW()`
- [x] 1.5 Aplicar o script no Supabase (SQL Editor) e confirmar que a tabela, policies e grants existem

## 2. Backend — schemas e serviço

- [x] 2.1 Criar `backend/app/profile_schemas.py` com `ProfileUpsertRequest` (Pydantic — obrigatórios: `full_name`, `phone`, `farming_type` (`Literal["piscicultura","carcinicultura"]`), `annual_production_tons` (decimal, 1 casa, `ge=0`); demais campos opcionais) e `ProfileResponse` (inclui `sequential_id`, `email` refletido de `users`)
- [x] 2.2 Validar `annual_production_tons` com no máximo 1 casa decimal (validator Pydantic) e `address_state` contra a lista fechada de UF/DF
- [x] 2.3 Criar `backend/app/services/user_profile_service.py` com `get_profile(user_id, access_token)` e `upsert_profile(user_id, access_token, data)`, usando `get_user_scoped_client` (nunca `supabase_admin` para dados do usuário), seguindo o padrão de `fish_image_service.py`
- [x] 2.4 `get_profile` deve buscar o email atual de `users.email` (via cliente escopado) e combinar com a linha de `user_profiles` (ou retornar perfil vazio + email, se ainda não houver linha)

## 3. Backend — rotas

- [x] 3.1 Adicionar `GET /profile` em `backend/app/main.py`, usando `Depends(get_current_user)`, retornando `ProfileResponse`
- [x] 3.2 Adicionar `PUT /profile` em `backend/app/main.py`, usando `Depends(get_current_user)`, chamando `upsert_profile`, retornando `ProfileResponse` atualizado
- [x] 3.3 Tratar erro de validação do Postgres (`CHECK` constraint) como HTTP 422 com mensagem clara, além da validação Pydantic de entrada
- [x] 3.4 Testar manualmente os dois endpoints (perfil inexistente, criação, edição, tentativa sem obrigatórios, tentativa com `farming_type`/`address_state` inválidos)

## 4. Frontend — tipos e hook de dados

- [x] 4.1 Criar `frontend/types/profile.ts` com a interface `UserProfile` (todos os campos do design.md) e o enum/union de `farming_type` e de UFs
- [x] 4.2 Criar `frontend/hooks/useProfile.ts` (buscar perfil, `GET /profile`) e `frontend/hooks/useUpdateProfileMutation.ts` (salvar, `PUT /profile`), seguindo o padrão de `useSignupMutation.ts` (estados `isPending`/`isError`/`isSuccess`, normalização de erro do backend)

## 5. Frontend — página "Meu Perfil"

- [x] 5.1 Criar `frontend/app/main/profile/page.tsx`: `PageHeader` com título "Meu Perfil", formulário dividido em seções (Dados pessoais, Empresa, Endereço)
- [x] 5.2 Campos obrigatórios com indicação visual (ex. asterisco) e validação client-side antes do submit: nome completo, telefone, tipo de criação, produção/ano
- [x] 5.3 Campo email: exibido a partir de `useProfile`, input desabilitado/somente leitura com nota explicando que é o email de login
- [x] 5.4 Dropdown "Tipo de criação" com as duas opções fixas (Piscicultura / Carcinicultura)
- [x] 5.5 Campo "Produção em toneladas/ano": input numérico que aceita decimal com exatamente 1 casa (validação/mascaramento client-side)
- [x] 5.6 Dropdown "Estado" com as 26 UFs + DF (lista estática no frontend)
- [x] 5.7 Demais campos (instagram, linkedin, empresa, CNPJ, cargo, área de lâmina d'água, nº de tanques, espécie predominante, site, endereço) como opcionais, sem bloquear o submit
- [x] 5.8 Ao carregar a página, popular o formulário com `useProfile` se já existir perfil; exibir estado de carregamento
- [x] 5.9 Ao salvar com sucesso, exibir confirmação (toast/mensagem) e manter o usuário na própria página (edição livre, sem redirecionamento forçado nesta change)
- [x] 5.10 Adicionar link/atalho para "Meu Perfil" na navegação principal existente (ex. menu/hub), para o usuário conseguir acessá-la e editar quando quiser — já existia em `frontend/app/main/hub/page.tsx`

## 6. Verificação

- [x] 6.1 Rodar backend e frontend localmente; criar perfil de um usuário de teste preenchendo só os obrigatórios; confirmar leitura/edição subsequente — testado via navegador real (login como ffasti01@gmail.com), salvamento e reload de página confirmados
- [x] 6.2 Confirmar via Supabase que dois usuários distintos recebem `sequential_id` diferentes e crescentes, e que um usuário não consegue ler/gravar o perfil de outro (testar com dois tokens)
- [x] 6.3 Confirmar que valores de produção com 2+ casas decimais e UF fora da lista são rejeitados com HTTP 422 tanto direto na API quanto pelo formulário — API testada via curl; formulário bloqueia client-side antes mesmo de chamar a API
