## ADDED Requirements

### Requirement: Chat endpoint uses the vector search function that actually exists
`POST /consultoria/chat` SHALL retrieve relevant document chunks by calling the `rpc_vector_search` Postgres function (with its actual parameter names), not a nonexistent `match_documents` function.

#### Scenario: Chat request succeeds
- **WHEN** an authenticated user calls `POST /consultoria/chat` with a question
- **THEN** the backend does not raise a 500 error caused by a missing RPC function, and returns a 200 response with an answer

### Requirement: Similarity threshold filtering happens after retrieval
Since `rpc_vector_search` does not accept a similarity-threshold parameter, the backend SHALL request enough candidate matches from the function and then filter them by the configured minimum similarity (0.7) before building the answer context.

#### Scenario: Low-similarity matches are excluded
- **WHEN** `rpc_vector_search` returns candidate chunks with a mix of similarity scores, some below 0.7
- **THEN** only chunks with `similarity >= 0.7` are used to build the answer context

### Requirement: Source attribution works for documents lacking top-level file id/name
When building sources for the chat answer, the backend SHALL resolve each chunk's `original_file_id`/`original_file_name` from the top-level field if present, falling back to the same field inside `metadata` when the top-level field is absent.

#### Scenario: Legacy document without top-level file fields still shows a source
- **WHEN** a matched chunk's row has `original_file_name` as `NULL` at the top level but has `metadata.original_file_name` set
- **THEN** the chat response's `sources` list shows the file name from `metadata`, not an empty/unknown value
