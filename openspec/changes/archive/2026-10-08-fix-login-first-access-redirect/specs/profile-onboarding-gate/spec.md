## ADDED Requirements

### Requirement: Login encaminha o primeiro acesso diretamente ao cadastro
O sistema SHALL, ao concluir um login bem-sucedido, encaminhar o usuário que ainda não tem perfil
(nenhuma linha em `user_profiles`) diretamente para `/main/profile`, e SHALL encaminhar para `/main/hub`
somente o usuário que já completou o cadastro.

#### Scenario: Primeiro acesso vai direto ao cadastro
- **WHEN** um usuário sem linha em `user_profiles` faz login com sucesso
- **THEN** o sistema o leva para `/main/profile` sem passar por `/main/hub`

#### Scenario: Usuário com cadastro completo vai ao hub
- **WHEN** um usuário com linha em `user_profiles` faz login com sucesso
- **THEN** o sistema o leva para `/main/hub`

#### Scenario: Não foi possível determinar o estado do cadastro
- **WHEN** o login tem sucesso mas a resposta não informa se o cadastro está completo
- **THEN** o sistema o leva para `/main/hub` e o gate existente do middleware decide se o redireciona ao cadastro

#### Scenario: Login de usuário com cadastro completo dispensa a consulta do middleware
- **WHEN** um usuário com cadastro completo faz login com sucesso
- **THEN** o cookie `profileComplete=1` é gravado com o atributo `Secure` quando a página é servida por HTTPS, e o middleware não consulta o cadastro na primeira navegação ao hub

#### Scenario: Login de primeiro acesso não consome o redirecionamento único do gate
- **WHEN** um usuário sem cadastro é encaminhado a `/main/profile` pelo login
- **THEN** o cookie `profileGateSeen` não é gravado, e o gate do middleware se comporta nas navegações seguintes como se o usuário ainda não tivesse sido redirecionado

### Requirement: Backend informa se o cadastro está completo no login
`POST /auth/login` SHALL incluir no corpo da resposta de sucesso o campo booleano `profile_complete`,
verdadeiro se e somente se existe linha em `user_profiles` para o `user_id` autenticado. A consulta SHALL
ser feita no backend e uma falha na consulta SHALL NOT impedir o login: o campo assume `false` e o erro é
registrado no log.

#### Scenario: Conta recém-criada
- **WHEN** `POST /auth/login` é chamado por um usuário sem linha em `user_profiles`
- **THEN** a resposta tem status 200 e `profile_complete: false`

#### Scenario: Conta com cadastro salvo
- **WHEN** `POST /auth/login` é chamado por um usuário com linha em `user_profiles`
- **THEN** a resposta tem status 200 e `profile_complete: true`

#### Scenario: Falha ao consultar o cadastro
- **WHEN** a consulta a `user_profiles` falha durante o login
- **THEN** o login ainda retorna 200 com `profile_complete: false` e o erro é registrado no log

#### Scenario: Credenciais inválidas não revelam o estado do cadastro
- **WHEN** `POST /auth/login` é chamado com credenciais inválidas
- **THEN** a resposta é o erro de autenticação existente e não contém `profile_complete`

### Requirement: Telas acessíveis a quem tem cadastro incompleto não disparam prefetch de rotas protegidas
O sistema SHALL NOT disparar prefetch de rotas de `/main/*` a partir das telas que um usuário com cadastro
incompleto enxerga (`/main/profile` e o layout compartilhado `app/main/layout.tsx`): os links dessas telas
para outras rotas de `/main/*` usam `prefetch={false}`, de modo que um prefetch não consuma o
redirecionamento único nem deslogue o usuário sem ele ter navegado. Isso é necessário porque o middleware
do Next.js 14 não consegue distinguir uma requisição de prefetch de uma navegação real (o framework remove
os cabeçalhos `RSC` e `Next-Router-Prefetch` antes de chamá-lo), então toda requisição de `/main/*` recebida
do gate é tratada como tentativa real do usuário.

#### Scenario: Abrir o cadastro não consome o redirecionamento único
- **WHEN** um usuário com cadastro incompleto permanece em `/main/profile`, sem clicar em nenhum link
- **THEN** o navegador não solicita nenhuma outra rota de `/main/*`, o cookie `profileGateSeen` não é gravado e o usuário não é deslogado

#### Scenario: O link da marca no layout não é pré-carregado
- **WHEN** o layout de `/main/*` é exibido a um usuário com cadastro incompleto
- **THEN** o link da marca (`/main/hub`) não dispara prefetch

### Requirement: O logout por abandono encerra a sessão por completo
Quando o gate deslogar um usuário por abandono do cadastro, o middleware SHALL redirecionar para
`/auth/login` e expirar, na mesma resposta, os cookies `accessToken`, `user`, `profileGateSeen` e
`profileComplete`. O frontend SHALL tratar os cookies como a fonte da verdade da sessão: ao navegar para
`/auth/login`, `AuthProvider` SHALL ressincronizar o estado em memória com os cookies, de modo que um usuário
deslogado pelo middleware não seja redirecionado de volta a `/main/hub`.

#### Scenario: Segunda tentativa de sair do cadastro desloga o usuário
- **WHEN** um usuário com cadastro incompleto, que já recebeu o redirecionamento automático nesta sessão, navega de fato para outra página de `/main/*`
- **THEN** o middleware o redireciona para `/auth/login` e os cookies `accessToken`, `user`, `profileGateSeen` e `profileComplete` são expirados

#### Scenario: Usuário deslogado por abandono permanece na tela de login
- **WHEN** o usuário é levado a `/auth/login` pelo logout por abandono
- **THEN** o estado de autenticação em memória fica limpo e a tela de login é exibida, sem redirecionamento de volta a `/main/hub`

#### Scenario: Primeiro acesso encaminhado pelo login ainda tem um aviso antes do logout
- **WHEN** um usuário sem cadastro é levado a `/main/profile` pelo login e tenta abrir `/main/hub`
- **THEN** na primeira tentativa o middleware o devolve a `/main/profile` (e grava `profileGateSeen`), e só uma segunda tentativa real o desloga
