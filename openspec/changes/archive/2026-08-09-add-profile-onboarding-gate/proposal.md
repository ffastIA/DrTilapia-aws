## Why

A change `add-user-profile` cria o cadastro de perfil ("Meu Perfil"), mas por si só não obriga ninguém a preenchê-lo — um usuário pode logar e nunca passar por lá. Para que os dados de contato/produção realmente existam para a base de usuários, o preenchimento dos campos obrigatórios precisa ser forçado no primeiro acesso, e abandonar essa etapa sem completá-la não pode deixar o usuário "meio dentro" do sistema.

**Depende de** `add-user-profile` (deve ser aplicada antes ou junto): usa a tabela `user_profiles`, o endpoint `GET/PUT /profile` e a página `/main/profile` criados lá.

## What Changes

- Middleware do frontend (`frontend/middleware.ts`) passa a verificar, em toda navegação para `/main/*` (exceto `/main/profile`), se o usuário autenticado já tem uma linha em `user_profiles` (perfil completo — os campos obrigatórios são `NOT NULL` no banco, então a existência da linha já garante que estão preenchidos).
- **Primeiro acesso / perfil incompleto**: a primeira tentativa de navegar para qualquer página de `/main/*` que não seja `/main/profile` é silenciosamente redirecionada para `/main/profile`, sem logout.
- **Abandono do cadastro**: se, depois desse primeiro redirecionamento, o usuário tentar novamente sair de `/main/profile` sem ter completado o cadastro, o sistema o desloga (limpa a sessão) e o envia para `/auth/login`, em vez de apenas redirecioná-lo de novo. **BREAKING** (comportamento novo e mais restritivo para contas com perfil incompleto — usuários existentes sem perfil cadastrado passam a ser forçados a completá-lo).
- Ao salvar o cadastro com sucesso pela primeira vez (via `PUT /profile`), o frontend redireciona automaticamente para `/main/hub` (tela principal).
- Na página principal (`/main/hub`), a saudação que hoje exibe o email (`Bem-vindo, {user?.email}!`) passa a exibir o nome completo do perfil quando disponível, mantendo o email como fallback.

## Capabilities

### New Capabilities
- `profile-onboarding-gate`: exigência de perfil completo para acessar a área autenticada além da própria página de perfil, incluindo o comportamento de redirecionamento no primeiro acesso e logout ao abandonar o cadastro.

### Modified Capabilities
(nenhuma spec existente de `openspec/specs/` tem requisitos alterados; a capability `user-profile` da change `add-user-profile` ainda não foi arquivada, então esta change consome seu contrato de API sem modificá-lo)

## Impact

- **Frontend**: `frontend/middleware.ts` (nova regra de verificação de perfil + cookies auxiliares de estado), `frontend/app/main/hub/page.tsx` (saudação com nome), `frontend/store/authStore.ts` / `frontend/types/auth.ts` (campo `name` no usuário em sessão), página `frontend/app/main/profile/page.tsx` (redirecionamento pós-salvamento) — todos criados/alterados por `add-user-profile` ou por esta change.
- **Backend**: nenhuma rota nova; reutiliza `GET/PUT /profile` de `add-user-profile`. Nenhuma alteração em `user-signup` ou no fluxo de login/senha.
- **Sem impacto em dados**: não cria tabelas novas; usa a existência de linha em `user_profiles` como sinal de completude.
