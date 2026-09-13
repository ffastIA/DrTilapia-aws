## Context

- `main.py`: `return {"answer": response, "sources": []}` — `sources` é literal, nunca calculado.
- `rag_service.get_answer` retorna `result["answer"]` (uma `str`); o estado do grafo (`State`, TypedDict) tem `context` (texto achatado) mas não guarda a lista de `Document`s recuperados até o fim — eles são descartados assim que `context = "\n\n".join(...)` roda no nó `retrieve`.
- Cada `Document` recuperado já tem em `.metadata`: `db_id`, `original_file_id`, `original_file_name`, `page`/`page_start`/`page_end`, `chunk_index`, `similarity` (via `_normalize_match_doc`).
- Frontend: `useChat.ts` tipa a resposta como `{ answer: string; sources: string[] }` mas nunca lê `sources`; `ChatMessage.tsx` só recebe `message`/`isUser`.

## Goals / Non-Goals

**Goals:**
- Fontes reais (arquivo + página) na resposta, deduplicadas por arquivo (ou por arquivo+página, a decidir — ver Open Questions).
- Não regredir nada da recuperação/geração — mudança é só de "carregar a informação adiante", não de comportamento de busca.

**Non-Goals:**
- Não implementa citação inline no texto da resposta (ex.: "[1]" no meio da resposta apontando pra fonte 1) — só uma lista de fontes ao final, mais simples de implementar e já resolve o problema central de verificabilidade.
- Não muda o que é recuperado nem como é rankeado — depende de `retrieval-refusal-quality` já ter aterrissado para as fontes mostradas serem confiáveis.

## Decisions

1. **Lista estruturada de fontes ao final da resposta, não citação inline.** Citação inline exigiria o LLM referenciar índices de fonte corretamente no texto gerado (frágil, sujeito a alucinação de números errados) ou pós-processamento para inserir marcadores (complexo). Uma lista separada é mais simples e mais confiável — decisão a revisitar se o usuário quiser inline depois.

2. **Deduplicação por arquivo, não por chunk individual.** Mostrar 8 entradas repetidas do mesmo PDF (uma por chunk usado) seria ruído. Agrupar por `original_file_name`, com o range de páginas coberto (`min(page_start)`–`max(page_end)` entre os chunks usados daquele arquivo).

## Risks / Trade-offs

- **[Trade-off] Estado do grafo precisa carregar os `Document`s completos (não só o texto achatado) até o final** — leve aumento de memória por request, irrelevante no volume atual.
- **[Risco] Mudar a forma de retorno de `get_answer` (de `str` para algo estruturado) pode quebrar chamadores existentes** — checar todos os call sites (`main.py`, scripts manuais `test_phase*.py`) antes de mudar a assinatura; preferir aditivo (retornar uma tupla ou um objeto com `.answer`/`.sources`) a quebrar o contrato atual sem necessidade.

## Open Questions (resolvidas na implementação)

- **Deduplicar por arquivo inteiro ou por arquivo+página?** Decidido: por arquivo inteiro, com o range de páginas (`min(page_start)`–`max(page_end)`) agregado. Testado com uma pergunta que usou 8 chunks de 3 arquivos diferentes (via `_add_data_companion_chunks`) — o resultado ficou como 3 entradas de fonte, não 8, exatamente o comportamento pretendido.
- **Mostrar trecho/similaridade ou só nome+página?** Decidido: só nome do arquivo + páginas. Formato final no frontend: `arquivo.pdf (p. 3)` ou `arquivo.pdf (p. 3-5)` quando a resposta cobre um range; páginas exibidas 1-indexed (a coluna `page` no banco é 0-indexed).

## Resultado da verificação (2026-08-01)

- Pergunta respondível sobre o BIA → `sources: [{'file': 'BIA_RAG.pdf', 'page_start': 0, 'page_end': 3}]`, confirmado batendo com o documento real.
- Pergunta fora do escopo → `sources: []`, nenhuma fonte inventada (a recusa implementada em `retrieval-refusal-quality` já garante `source_docs=[]` quando `insufficient_context=True`, então `_build_sources` não precisou de nenhum caso especial para isso).
- `test_phase6_post_reindex_success_manual.py`: ✅ APROVADO, 3 fontes reais listadas para uma pergunta que tocou múltiplos documentos.
