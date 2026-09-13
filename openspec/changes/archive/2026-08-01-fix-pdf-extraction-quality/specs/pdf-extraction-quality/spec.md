## ADDED Requirements

### Requirement: Incomplete extraction is detected, not only absent extraction
Extraction validation SHALL detect text that was extracted incompletely — structure present but content missing — and not rely solely on text being absent or having broken character encoding.

#### Scenario: Page with structure but no content is rejected
- **WHEN** a page of a text-bearing document yields only section headings, table headers without data rows, and isolated one-character tokens
- **THEN** the extraction is judged inadequate for that page

#### Scenario: Encoding-broken text is still detected
- **WHEN** extracted text contains a high proportion of undecodable characters
- **THEN** the extraction is judged inadequate, as before this change

#### Scenario: Well-extracted document is not rejected
- **WHEN** a document is extracted with prose content at normal density
- **THEN** the extraction is judged adequate and no rescue is attempted

### Requirement: Extraction quality is judged over the whole document
Extraction quality SHALL be assessed across the document as a whole, not by individual pages in isolation, so that legitimately sparse pages do not trigger a false failure.

#### Scenario: Isolated sparse page does not fail the document
- **WHEN** a document contains a cover page or a references page with little text, while its remaining pages are dense
- **THEN** the document is judged adequately extracted

#### Scenario: Predominantly sparse document fails
- **WHEN** most pages of a document are sparse relative to what its page count implies
- **THEN** the document is judged inadequately extracted, even if no single page is conclusive on its own

### Requirement: Inadequate extraction triggers the rescue cascade
When extraction is judged inadequate, the system SHALL attempt the alternative extraction methods already available before accepting the result.

#### Scenario: Text-layer failure escalates to alternative extraction
- **WHEN** the primary extraction is judged inadequate
- **THEN** the system attempts the alternative extraction methods in order and uses the first result judged adequate

#### Scenario: Adequate result stops the cascade
- **WHEN** an earlier extraction method produces an adequate result
- **THEN** later, more expensive methods are not attempted

### Requirement: Persistently inadequate extraction fails visibly
If no extraction method yields adequate quality, ingestion SHALL fail with an explicit reason and SHALL NOT store any chunk from that document.

#### Scenario: Unrescuable document is rejected
- **WHEN** every extraction method yields inadequate quality for a document
- **THEN** ingestion reports a failure identifying extraction quality as the cause

#### Scenario: No partial content is stored on failure
- **WHEN** ingestion fails due to extraction quality
- **THEN** no chunk from that document is present in the vector base

### Requirement: Extraction method and quality are recorded
Every ingested document SHALL record which extraction method produced its text and the quality measurements that justified accepting it.

#### Scenario: Successful extraction records its method
- **WHEN** a document is ingested successfully by any extraction method
- **THEN** its stored chunks record which method produced the text, including when the primary method succeeded

#### Scenario: Quality of an ingested document is auditable afterwards
- **WHEN** an already-ingested document is inspected
- **THEN** the recorded quality measurements allow distinguishing a well-extracted document from a poorly-extracted one, without re-processing the source file

### Requirement: Optical extraction is bounded in cost
Extraction methods that incur per-page API cost SHALL be bounded by a configurable maximum page count, and exceeding it SHALL fail explicitly rather than process a truncated document.

#### Scenario: Document beyond the page limit is refused
- **WHEN** a document requiring per-page optical extraction exceeds the configured page limit
- **THEN** ingestion fails reporting the page limit as the reason

#### Scenario: Truncation is never silent
- **WHEN** the page limit prevents processing an entire document
- **THEN** no partially-processed version of that document is stored as if complete

#### Scenario: Page limit is configurable
- **WHEN** an operator changes the configured page limit
- **THEN** subsequent ingestions honour the new limit without code changes
