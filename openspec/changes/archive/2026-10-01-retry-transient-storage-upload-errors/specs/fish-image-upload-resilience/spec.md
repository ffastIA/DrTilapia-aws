## ADDED Requirements

### Requirement: Upload de imagem tolera falhas transitórias do Storage
Ao subir uma imagem de peixe para o bucket `fish-images`, o sistema SHALL tentar novamente, com um pequeno atraso entre tentativas, quando a chamada ao Storage falhar com um status tipicamente transitório (`429`, `500`, `502`, `503`, `504`), antes de propagar o erro ao chamador.

#### Scenario: Falha transitória se recupera na tentativa seguinte
- **WHEN** a primeira tentativa de upload ao Storage falha com `429` (`too_many_connections`) ou outro status da lista de transitórios, e uma tentativa seguinte dentro do limite de retries é bem-sucedida
- **THEN** `upload_image` retorna normalmente (sucesso), sem propagar o erro da primeira tentativa ao endpoint HTTP

#### Scenario: Falha não-transitória propaga imediatamente
- **WHEN** a chamada ao Storage falha com um status que não está na lista de transitórios (ex.: `403`, `413`)
- **THEN** o erro propaga imediatamente, sem nenhuma tentativa adicional

#### Scenario: Falha persistente ainda propaga após esgotar as tentativas
- **WHEN** todas as tentativas (a original mais as de retry) falham com um status transitório
- **THEN** o erro da última tentativa propaga ao chamador, resultando no mesmo comportamento de erro observado antes desta mudança (resposta HTTP genérica sanitizada)
