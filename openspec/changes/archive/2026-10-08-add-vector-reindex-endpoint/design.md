## Context

`original_file_id` hoje é `SHA-256` dos bytes do PDF (`RAGService.ingest_pdf`, desde `harden-pdf-ingestion` — o achado M3 da auditoria original, que descrevia `MD5(nome do arquivo)`, está desatualizado). O PDF original fica salvo no Storage num caminho determinístico (`{original_file_id}{ext}`). `VectorAdminRepository` já sabe listar/consultar arquivos e seus chunks (`list_files`, `get_file`, `get_file_chunks`) e apagar um arquivo inteiro (`delete_file`, que também remove o Storage — não serve para reindex, que precisa MANTER o PDF original).

O único vestígio de uma implementação anterior é um script órfão (`backend/scripts/manual_clean_reindex.py`) que dependia de `app.services.clean_reindex_service.CleanReindexService` — módulo cujo arquivo-fonte foi perdido (só existe o `.pyc`, sem histórico no git). Não há como recuperá-lo com segurança; esta mudança implementa a funcionalidade do zero, reaproveitando a pipeline de ingestão real e testada (`ingest_pdf`), não o script perdido.

## Goals / Non-Goals

**Goals:**
- `POST /admin/vector-base/reindex` reprocessa um ou mais arquivos já indexados (ou todos, se nenhum `original_file_ids` for informado), usando a extração/chunking/embedding ATUAIS — útil depois de corrigir um bug de extração ou mudar parâmetros de chunking.
- Falha ao reindexar um arquivo nunca apaga o índice existente daquele arquivo (sem janela de perda de dados).
- Falha em um arquivo de um lote não interrompe o processamento dos demais (relatório por arquivo).

**Non-Goals:**
- Não tentar recuperar/decompilar o `CleanReindexService` perdido.
- Não mudar `original_file_id` (continua SHA-256 do conteúdo) nem a lógica de deduplicação do upload normal (`ingest_pdf` sem `force`).
- Não implementar reindexação em lote em background/assíncrona com progresso incremental — é uma chamada HTTP síncrona (do ponto de vista do cliente), como os outros endpoints de `/admin/vector-base/*`; para volumes grandes de arquivos, o tempo de resposta cresce linearmente (mesmo custo de um upload por arquivo).

## Decisions

1. **Ingerir primeiro, apagar os chunks antigos depois — nunca o contrário.** Alternativa óbvia (apagar antes de reingerir) foi descartada: se a reingestão falhar no meio (erro da API de embeddings, extração ruim, etc.), o arquivo ficaria sem nenhum chunk, uma perda de dados real. Ingerir primeiro com `force=True` garante que só apagamos o antigo depois de confirmar que o novo já existe.
2. **`force` como parâmetro explícito de `ingest_pdf`, não uma checagem removida.** Manter a checagem de duplicata como default (`force=False`) preserva 100% do comportamento de upload normal; só a chamada de dentro de `reindex_files` passa `force=True` deliberadamente.
3. **Reindexar a partir do PDF no Storage, não pedir upload de novo.** O objetivo de "reindexar" é justamente não precisar re-enviar o arquivo — por isso o pré-requisito é ter `storage_bucket`/`storage_path` preenchidos; arquivos sem isso (ex.: ingeridos antes de o Storage existir) falham individualmente com mensagem clara, não travam o lote.
4. **`delete_document_rows` extraído de `delete_file`** — pequena refatoração para reusar a mesma lógica de "apagar por UUID real da linha" em vez de duplicá-la; `delete_file` continua se comportando exatamente igual (delega para o novo helper).
5. **Nomes dos aliases da fachada** — seguindo o mesmo padrão de `_call_repo_method`, mas aqui a lógica de reindexação é orquestração nova (baixa do Storage, chama `rag_service`, decide o que apagar), não um simples passthrough — por isso vive diretamente em `VectorAdminService.reindex_files`, não como mais um alias de repositório.

## Risks / Trade-offs

- **[Custo]** Reindexar N arquivos custa o mesmo que N uploads (chamadas de embedding à OpenAI). Não há um limite de lote nesta primeira versão — um `original_file_ids` grande (ou omitido, reindexando tudo) pode ser caro/demorado. Aceitável para uma ferramenta administrativa operada manualmente; um limite/confirmação de tamanho fica como possível melhoria futura.
- **[Duplicação temporária]** Durante a janela entre a nova ingestão bem-sucedida e a remoção dos chunks antigos (dentro da mesma requisição), o arquivo tem temporariamente chunks antigos E novos ativos simultaneamente. É uma janela curta (mesma requisição, sem chamada externa entre as duas etapas) — aceito conscientemente em troca de nunca arriscar ficar sem nenhum chunk.
