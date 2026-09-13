## Why

`POST /consultoria/chat` sempre devolve `"sources": []` hardcoded (`backend/app/main.py`), mesmo o spec aceito `rag-chat-vector-search` declarando que a atribuição de fontes funciona. Cada chunk recuperado já carrega `original_file_id`, `original_file_name`, `page`/`page_start`/`page_end`, `chunk_index` e `similarity` no `metadata` (populados em `_normalize_match_doc`, e as colunas `page`/`chunk_index` agora são reais no banco desde `restore-embedding-and-chunking-quality` — essa mudança foi explicitamente motivada como "pré-requisito da citação de fontes"). Nada no caminho de resposta usa essa informação: `context = "\n\n".join(doc.page_content for doc in docs)` achata tudo em texto puro antes de chegar ao prompt, e a metadata se perde ali.

O resultado prático: o usuário não tem como saber de qual documento (ou página) veio uma afirmação da resposta, e não há como verificar se o sistema está correto sem reabrir o PDF inteiro. Isso é especialmente relevante depois de `retrieval-refusal-quality` — uma vez que o sistema passa a recusar honestamente quando não sabe, mostrar a fonte quando *sabe* fecha o ciclo de confiança.

## What Changes

- `rag_service.get_answer` para de devolver só uma `str` — passa a devolver também a lista de fontes reais que embasaram a resposta (arquivo + página, deduplicada).
- `POST /consultoria/chat` devolve `sources` preenchido de verdade, no lugar do `[]` hardcoded.
- Frontend (`useChat.ts`, `ChatMessage.tsx`) passa a renderizar as fontes recebidas.
- **Não muda** a lógica de recuperação/geração em si — só passa adiante uma informação que já existe e hoje é descartada.

## Capabilities

### Modified Capabilities
- `rag-chat-vector-search`: o requisito já aceito de atribuição de fontes passa a corresponder ao comportamento real (hoje o código o viola).

## Impact

- `backend/app/services/rag_service.py`: `get_answer`, nó `generate`/estado do grafo (precisa carregar os docs recuperados, não só o texto achatado, até o retorno final).
- `backend/app/main.py`: endpoint `/consultoria/chat`.
- `frontend/hooks/useChat.ts`, `frontend/components/ChatMessage.tsx`.
- Nenhuma mudança de schema — os dados já existem no banco.
