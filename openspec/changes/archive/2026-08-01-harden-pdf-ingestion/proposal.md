## Why

Quatro fragilidades da ingestão foram identificadas e adiadas repetidamente em mudanças anteriores, cada uma citando uma "mudança de robustez" futura que nunca chegou a ser proposta:

1. **O PDF original nunca é salvo.** `ingest_pdf` recebe um arquivo temporário (`main.py` escreve via `tempfile.NamedTemporaryFile`, apaga em `finally: os.unlink(temp_path)`), processa, e o descarta — nada é enviado ao Supabase Storage. As colunas `storage_bucket`/`storage_path` existem na tabela `documents` e o código de administração (`vector_admin_repository.py`) já lê e usa essas colunas para limpeza (`storage.from_(bucket).remove(...)`), mas nada no caminho de ingestão real as popula. Se for preciso reprocessar um documento (novo modelo de embedding, correção de extração, auditoria), a única fonte é o computador de quem fez o upload originalmente — como aconteceu nesta sessão com o BIP 2024, onde o exemplar que causou o problema original não existe mais em lugar nenhum do projeto.

2. **`original_file_id = MD5(nome do arquivo)`, não do conteúdo.** Dois arquivos com nomes iguais e conteúdos diferentes colidem; o mesmo arquivo com nome diferente não é detectado como duplicata. Documentado como risco em `restore-embedding-and-chunking-quality` e `fix-vector-index-and-db-hygiene`, nunca corrigido.

3. **Ingestão não é transacional.** `ingest_pdf` insere chunks (`add_documents`) e depois faz um upsert separado para as colunas top-level (`_backfill_top_level_columns`, adicionado em `restore-embedding-and-chunking-quality`); se qualquer etapa falhar no meio, as linhas já inseridas ficam órfãs — e como `_check_file_exists` verifica pela `metadata->>original_file_id` (JSONB, sempre escrito primeiro), uma tentativa de reingestão é bloqueada como `"already_exists"` mesmo com os dados incompletos.

4. **`ingest_pdf` é `async def` mas bloqueia o event loop.** A cascata de extração (especialmente OCR via Tesseract/Vision, que pode levar minutos) roda de forma síncrona dentro de uma corrotina — sem `await` real em nenhuma etapa pesada. Isso significa que uma ingestão grande trava o processo inteiro, incluindo chamadas de chat de outros usuários.

## What Changes

- O PDF original passa a ser enviado ao Supabase Storage durante a ingestão, populando `storage_bucket`/`storage_path` de verdade.
- `original_file_id` passa a ser hash do **conteúdo** do arquivo, não do nome.
- Uma falha em qualquer etapa da ingestão (inserção de chunks, backfill de colunas, upload do PDF) limpa o que já foi escrito para aquele arquivo antes de retornar erro — sem deixar linhas órfãs nem bloquear uma nova tentativa.
- O trabalho pesado de extração/OCR passa a rodar fora do event loop principal (thread separada), para não bloquear outras requisições durante uma ingestão longa.
- **BREAKING** (interno): mudar `original_file_id` de hash-do-nome para hash-do-conteúdo muda o identificador de todos os documentos já ingeridos. Requer reingestão (ou uma migração que recalcule o id a partir do conteúdo já armazenado) — a decidir na implementação.

## Capabilities

### New Capabilities
- `pdf-ingestion-robustness`: garantias sobre persistência do arquivo original, identidade por conteúdo, atomicidade da ingestão e não-bloqueio do processo durante ingestões longas.

## Impact

- `backend/app/services/rag_service.py`: `ingest_pdf` (upload, cálculo de `original_file_id`, tratamento de erro/rollback, offload para thread).
- `backend/app/main.py`: endpoint `/admin/upload` (o arquivo temporário passa a ser a fonte do upload ao Storage antes de ser descartado).
- Possível migração de dados para os 4 documentos já na base (recalcular `original_file_id` por conteúdo, ou reingerir).
- Decisão pendente sobre `clean_reindex_service.py`/`insert_vector_batch` (código órfão hoje) — remover ou consertar de verdade, não deixar como está.
