## Why

Durante a verificação ao vivo das mudanças anteriores, encontramos dois bugs novos, pré-existentes e não relacionados ao escopo daquelas mudanças:

1. **`/consultoria/chat` está completamente quebrado.** `backend/app/services/rag_service.py`'s `get_answer` chama `self.supabase.rpc("match_documents", {"query_embedding": ..., "match_count": 5, "similarity_threshold": 0.7})`, mas essa função **não existe** no banco (`tfdripphcwbjiveksuet`). A função de busca vetorial que de fato existe é `public.rpc_vector_search(query_vector jsonb, limit_count integer)`, com parâmetros e nome diferentes, sem suporte a `similarity_threshold`, e retornando colunas `(id, content, metadata, similarity)` — sem `original_file_id`/`original_file_name` no topo (só dentro de `metadata`). Toda chamada ao chat retorna `500 PGRST202` hoje.

2. **A exclusão de documentos (individual e em massa) é um no-op silencioso para os dados já existentes.** Os 49 registros de `public.documents` ingeridos anteriormente têm a coluna de topo `original_file_id` como `NULL` — o valor real só existe dentro de `metadata->>'original_file_id'`. `VectorAdminRepository.delete_file` (e o cleanup em massa, que o chama por arquivo) filtram a exclusão com `.eq('original_file_id', ...)` na coluna de topo, que nunca casa com nenhuma linha para esses registros legados. Confirmamos isso ao vivo: o cleanup "real", autorizado explicitamente, reportou `total_documents_deleted: 0` e os 4 arquivos reais permaneceram intactos — ou seja, hoje **nenhum admin consegue de fato apagar um arquivo já existente pelo painel**. (Ingestões novas, via `rag_service.ingest_pdf`, já gravam `original_file_id`/`original_file_name` corretamente na coluna de topo — o problema é só com os dados legados já gravados.)

## What Changes

- `backend/app/services/rag_service.py`: `get_answer` passa a chamar `rpc_vector_search(query_vector, limit_count)` (nomes de parâmetros corretos), aplica o filtro de `similarity_threshold` em Python sobre o campo `similarity` retornado, e `_normalize_match_doc` passa a ler `original_file_id`/`original_file_name` com fallback para dentro de `metadata` quando ausentes no nível superior (mesmo padrão defensivo já usado em `vector_admin_repository._extract_document_fields`).
- Migration de dados (não de schema) em `public.documents`: preencher `original_file_id`/`original_file_name` a partir de `metadata` nas linhas onde a coluna de topo está `NULL` mas o valor existe dentro de `metadata`. Não backfilla nem altera nenhuma linha que já tenha os campos de topo preenchidos.
- Nenhuma mudança em `rag_service.ingest_pdf` (já grava os campos corretamente para ingestões novas).

## Capabilities

### New Capabilities
- `rag-chat-vector-search`: Comportamento correto de `/consultoria/chat` usando a função de busca vetorial que de fato existe no banco, com atribuição de fonte (nome/id do arquivo) funcionando mesmo para documentos legados sem os campos de topo preenchidos.
- `documents-file-id-backfill`: Garantia de que `original_file_id`/`original_file_name` na tabela `documents` refletem o valor presente em `metadata` quando a coluna de topo está nula, permitindo que as operações de exclusão (individual e em massa) encontrem e removam as linhas corretas.

### Modified Capabilities
(nenhuma)

## Impact

- **Código afetado**: `backend/app/services/rag_service.py` (`get_answer`, `_normalize_match_doc`). Nenhuma mudança de schema, endpoint ou contrato de request/response.
- **Banco de dados**: migration de dados (UPDATE) em `public.documents`, apenas preenchendo colunas hoje `NULL` a partir de `metadata` já existente. Nenhuma linha com dados é removida ou tem valor não-nulo sobrescrito.
- **Frontend**: nenhuma mudança.
- **Comportamento observável**: `/consultoria/chat` volta a responder (200) com fontes corretas; excluir um arquivo pelo painel admin (individual ou via limpeza em massa) passa a de fato remover as linhas correspondentes de `documents` para os dados legados, além dos novos.
