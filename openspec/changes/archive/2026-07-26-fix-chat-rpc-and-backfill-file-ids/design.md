## Context

**Bug 1 — RPC inexistente.** `rag_service.py:54-60` (`get_answer`):
```python
response = self.supabase.rpc("match_documents", {
    "query_embedding": query_embedding,
    "match_count": 5,
    "similarity_threshold": 0.7
}).execute()
```
A função `match_documents` não existe no banco. A função real, inspecionada via `execute_sql`:
```sql
CREATE OR REPLACE FUNCTION public.rpc_vector_search(query_vector jsonb, limit_count integer DEFAULT 5)
 RETURNS TABLE(id text, content text, metadata jsonb, similarity double precision)
 LANGUAGE plpgsql
AS $function$
DECLARE
    query_embedding vector;
BEGIN
    SELECT ('[' || string_agg(value::text, ',') || ']')::vector
    INTO query_embedding
    FROM jsonb_array_elements(query_vector) AS value;

    RETURN QUERY
    SELECT
        d.id::text, d.content, d.metadata,
        1.0 - (d.embedding <=> query_embedding) AS similarity
    FROM public.documents d
    WHERE d.deleted_at IS NULL AND d.embedding IS NOT NULL
    ORDER BY d.embedding <=> query_embedding ASC
    LIMIT limit_count;
END;
$function$
```
Diferenças: nome do parâmetro do embedding (`query_vector`, não `query_embedding`), nome do limite (`limit_count`, não `match_count`), **sem parâmetro de threshold** (o filtro por similaridade mínima precisa ser feito em Python sobre o campo `similarity` retornado), e **sem colunas `original_file_id`/`original_file_name` no retorno** — só existem dentro de `metadata`.

`_normalize_match_doc` hoje assume que essas colunas vêm no nível superior do doc:
```python
def _normalize_match_doc(self, doc):
    return {
        "content": doc.get("content", ""),
        "metadata": doc.get("metadata", {}),
        "original_file_name": doc.get("original_file_name", ""),
        "original_file_id": doc.get("original_file_id", "")
    }
```
Com `rpc_vector_search`, isso sempre resultaria em string vazia para essas duas chaves — a resposta do chat funcionaria, mas todas as fontes apareceriam como "Arquivo desconhecido".

**Bug 2 — dados legados sem `original_file_id` na coluna de topo.** Confirmado via `execute_sql`: as 49 linhas de `documents` ingeridas anteriormente têm `original_file_id`/`original_file_name` (colunas de topo, tipo `text`) como `NULL`, mas o valor correto existe dentro de `metadata->>'original_file_id'` / `metadata->>'original_file_name'`. `vector_admin_repository.py`'s `_extract_document_fields` já tem um fallback para leitura:
```python
original_file_id = row.get('original_file_id') or metadata.get('original_file_id')
```
— por isso a listagem (`GET /admin/vector-base/files`) funciona corretamente mesmo para esses dados. Mas `delete_file`:
```python
response = supabase_admin.table("documents").delete().eq('original_file_id', original_file_id).execute()
```
filtra a exclusão pela coluna de topo diretamente — que é `NULL` para essas linhas —, então o `DELETE` nunca casa nenhuma linha. Confirmado ao vivo: cleanup real reportou `total_documents_deleted: 0` para os 4 arquivos reais, que permaneceram intactos.

Ingestões novas via `rag_service.ingest_pdf` → `_build_chunk_payloads` já incluem `original_file_id`/`original_file_name` como chaves de nível superior no payload de insert — ou seja, o código de ingestão atual está correto; o problema é exclusivamente com as linhas já gravadas por uma ingestão anterior/diferente.

## Goals / Non-Goals

**Goals:**
- `/consultoria/chat` volta a funcionar (200), com atribuição de fonte (nome do arquivo) correta mesmo para documentos legados.
- Excluir um arquivo (individual ou via limpeza em massa) passa a de fato remover as linhas correspondentes em `documents`, tanto para dados legados quanto novos.
- Nenhuma linha de dado existente é perdida ou sobrescrita incorretamente pela migration de backfill.

**Non-Goals:**
- Não renomear/recriar a função `rpc_vector_search` no banco — adaptar o código Python a ela é mais seguro do que manter duas funções de busca vetorial quase-duplicadas.
- Não adicionar uma constraint `NOT NULL` em `original_file_id`/`original_file_name` nesta mudança — isso poderia quebrar algum caminho de ingestão ainda não mapeado; fica como melhoria futura, se necessário.
- Não testar a exclusão real contra os 4 arquivos de produção nesta mudança — a verificação usará apenas consultas `SELECT` não-destrutivas para confirmar que o filtro passaria a casar as linhas certas. Um teste de exclusão real, se desejado, requer nova autorização explícita.

## Decisions

1. **Adaptar `rag_service.get_answer` para chamar `rpc_vector_search` com os nomes de parâmetro corretos, e aplicar o filtro de `similarity_threshold` em Python.**
   - Pedir um `limit_count` maior que o desejado final (ex.: `limit_count=20`) para ter margem de sobra depois de filtrar por `similarity >= 0.7`, e então cortar para os top 5 por similaridade. Alternativa considerada: manter `limit_count=5` e aceitar menos resultados após o filtro — rejeitada porque poderia retornar menos contexto do que o pretendido originalmente (5 documentos com similaridade mínima).
   - `_normalize_match_doc` passa a resolver `original_file_id`/`original_file_name` com fallback: `doc.get('original_file_id') or doc.get('metadata', {}).get('original_file_id', '')` (mesmo padrão de `vector_admin_repository._extract_document_fields`), cobrindo tanto o retorno atual de `rpc_vector_search` (que só tem os campos em `metadata`) quanto um eventual futuro retorno com colunas de topo.

2. **Migration de dados (UPDATE, não DDL) em `public.documents`**: preencher `original_file_id`/`original_file_name` a partir de `metadata` apenas onde a coluna de topo é `NULL` e o valor existe em `metadata`.
   ```sql
   update public.documents
   set original_file_id = metadata->>'original_file_id'
   where original_file_id is null
     and metadata->>'original_file_id' is not null;

   update public.documents
   set original_file_name = metadata->>'original_file_name'
   where original_file_name is null
     and metadata->>'original_file_name' is not null;
   ```
   - Aplicada via `apply_migration` (projeto hospedado real).
   - Alternativa considerada: corrigir apenas o código de exclusão para filtrar via `metadata->>'original_file_id'` como fallback, sem tocar nos dados. Rejeitada como única solução — o backfill é mais simples, único, e alinha os dados legados com o formato que todo o resto do código (incluindo a ingestão nova) já espera, evitando manter dois caminhos de filtro para sempre. Mesmo assim, nada impede adicionar o fallback defensivo no futuro se aparecerem novos dados malformados.

## Risks / Trade-offs

- **[Risco] O backfill poderia sobrescrever um valor de topo já preenchido incorretamente** → Mitigação: o `WHERE original_file_id IS NULL` garante que só linhas hoje nulas são tocadas; nenhum valor não-nulo existente é alterado.
- **[Risco] `rpc_vector_search` sem `similarity_threshold` pode retornar documentos pouco relevantes se `limit_count` for pequeno e nada passar do threshold** → Mitigação: pedir `limit_count` maior (20) antes de filtrar por threshold em Python, replicando a intenção original com folga.
- **[Trade-off] Não testamos a exclusão real fim-a-fim nesta mudança** — validamos apenas que o filtro SQL passaria a casar as linhas certas (via SELECT), não que o DELETE de fato executa contra produção. Uma verificação totalmente completa exigiria apagar um arquivo real ou usar um arquivo de teste descartável — decisão deixada para quando a mudança for aplicada, com autorização explícita se for o caso.
