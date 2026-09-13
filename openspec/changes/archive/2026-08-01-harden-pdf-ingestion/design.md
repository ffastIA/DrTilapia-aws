## Context

- `main.py` (`/admin/upload`): escreve o upload em `tempfile.NamedTemporaryFile`, chama `rag_service.ingest_pdf(temp_path, file.filename)`, e apaga o arquivo temporário em `finally: os.unlink(temp_path)` — o único momento em que os bytes originais existem é durante essa janela.
- `original_file_id = hashlib.md5(original_filename.encode()).hexdigest()` (`rag_service.py`, início de `ingest_pdf`) — hash do nome, não do conteúdo.
- `_check_file_exists` verifica duplicata via `metadata->>original_file_id` (JSONB) — escrito na mesma passada que insere os chunks, então não distingue "ingestão completa" de "ingestão parcial que falhou depois de inserir alguns chunks".
- `_backfill_top_level_columns` (adicionado em `restore-embedding-and-chunking-quality`) é uma segunda escrita separada, depois do `add_documents` — outro ponto onde uma falha deixa o documento em estado inconsistente (JSONB completo, colunas top-level ausentes).
- Padrão já estabelecido para upload de Storage em outros serviços do projeto (`fish_image_service.py`, `video_service.py`): `self.bucket = BUCKET_NAME`; `supabase_admin.storage.from_(self.bucket).upload(path=..., file=file_obj, file_options={"content-type": ...})`. Reutilizar essa forma, não inventar uma nova.
- `vector_admin_repository.py` já lê `storage_bucket`/`storage_path` e já sabe deletar do Storage (`delete_file`, chamado pelo cleanup) — só nunca recebeu dados reais para agir sobre.

## Goals / Non-Goals

**Goals:**
- PDF original recuperável depois da ingestão, para reprocessamento/auditoria.
- Identidade de documento por conteúdo, não por nome de arquivo.
- Uma ingestão que falha no meio não deixa rastro inconsistente nem bloqueia a próxima tentativa.
- Ingestões longas (OCR) não travam outras requisições.

**Non-Goals:**
- Não implementa versionamento de documentos (reingerir o "mesmo" arquivo com conteúdo diferente ainda é tratado como duplicata/substituição simples, não como uma nova versão rastreada).
- Não migra `clean_reindex_service.py`/`insert_vector_batch` para um estado "correto e usado" — a decisão aqui é só reconhecer que são órfãos e decidir remover ou consertar, não redesenhar o caminho de reindexação.
- Não muda a cascata de extração em si (pypdf/pdfplumber/Tesseract/Vision) — só onde/como ela roda (thread vs. event loop).

## Decisions (preliminares — refinar na implementação)

1. **Bucket dedicado para PDFs de origem** (ex.: `rag-source-pdfs`), seguindo o padrão de `fish_image_service.py`/`video_service.py` (um serviço, um bucket, `storage_path` derivado de forma previsível). Alternativa considerada: reaproveitar um bucket genérico existente — rejeitada para não misturar categorias de arquivo com políticas de acesso potencialmente diferentes.
2. **Hash de conteúdo via SHA-256 do arquivo, não MD5 do nome.** MD5 é aceitável para deduplicação (não é uso criptográfico), mas trocar para SHA-256 evita qualquer discussão futura sobre colisão e não tem custo prático diferente. A migração dos 4 documentos já ingeridos (recalcular a partir do conteúdo armazenado, ou reingerir do zero) é uma decisão de implementação, não travada aqui.
3. **"Transacional" na prática = limpar em caso de falha, não uma transação de banco real.** O Supabase/PostgREST usado aqui não expõe transação multi-statement pelo client Python facilmente; a abordagem realista é: se qualquer etapa falhar, executar um `DELETE` de compensação nas linhas já inseridas para aquele `original_file_id` antes de retornar o erro — replicando o padrão que `vector_admin_repository.delete_file` já sabe fazer.
4. **OCR fora do event loop via thread, não um worker/fila separado.** Um sistema de filas (Celery/RQ) seria mais robusto para ingestões muito grandes, mas é infraestrutura nova desproporcional ao volume atual (4-10 documentos). `asyncio.to_thread`/`run_in_executor` resolve o bloqueio do event loop sem introduzir um componente novo de infra.
5. **`clean_reindex_service.py`/`insert_vector_batch`: inclinação a remover, não consertar.** Nenhum caminho ativo os usa hoje; consertar um recurso que ninguém pediu e nada chama é manutenção sem benefício. Decisão final fica para a implementação, com espaço para o usuário discordar.

## Risks / Trade-offs

- **[Risco] Migrar `original_file_id` para hash de conteúdo é uma mudança de identificador — qualquer código que hoje computa esse hash a partir do nome do arquivo (ex.: para verificar duplicata antes mesmo de ler o arquivo) precisa mudar de ordem (ler o arquivo primeiro).**
- **[Trade-off] Upload para Storage adiciona uma chamada de rede a mais por ingestão** — aceito, é o objetivo da mudança.
- **[Risco] "Limpar em caso de falha" pode competir com uma falha na própria limpeza** (ex.: banco caiu no meio) — aceito como risco residual; não existe solução sem transação de banco real, e isso já é mais seguro que o estado atual (nenhuma limpeza).

## Open Questions

- Reingerir os 4 documentos atuais para adotar o novo `original_file_id`, ou migrar in-place recalculando o hash a partir do `content` já armazenado? Decidir na implementação — migrar in-place evita gastar embeddings de novo.
- `clean_reindex_service.py`: remover de vez ou consertar para ficar utilizável? Pendente de decisão do usuário na implementação desta change.
