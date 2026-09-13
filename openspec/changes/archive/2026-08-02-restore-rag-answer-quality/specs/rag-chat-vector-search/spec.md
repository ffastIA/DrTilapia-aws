## MODIFIED Requirements

### Requirement: Similarity threshold filtering happens after retrieval
Since `rpc_vector_search` does not accept a similarity-threshold parameter, the backend SHALL request enough candidate matches from the function and then select the answer context by rank, not by a single confidence threshold applied as an all-or-nothing gate. The selected context SHALL always fall between a configured minimum and maximum chunk count (unless the question is refused), bounded by a total character budget, so that context size never collapses to a handful of chunks nor grows to consume most of the retrieved candidate pool. The refusal floor below which the system declines to answer SHALL remain a separate, lower-priority check than the ranking window.

#### Scenario: A weakly-matching question still receives a stable-sized context
- **WHEN** the best-matching candidate for a question falls below the high-confidence threshold but at or above the refusal floor
- **THEN** the selected context contains at least the configured minimum number of chunks, not only the single best match

#### Scenario: A strongly-matching question does not receive a flooded context
- **WHEN** many candidates for a question exceed the refusal floor
- **THEN** the selected context is capped at the configured maximum chunk count and character budget, not the full candidate pool

#### Scenario: Context size adapts to configuration, not code changes
- **WHEN** the minimum chunk count, maximum chunk count, or character budget needs adjustment based on measured evaluation results
- **THEN** the adjustment is made through configuration, not a code change to the selection logic

### Requirement: Source attribution works for documents lacking top-level file id/name
When building sources for the chat answer, the backend SHALL resolve each chunk's `original_file_id`/`original_file_name` from the top-level field if present, falling back to the same field inside `metadata` when the top-level field is absent, and SHALL return this information to the caller as part of the chat response rather than an empty placeholder. Only chunks that were actually included in the context supplied to the answer-generation call SHALL be reflected in the sources.

#### Scenario: Legacy document without top-level file fields still shows a source
- **WHEN** a matched chunk's row has `original_file_name` as `NULL` at the top level but has `metadata.original_file_name` set
- **THEN** the chat response's `sources` list shows the file name from `metadata`, not an empty/unknown value

#### Scenario: An answerable question returns real sources with precise pages
- **WHEN** the system generates an answer grounded in retrieved chunks
- **THEN** the chat response's `sources` field lists the distinct source documents that contributed to that answer, each with the specific pages the used chunks came from — not a min/max span covering every page between the lowest and highest page seen across all retrieved candidates

#### Scenario: A refusal returns no sources
- **WHEN** the system declines to answer due to insufficient relevant context
- **THEN** the chat response's `sources` field is empty, not a fabricated or misleading source list

#### Scenario: Supplementary chunks do not introduce new cited documents on their own
- **WHEN** a chunk was added to the context through a supplementary mechanism unrelated to the question's semantic match (rather than through ranked retrieval)
- **THEN** that chunk's source document is not added to the citation list unless a chunk from the same document was already included through ranked retrieval

## ADDED Requirements

### Requirement: Answers are composed as continuous prose
The system SHALL generate answers as continuous prose organized in paragraphs, not as a fixed set of mandatory labeled sections. Bulleted or numbered lists SHALL be used only where they aid readability for genuine enumerations, never as a required structural template applied regardless of content.

#### Scenario: An answer with no numeric findings is not padded with empty sections
- **WHEN** the retrieved context contains no data relevant to a quantitative aspect of the question
- **THEN** the answer omits that aspect in prose or addresses it in a sentence, rather than presenting a labeled section containing a placeholder value

#### Scenario: An answer covering multiple distinct findings uses prose, with lists only for genuine enumeration
- **WHEN** an answer addresses a question with several related findings
- **THEN** the findings are woven into paragraph prose, and a list is used only where the content is a genuine sequence or enumeration that benefits from visual separation, not as a mandatory layout

### Requirement: The system declines when it determines mid-generation that it cannot answer
In addition to declining before generation when no chunk meets the refusal floor, the system SHALL provide a way for the answer-generation step itself to signal that the supplied context — though present — is insufficient to answer the question, and SHALL convert that signal into the same honest refusal response used elsewhere, without exposing the raw signal to the user.

#### Scenario: Present but insufficient context still results in a clean refusal
- **WHEN** the context passed to answer generation is non-empty but does not contain the information needed to answer the question
- **THEN** the user-visible response is the system's standard refusal message, not a partial, padded, or speculative answer

#### Scenario: A refusal produced this way carries no sources
- **WHEN** the answer-generation step signals that it cannot answer from the supplied context
- **THEN** the response's `sources` field is empty

### Requirement: Partial-confidence answers include an explicit caveat
When the best-matching retrieved content falls short of high confidence but still clears the refusal floor, the system SHALL still attempt to answer, and SHALL include an explicit, natural-language signal of reduced confidence in the answer rather than presenting the answer with the same certainty as a high-confidence match.

#### Scenario: A partial-confidence answer is distinguishable from a confident one
- **WHEN** the system answers a question whose best-matching content is in the intermediate confidence range (above the refusal floor, below the high-confidence threshold)
- **THEN** the answer's opening signals the reduced confidence in natural language, rather than reading identically to an answer grounded in strong matches

#### Scenario: A high-confidence answer is not caveated unnecessarily
- **WHEN** the system answers a question whose best-matching content is at or above the high-confidence threshold
- **THEN** the answer does not include a confidence caveat
