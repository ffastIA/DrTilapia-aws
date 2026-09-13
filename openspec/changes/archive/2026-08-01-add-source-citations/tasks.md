## 1. Backend — carregar fontes até o retorno final

- [x] 1.1 `State` ganhou `source_docs: List[Dict[str, Any]]` — metadata leve (`original_file_name`, `page_start`, `page_end`) de cada chunk usado, montada pelo novo helper `_extract_source_doc_info`. Populado nos nós `retrieve` e `retrieve_retry`.
- [x] 1.2 `get_answer` agora retorna `AnswerResult` (NamedTuple `answer`/`sources`) em vez de `str` — aditivo na forma de um tipo novo e explícito, não um dict solto. Novo helper `_build_sources` deduplica por `original_file_name` e calcula o range de páginas (`min(page_start)`–`max(page_end)`) coberto por aquele arquivo.
- [x] 1.3 Todos os call sites atualizados: `main.py`, `evaluation/run_eval.py`, `test_phase3_rag_manual.py`, `test_phase4_quality_manual.py`, `test_phase6_post_reindex_success_manual.py`, `tests/test_backend_api.py` (o mock de `test_chat_success` também estava com a forma de retorno errada antes desta mudança — corrigido junto).

## 2. Backend — endpoint

- [x] 2.1 `POST /consultoria/chat`: `"sources": []` hardcoded substituído por `result.sources` real.
- [x] 2.2 Schema de `sources`: `[{file: str, page_start: int | null, page_end: int | null}]` — decidido durante a implementação (não travado em design.md antes).

## 3. Frontend

- [x] 3.1 `useChat.ts`: novo tipo exportado `ChatSource`; `ChatMessage`/`ChatResponse` internos passam a carregar `sources`.
- [x] 3.2 `ChatMessage.tsx`: renderiza as fontes abaixo da resposta (só para mensagens da IA com fontes não vazias), formatando página 0-indexed como 1-indexed para o usuário (`p. 3` em vez de `p. 2`), e como range quando `page_start != page_end` (`p. 3-5`).
- [x] 3.3 `consultoria/page.tsx`: tipo `Message` local (que já duplicava o shape do hook em vez de importar) ganhou `sources?: ChatSource[]`, repassado ao componente.

## 4. Verificação

- [x] 4.1 Teste manual direto (`rag_service.get_answer`): pergunta respondível sobre o BIA mostrou `sources: [{'file': 'BIA_RAG.pdf', 'page_start': 0, 'page_end': 3}]` — bate com o documento/páginas reais.
- [x] 4.2 Mesma checagem para recusa: pergunta claramente fora do escopo devolveu `sources: []`, nenhuma fonte inventada.
- [x] 4.3 `python test_phase6_post_reindex_success_manual.py`: ✅ APROVADO, com 3 fontes reais listadas (BIP 2024, Genetic characterization, Indice volumetrico — os 3 arquivos que de fato embasaram a resposta).
- [x] 4.4 `npx tsc --noEmit`: nenhum erro novo introduzido pelas mudanças de frontend (só o erro pré-existente não relacionado em `Button`/`size`).
- [x] 4.5 `pytest tests/test_rag_retrieval_refusal.py`: 8/8 continuam passando (nenhuma regressão na mudança anterior).
