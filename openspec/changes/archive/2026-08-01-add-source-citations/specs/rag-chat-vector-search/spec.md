## MODIFIED Requirements

### Requirement: Source attribution works for documents lacking top-level file id/name
When building sources for the chat answer, the backend SHALL resolve each chunk's `original_file_id`/`original_file_name` from the top-level field if present, falling back to the same field inside `metadata` when the top-level field is absent, and SHALL return this information to the caller as part of the chat response rather than an empty placeholder.

#### Scenario: Legacy document without top-level file fields still shows a source
- **WHEN** a matched chunk's row has `original_file_name` as `NULL` at the top level but has `metadata.original_file_name` set
- **THEN** the chat response's `sources` list shows the file name from `metadata`, not an empty/unknown value

#### Scenario: An answerable question returns real sources
- **WHEN** the system generates an answer grounded in retrieved chunks
- **THEN** the chat response's `sources` field lists the distinct source documents (and the page range within each) that contributed to that answer, instead of an empty list

#### Scenario: A refusal returns no sources
- **WHEN** the system declines to answer due to insufficient relevant context
- **THEN** the chat response's `sources` field is empty, not a fabricated or misleading source list
