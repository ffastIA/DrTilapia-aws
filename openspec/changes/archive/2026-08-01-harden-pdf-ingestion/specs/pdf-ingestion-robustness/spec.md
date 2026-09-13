## ADDED Requirements

### Requirement: The original source PDF is persisted after ingestion
Ingesting a PDF SHALL upload the original file to durable storage, so it remains available for reprocessing or audit after the temporary upload file is discarded.

#### Scenario: Original file is retrievable after ingestion
- **WHEN** a PDF has been successfully ingested
- **THEN** the original file bytes can be retrieved from storage using the recorded `storage_bucket`/`storage_path`, without depending on the uploader's local copy

### Requirement: Document identity is derived from content, not filename
The system SHALL identify a document by a hash of its content, so that two different files with the same name are not treated as duplicates and the same file re-uploaded under a different name is recognized as already ingested.

#### Scenario: Same content, different filename is recognized as duplicate
- **WHEN** a file with identical content to an already-ingested document is uploaded under a different filename
- **THEN** the system recognizes it as already ingested rather than creating a duplicate entry

#### Scenario: Different content, same filename is not treated as duplicate
- **WHEN** a file with different content from an already-ingested document is uploaded under the same filename
- **THEN** the system ingests it as a distinct document rather than rejecting it as a duplicate

### Requirement: A failed ingestion leaves no partial state
If ingestion fails after any data has been written, the system SHALL remove what was already written for that document before reporting the failure, and SHALL allow a subsequent ingestion attempt for the same document to proceed rather than being blocked by leftover partial state.

#### Scenario: Partial failure is cleaned up
- **WHEN** ingestion fails after some chunks have already been written
- **THEN** those chunks are removed before the failure is reported to the caller

#### Scenario: Retry after partial failure succeeds
- **WHEN** a document that previously failed partway through ingestion is submitted again
- **THEN** the system does not reject it as already existing, and ingestion can complete normally

### Requirement: Ingestion does not block concurrent requests
Processing-intensive stages of ingestion (including OCR) SHALL run without blocking the server's event loop, so that other requests are served normally while a long ingestion is in progress.

#### Scenario: Chat remains responsive during a long ingestion
- **WHEN** a document requiring OCR is being ingested
- **THEN** concurrent chat requests continue to receive timely responses
