# profile-onboarding-gate Specification

## Purpose
TBD - created by syncing change add-profile-onboarding-gate. Update Purpose after archive.
## Requirements
### Requirement: Primeiro acesso com perfil incompleto redireciona automaticamente ao cadastro
O sistema SHALL redirecionar, de forma automática e sem deslogar, um usuário autenticado com perfil incompleto que tente acessar qualquer página de `/main/*` diferente de `/main/profile`, na primeira vez que isso ocorrer na sessão.

#### Scenario: Usuário recém-logado tenta acessar a página principal sem perfil
- **WHEN** um usuário autenticado sem nenhuma linha em `user_profiles` navega para `/main/hub` (ou qualquer outra página de `/main/*` exceto `/main/profile`) pela primeira vez nesta sessão
- **THEN** o sistema o redireciona para `/main/profile` sem encerrar a sessão

#### Scenario: Usuário com perfil incompleto pode acessar a própria página de cadastro livremente
- **WHEN** um usuário autenticado com perfil incompleto navega para `/main/profile`
- **THEN** o sistema exibe a página normalmente, sem redirecionar nem deslogar

### Requirement: Abandonar o cadastro após o redirecionamento inicial encerra a sessão
O sistema SHALL deslogar (encerrar a sessão e redirecionar para a tela de login) um usuário com perfil incompleto que tente novamente acessar qualquer página de `/main/*` diferente de `/main/profile` depois de já ter recebido o redirecionamento automático nesta sessão.

#### Scenario: Usuário tenta sair da tela de cadastro sem completar os obrigatórios
- **WHEN** um usuário que já foi redirecionado automaticamente para `/main/profile` nesta sessão tenta navegar para outra página de `/main/*` sem ter salvado os campos obrigatórios do perfil
- **THEN** o sistema encerra a sessão do usuário (remove os dados de autenticação) e o redireciona para a tela de login

#### Scenario: Usuário deslogado por abandono precisa logar novamente para tentar de novo
- **WHEN** um usuário deslogado por abandono do cadastro faz login novamente
- **THEN** ele recebe um novo redirecionamento automático (silencioso) para `/main/profile` na primeira tentativa de acessar outra página, reiniciando o ciclo descrito nestes requisitos

### Requirement: Completar o cadastro libera o acesso e retorna à tela principal
O sistema SHALL permitir acesso irrestrito a `/main/*` assim que o perfil do usuário tiver os campos obrigatórios preenchidos, e SHALL redirecionar o usuário para a tela principal imediatamente após o primeiro salvamento bem-sucedido do cadastro.

#### Scenario: Salvamento bem-sucedido do primeiro cadastro
- **WHEN** um usuário com perfil incompleto preenche os campos obrigatórios em `/main/profile` e salva com sucesso
- **THEN** o sistema o redireciona para `/main/hub`

#### Scenario: Navegação livre após completar o cadastro
- **WHEN** um usuário cujo perfil já tem os campos obrigatórios preenchidos navega para qualquer página de `/main/*`
- **THEN** o sistema não redireciona nem desloga, permitindo acesso normal

### Requirement: Página principal exibe o nome do perfil no lugar do email
Assim que o perfil do usuário tiver o nome completo preenchido, a página principal (`/main/hub`) SHALL exibir esse nome na saudação em vez do email; enquanto o nome não estiver disponível, a saudação SHALL continuar exibindo o email como ocorre hoje.

#### Scenario: Perfil com nome preenchido
- **WHEN** um usuário cujo perfil tem `full_name` preenchido acessa `/main/hub`
- **THEN** a saudação exibe o nome completo do usuário, não o email

#### Scenario: Perfil sem nome preenchido ainda
- **WHEN** um usuário cujo perfil ainda não tem `full_name` (ou não tem perfil algum) acessa `/main/hub`
- **THEN** a saudação continua exibindo o email do usuário, como comportamento atual
