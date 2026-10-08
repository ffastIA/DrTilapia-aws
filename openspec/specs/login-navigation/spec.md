# login-navigation Specification

## Purpose
TBD - created by archiving change fix-login-first-access-redirect. Update Purpose after archive.
## Requirements
### Requirement: A navegação pós-login não reutiliza respostas de rota geradas antes de autenticar
Depois de um login bem-sucedido, o frontend SHALL navegar para o destino por navegação completa de página
(`window.location.assign`), e NÃO por navegação client-side do Next.js (`router.push`), de modo que nenhuma
resposta de rota guardada no Router Cache antes do login (por exemplo, um redirecionamento do middleware
para `/auth/login`) seja reutilizada.

#### Scenario: Redirecionamento guardado antes do login não é reaproveitado
- **WHEN** a tela de login foi aberta sem cookie e, depois, o usuário faz login com sucesso
- **THEN** o destino é carregado do servidor com o cookie `accessToken` presente e o usuário não volta a `/auth/login`

#### Scenario: Mensagem de sucesso antes do redirecionamento
- **WHEN** o login tem sucesso
- **THEN** a tela exibe "Login realizado com sucesso! Redirecionando..." e, em seguida, carrega o destino sem permanecer indefinidamente nessa mensagem

### Requirement: Telas de autenticação não fazem prefetch de rotas protegidas
Páginas em `/auth/*` SHALL NOT disparar prefetch de rotas de `/main/*` enquanto o usuário está deslogado;
links para `/main/*` nessas páginas SHALL usar `prefetch={false}`.

#### Scenario: Abrir a tela de login não gera requisição a /main/*
- **WHEN** um visitante deslogado abre `/auth/login`
- **THEN** o navegador não solicita `/main/hub` (nem outra rota de `/main/*`) em segundo plano

