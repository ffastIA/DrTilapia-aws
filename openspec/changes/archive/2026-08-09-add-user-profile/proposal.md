## Why

Hoje o cadastro do usuário se resume a email/senha (`public.users`). Não há como identificar quem é a pessoa por trás da conta, os dados de contato, a empresa/propriedade de criação ou seu porte de produção — informações essenciais para segmentar e atender clientes de piscicultura/carcinicultura na plataforma DrTilápia. É preciso um cadastro de perfil que o usuário preencha e possa manter atualizado a qualquer momento.

## What Changes

- Nova tabela `public.user_profiles`, 1:1 com `public.users` (chave = `user_id`), com um `sequential_id` gerado pelo banco, único por usuário, para servir de código de cadastro legível (ex.: exibição em relatórios/suporte).
- Novos endpoints backend `GET /profile` e `PUT /profile` (upsert) para o usuário autenticado ler e atualizar seu próprio perfil.
- Nova página "Meu Perfil" no frontend (`frontend/app/main/profile/page.tsx`) com formulário completo, dropdowns fechados para "Tipo de criação" (Piscicultura/Carcinicultura) e "Estado" (26 UFs + DF), e campo de produção anual aceitando decimal com 1 casa.
- Validação de campos obrigatórios (nome completo, telefone, email, tipo de criação, produção/ano) tanto no frontend quanto no backend.
- RLS em `user_profiles` seguindo o padrão self-read/self-write já usado em `fish_images`/`fish_analyses`: o próprio usuário só lê e escreve sua própria linha.

Fora do escopo desta change (tratado em `add-profile-onboarding-gate`): redirecionamento automático no primeiro acesso, bloqueio de navegação até preencher os campos obrigatórios, logout ao sair sem completar o cadastro, e substituição do email pelo nome no cabeçalho da página principal.

## Capabilities

### New Capabilities
- `user-profile`: cadastro de perfil do usuário (dados pessoais, empresa, endereço) com identificador sequencial único, editável a qualquer momento via `GET`/`PUT /profile` e a página "Meu Perfil".

### Modified Capabilities
(nenhuma — `user-profile` é uma capability nova; não altera requisitos de `user-signup` nem `users-table-rls-self-read`)

## Impact

- **Banco de dados**: nova tabela `public.user_profiles` + migration, sequence/identity para `sequential_id`, policies de RLS.
- **Backend**: `backend/app/main.py` (novas rotas), novo `backend/app/services/user_profile_service.py`, novos schemas Pydantic (ex. `backend/app/profile_schemas.py`), uso de `get_user_scoped_client` (padrão de `fish_image_service.py`) e `get_current_user`.
- **Frontend**: nova rota `frontend/app/main/profile/`, novo hook de dados (`frontend/hooks/useProfile*.ts`), reutiliza `PageHeader`, `Card`, `Button` existentes.
- **Sem impacto** em `user-signup`, `users-table-rls-self-read` ou fluxo de login/senha — este cadastro é um recurso adicional pós-login.
