## ADDED Requirements

### Requirement: Administrador pode reindexar arquivos já indexados
`POST /admin/vector-base/reindex` SHALL reprocessar (nova extração, chunking e embeddings) um ou mais arquivos já indexados, identificados por `original_file_id`, a partir do PDF original salvo no Storage — sem exigir reenvio do arquivo pelo cliente.

#### Scenario: Reindexação de um arquivo específico
- **WHEN** um administrador chama `POST /admin/vector-base/reindex` com `confirmation_phrase` válida e `original_file_ids: ["<id>"]` para um arquivo cujo PDF original ainda está no Storage
- **THEN** o arquivo é reprocessado com a extração/chunking/embedding atuais, os chunks antigos desse arquivo deixam de existir, e a resposta reporta `processed_files: 1`

#### Scenario: Reindexação de todos os arquivos
- **WHEN** um administrador chama o endpoint com `confirmation_phrase` válida e sem `original_file_ids`
- **THEN** todos os arquivos atualmente indexados são reprocessados, um a um, e o relatório agregado reflete quantos foram processados e quantos falharam

#### Scenario: Frase de confirmação ausente ou inválida
- **WHEN** a requisição não inclui `confirmation_phrase` ou inclui um valor que não corresponde à frase esperada
- **THEN** nenhum arquivo é reprocessado

### Requirement: Falha ao reindexar nunca apaga o índice existente
Se a reingestão de um arquivo falhar (erro de extração, de embeddings, ou qualquer exceção), o sistema SHALL preservar os chunks já existentes desse arquivo intactos — nunca removê-los antes de uma reingestão bem-sucedida.

#### Scenario: Reingestão falha, índice antigo permanece
- **WHEN** a reingestão de um arquivo falha por qualquer motivo (ex.: PDF corrompido, erro da API de embeddings)
- **THEN** os chunks que existiam antes da tentativa de reindexação continuam presentes e recuperáveis, e o relatório marca aquele arquivo como falho

### Requirement: Painel admin permite reindexar um arquivo pela interface
O painel de administração RAG (`/main/admin`) SHALL exibir uma ação "Reindexar" por documento listado, que aciona `POST /admin/vector-base/reindex` para aquele arquivo e atualiza a lista após sucesso.

#### Scenario: Administrador reindexa um arquivo pela UI
- **WHEN** um administrador autenticado clica em "Reindexar" num documento listado no painel admin
- **THEN** o sistema chama o endpoint de reindexação para aquele arquivo, exibe uma mensagem de sucesso ou erro, e atualiza a lista de documentos após sucesso

### Requirement: Falha em um arquivo não interrompe o processamento do lote
Ao reindexar múltiplos arquivos numa mesma chamada, uma falha em um arquivo SHALL NOT impedir que os demais arquivos do lote sejam processados.

#### Scenario: Um arquivo sem PDF no Storage não bloqueia os outros
- **WHEN** um lote de reindexação inclui um arquivo sem `storage_bucket`/`storage_path` (PDF original não disponível) e outros arquivos com o PDF disponível
- **THEN** o arquivo sem PDF é reportado como falho, e os demais arquivos do lote são reindexados normalmente
