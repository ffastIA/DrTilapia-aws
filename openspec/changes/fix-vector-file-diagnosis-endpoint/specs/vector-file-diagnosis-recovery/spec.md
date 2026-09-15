## ADDED Requirements

### Requirement: O diagnóstico de recuperação de arquivo retorna um resultado real
`GET /admin/vector-base/files/{original_file_id}/diagnosis` SHALL retornar o diagnóstico de recuperabilidade do arquivo (contagem de chunks ativos/deletados e se o conteúdo é recuperável pela tabela `documents` e/ou pelo Storage), em vez de falhar.

#### Scenario: Diagnóstico de um arquivo existente
- **WHEN** um administrador autenticado chama `GET /admin/vector-base/files/{original_file_id}/diagnosis` para um `original_file_id` que tem ao menos um chunk em `documents`
- **THEN** a resposta é `200` e inclui `total_chunks`, `active_chunks`, `deleted_chunks` e as flags `recoverable_from_table`/`recoverable_from_storage`/`recoverable_from_both`/`recoverable_from_none`

#### Scenario: Diagnóstico não falha mais com erro de método não implementado
- **WHEN** o endpoint de diagnóstico é chamado para qualquer arquivo válido
- **THEN** a resposta nunca é `500` por `NotImplementedError` de resolução de método na fachada do serviço
