# rag-ingestion-quality Specification

## Purpose
TBD - created by archiving change restore-embedding-and-chunking-quality. Update Purpose after archive.
## Requirements
### Requirement: The embedding model is explicit and configurable
The system SHALL specify its embedding model explicitly rather than relying on a library default, and the model SHALL be configurable without code changes.

#### Scenario: Model is stated in code, not inherited from a default
- **WHEN** the embedding client is constructed
- **THEN** the embedding model is passed explicitly

#### Scenario: Model is overridable by configuration
- **WHEN** an operator sets the embedding model configuration to a different supported model
- **THEN** the system uses that model without any code change

#### Scenario: Effective model is observable at startup
- **WHEN** the RAG service starts
- **THEN** it logs the embedding model actually in use, together with the chunk size and overlap in effect

### Requirement: Embedding dimensionality matches the stored vector column
The embeddings produced at ingestion and at query time SHALL have the dimensionality declared by the vector column, and both paths SHALL use the same model and dimensionality.

#### Scenario: Stored embeddings match the column dimension
- **WHEN** documents are ingested
- **THEN** every stored embedding has the dimensionality declared by the vector column

#### Scenario: Query embedding matches stored embeddings
- **WHEN** a user question is embedded for search
- **THEN** it is produced by the same model and dimensionality as the stored embeddings

### Requirement: Chunk size and overlap are configurable and suited to retrieval
Chunk size and overlap SHALL be configurable without code changes, and SHALL be sized so that a chunk represents a focused passage rather than a broad span of mixed subjects.

#### Scenario: Chunking parameters are overridable by configuration
- **WHEN** an operator changes the chunk size or overlap configuration
- **THEN** subsequent ingestions use the new values without any code change

#### Scenario: A single ingestion path defines the parameters
- **WHEN** any ingestion or reindexing path splits a document
- **THEN** it uses the same configured chunk size and overlap as every other path

### Requirement: Chunking is continuous across page boundaries
Document text SHALL be split as a continuous sequence, so that a passage spanning a page break can be contained in a single chunk and the configured overlap applies across page boundaries.

#### Scenario: Passage spanning a page break stays retrievable
- **WHEN** a sentence or table begins on one page and continues on the next
- **THEN** at least one chunk contains that passage without being cut at the page boundary

#### Scenario: Overlap crosses page boundaries
- **WHEN** consecutive chunks are produced across a page break
- **THEN** the configured overlap is present between them, as it is between chunks within a page

### Requirement: Chunks carry position and page provenance
Each stored chunk SHALL record its ordinal position within its source document and the page or page range it came from, in both the chunk metadata and queryable columns.

#### Scenario: Chunk records its ordinal position
- **WHEN** a document is ingested
- **THEN** each of its chunks carries an index identifying its position within that document

#### Scenario: Chunk records its page provenance
- **WHEN** a chunk is stored
- **THEN** it carries the page (or page range) of the source document it was extracted from

#### Scenario: Provenance is queryable without parsing metadata
- **WHEN** the administration layer reads a chunk's page and position
- **THEN** it obtains them from queryable columns rather than receiving null

### Requirement: Retrieval quality improves against the recorded baseline
After re-ingestion with the new configuration, retrieval of the expected passages SHALL improve relative to the baseline recorded before this change.

#### Scenario: Measured improvement over baseline
- **WHEN** the evaluation set is run after re-ingestion and compared to the pre-change baseline
- **THEN** the retrieval metrics show an improvement rather than a regression

#### Scenario: Absence of improvement is treated as a failure
- **WHEN** the post-change evaluation shows no improvement over the baseline
- **THEN** the change is treated as unsuccessful and the configuration is reconsidered, rather than accepted on the assumption that it must be better

