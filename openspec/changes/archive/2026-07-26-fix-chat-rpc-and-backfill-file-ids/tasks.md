## 1. Corrigir a busca vetorial do chat

- [x] 1.1 Em `backend/app/services/rag_service.py`, `get_answer`: trocado `rpc("match_documents", {"query_embedding", "match_count", "similarity_threshold"})` por `rpc("rpc_vector_search", {"query_vector": query_embedding, "limit_count": 20})`.
- [x] 1.2 Filtro em Python por `similarity >= 0.7`, mantendo os 5 melhores ordenados por similaridade desc, antes de normalizar/montar o contexto.
- [x] 1.3 `_normalize_match_doc` atualizado: `original_file_id`/`original_file_name` resolvidos do campo de topo com fallback para dentro de `metadata`.

## 2. Backfill dos dados legados

- [x] 2.1 Migration `backfill_documents_file_id_from_metadata` aplicada via `apply_migration` no projeto `tfdripphcwbjiveksuet`.
- [x] 2.2 `get_advisors(type="security")` rodado após aplicar — nenhum alerta novo (os mesmos warnings pré-existentes de antes).

## 3. Verificação

- [x] 3.1 Confirmado via `execute_sql`: `total_documents=49`, `count(distinct original_file_id)=4` (batendo com os 4 arquivos reais), `still_null=0`. Nenhum valor de topo previamente não-nulo foi tocado (o `WHERE original_file_id IS NULL` garante isso).
- [x] 3.2 Backend reiniciado via `backend/.venv` com o código corrigido.
- [x] 3.3 `POST /consultoria/chat` com token válido: **200 OK**, resposta real sobre tilápia do Nilo, com `sources` mostrando `BIA_RAG.pdf` (nome de arquivo real) em várias páginas — não mais vazio nem erro 500 `PGRST202`.
- [x] 3.4 Confirmado via `SELECT` não-destrutivo: filtro `original_file_id = '5faf703da6246b9f38fcf7074c2e5b59'` (arquivo "Indice volumetrico abate.pdf") retornou exatamente os 6 chunks esperados — uma exclusão futura com o mesmo filtro casaria corretamente essas linhas. Nenhuma exclusão real foi executada contra os dados de produção.
