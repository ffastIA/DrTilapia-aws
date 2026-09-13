# user-profile Specification

## Purpose
TBD - created by syncing change add-user-profile. Update Purpose after archive.
## Requirements
### Requirement: Perfil do usuário existe 1:1 com a conta e tem identificador sequencial próprio
O sistema SHALL manter uma linha de perfil (`user_profiles`) por usuário, associada por `user_id` (chave primária, igual a `auth.uid()`), e SHALL atribuir a cada linha um `sequential_id` numérico gerado pelo banco, único e distinto do `id`/`user_id` (uuid), no momento em que o perfil é criado pela primeira vez.

#### Scenario: Sequential_id é atribuído na criação do perfil
- **WHEN** um usuário salva seu perfil pela primeira vez via `PUT /profile`
- **THEN** o sistema cria a linha em `user_profiles` com um `sequential_id` inteiro gerado automaticamente pelo banco, exclusivo daquele usuário e nunca reutilizado por outro

#### Scenario: Sequential_id é estável entre edições
- **WHEN** um usuário atualiza seu perfil existente via `PUT /profile`
- **THEN** o `sequential_id` da sua linha permanece inalterado

### Requirement: Usuário autenticado pode ler seu próprio perfil
O sistema SHALL expor `GET /profile`, retornando o perfil do usuário autenticado (incluindo o email de login, refletido de `users.email`) ou um indicador de perfil inexistente quando o usuário ainda não cadastrou nenhum dado.

#### Scenario: Usuário com perfil já cadastrado
- **WHEN** um usuário autenticado chama `GET /profile`
- **THEN** o sistema retorna HTTP 200 com todos os campos do seu perfil e o email da conta

#### Scenario: Usuário sem perfil cadastrado ainda
- **WHEN** um usuário autenticado que nunca salvou um perfil chama `GET /profile`
- **THEN** o sistema retorna HTTP 200 com um corpo indicando ausência de perfil (campos nulos/vazios), sem erro

#### Scenario: Usuário não pode ler perfil de outra conta
- **WHEN** qualquer requisição tenta ler dados de perfil de um `user_id` diferente do usuário autenticado no token
- **THEN** o sistema não retorna nenhuma linha de outro usuário (aplicado via RLS, independentemente do endpoint chamado)

### Requirement: Usuário autenticado pode criar ou atualizar seu próprio perfil a qualquer momento
O sistema SHALL expor `PUT /profile` como upsert: cria o perfil se não existir, ou atualiza os campos enviados se já existir, sem limite de quantas vezes o usuário pode alterá-lo.

#### Scenario: Primeiro salvamento com apenas os obrigatórios
- **WHEN** um usuário sem perfil envia `PUT /profile` com nome completo, telefone, tipo de criação e produção/ano preenchidos
- **THEN** o sistema cria o perfil com sucesso, mesmo sem os demais campos preenchidos

#### Scenario: Edição de perfil já existente
- **WHEN** um usuário com perfil já cadastrado envia `PUT /profile` com novos valores
- **THEN** o sistema atualiza a linha existente (mesmo `user_id`/`sequential_id`) com os novos valores, sem criar uma segunda linha

#### Scenario: Usuário não pode escrever no perfil de outra conta
- **WHEN** qualquer requisição de escrita tenta gravar dados de perfil associados a um `user_id` diferente do usuário autenticado no token
- **THEN** o sistema rejeita a operação (aplicado via RLS, independentemente do endpoint chamado)

### Requirement: Campos obrigatórios são validados no salvamento
O sistema SHALL rejeitar `PUT /profile` se nome completo, telefone de contato, tipo de criação ou produção anual estiverem ausentes ou vazios, retornando erro por campo. Os demais campos (instagram, linkedin, empresa, CNPJ, endereço e demais campos complementares) SHALL permanecer opcionais.

#### Scenario: Requisição sem campo obrigatório é rejeitada
- **WHEN** um usuário envia `PUT /profile` sem o telefone de contato (ou qualquer outro campo obrigatório)
- **THEN** o sistema retorna HTTP 422 identificando o(s) campo(s) obrigatório(s) ausente(s), e nenhuma alteração é persistida

#### Scenario: Requisição com opcionais ausentes é aceita
- **WHEN** um usuário envia `PUT /profile` com todos os obrigatórios preenchidos e nenhum campo de endereço/empresa/redes sociais
- **THEN** o sistema aceita e salva o perfil normalmente, com os campos opcionais nulos

### Requirement: Tipo de criação é restrito a um conjunto fechado de valores
O sistema SHALL aceitar apenas `"piscicultura"` ou `"carcinicultura"` para o campo tipo de criação, tanto na validação do backend quanto na opção exibida no frontend.

#### Scenario: Valor fora da lista é rejeitado
- **WHEN** um usuário envia `PUT /profile` com tipo de criação diferente de "piscicultura" ou "carcinicultura"
- **THEN** o sistema retorna HTTP 422 e não salva o perfil

### Requirement: Produção anual é numérica com uma casa decimal
O sistema SHALL armazenar a produção anual em toneladas como número não negativo com precisão de uma casa decimal, e SHALL rejeitar valores com mais de uma casa decimal ou negativos.

#### Scenario: Valor com uma casa decimal é aceito
- **WHEN** um usuário envia produção anual `"125.5"` toneladas
- **THEN** o sistema salva o valor `125.5`

#### Scenario: Valor com mais de uma casa decimal é rejeitado
- **WHEN** um usuário envia produção anual `"125.55"` toneladas
- **THEN** o sistema retorna HTTP 422 e não salva o perfil

### Requirement: Estado do endereço é restrito às siglas de UF válidas
Quando informado, o campo estado do endereço SHALL aceitar apenas uma das 26 siglas de unidade federativa mais o Distrito Federal (DF); o backend SHALL rejeitar qualquer outro valor.

#### Scenario: Sigla de UF válida é aceita
- **WHEN** um usuário envia `"SP"` como estado do endereço
- **THEN** o sistema salva o valor normalmente

#### Scenario: Sigla inválida é rejeitada
- **WHEN** um usuário envia `"XX"` como estado do endereço
- **THEN** o sistema retorna HTTP 422 e não salva o perfil

### Requirement: Página "Meu Perfil" permite cadastro e edição
O sistema SHALL prover uma página autenticada "Meu Perfil" onde o usuário visualiza seus dados atuais (quando existentes), edita qualquer campo e salva as alterações, com os campos obrigatórios sinalizados e validados antes do envio.

#### Scenario: Usuário acessa a página com perfil já preenchido
- **WHEN** um usuário com perfil cadastrado abre "Meu Perfil"
- **THEN** o formulário é exibido pré-preenchido com os valores salvos, incluindo o email de login em modo somente leitura

#### Scenario: Usuário tenta salvar sem preencher um obrigatório
- **WHEN** um usuário deixa em branco um campo obrigatório e tenta salvar
- **THEN** o formulário impede o envio e sinaliza visualmente o(s) campo(s) pendente(s), sem chamar a API
