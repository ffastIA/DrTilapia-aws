## ADDED Requirements

### Requirement: Remoção de fundo usa um modelo fixado, não o default de uma dependência externa
`ImageProcessingService.remove_background` SHALL usar um modelo de remoção de fundo determinado por configuração explícita da aplicação (`REMBG_MODEL`, default `u2net`), nunca o valor default da versão instalada da biblioteca `rembg`.

#### Scenario: Upgrade da biblioteca não muda o modelo em uso
- **WHEN** a versão instalada de `rembg` é atualizada e sua própria escolha de modelo default muda
- **THEN** `remove_background` continua usando o modelo determinado por `REMBG_MODEL`, sem mudança de comportamento

### Requirement: Análise de imagem não crasha o processo do backend
Processar uma imagem de peixe via `POST /fish/analyses/process` SHALL completar (com sucesso ou com um erro tratado, HTTP apropriado) sem derrubar o processo worker que atende a requisição.

#### Scenario: Processamento de uma imagem real completa sem crash
- **WHEN** um usuário autenticado envia duas imagens válidas (lateral e superior) para análise
- **THEN** a resposta é `200` com o resultado da análise, e o processo do backend continua rodando normalmente para requisições seguintes

### Requirement: Modelo de remoção de fundo está pronto no primeiro uso
O modelo de remoção de fundo usado por `remove_background` SHALL estar disponível localmente assim que o backend iniciar, sem exigir download em tempo de execução durante uma requisição real.

#### Scenario: Primeira análise depois de subir o container não espera download
- **WHEN** o container do backend acabou de subir (imagem construída com o modelo pré-baixado) e a primeira requisição de análise de imagem chega
- **THEN** a análise não dispara nenhum download de modelo, completando no tempo normal de processamento (sem o atraso adicional de baixar ~176MB)
