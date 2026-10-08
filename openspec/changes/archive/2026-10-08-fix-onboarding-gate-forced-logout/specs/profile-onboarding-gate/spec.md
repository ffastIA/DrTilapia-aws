## MODIFIED Requirements

### Requirement: Abandonar o redirecionamento inicial permite acesso normal ao hub
O sistema SHALL permitir acesso normal a qualquer página de `/main/*` a um usuário com perfil incompleto que tente navegar para fora de `/main/profile` depois de já ter recebido o redirecionamento automático de primeiro acesso nesta sessão, SEM encerrar a sessão do usuário.

#### Scenario: Usuário navega para outra página sem completar o cadastro
- **WHEN** um usuário que já foi redirecionado automaticamente para `/main/profile` nesta sessão tenta navegar para outra página de `/main/*` sem ter salvado os campos obrigatórios do perfil
- **THEN** o sistema permite a navegação normalmente (sem redirecionar de volta para `/main/profile` nem encerrar a sessão)

#### Scenario: Botão "Voltar" no cadastro funciona normalmente
- **WHEN** um usuário nessa mesma situação clica no botão "Voltar" da tela `/main/profile`
- **THEN** o sistema navega para a página de destino (ex.: `/main/hub`) sem encerrar a sessão

#### Scenario: Logout normal não deixa estado de gate obsoleto
- **WHEN** um usuário com perfil incompleto que já recebeu o redirecionamento de primeiro acesso nesta sessão faz logout pelo fluxo normal (botão sair, ou expiração de token) e loga novamente
- **THEN** ele recebe um novo redirecionamento automático (silencioso) para `/main/profile` na primeira tentativa de acessar outra página, reiniciando corretamente o ciclo de primeiro acesso (sem herdar o estado de "já visto" da sessão anterior)
