## ADDED Requirements

### Requirement: A marca do app é sempre um link para o hub principal
Em qualquer página onde a marca "Dr. Tilap-IA" (ícone + texto) for exibida ao lado do favicon/ícone do app, ela SHALL ser um elemento navegável que leva o usuário para `/main/hub`.

#### Scenario: Clique na marca em página autenticada
- **WHEN** um usuário autenticado clica na marca "Dr. Tilap-IA" em qualquer página
- **THEN** o sistema navega para `/main/hub`

#### Scenario: Clique na marca em página pública/de autenticação
- **WHEN** um usuário não autenticado clica na marca "Dr. Tilap-IA" na landing page ou em qualquer página de `/auth/*`
- **THEN** o sistema tenta navegar para `/main/hub`, que por sua vez redireciona para `/auth/login` (comportamento existente do middleware para rotas protegidas sem sessão)
