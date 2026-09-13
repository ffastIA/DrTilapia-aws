## ADDED Requirements

### Requirement: Initial retrieval searches with multiple phrasings of the question
When multi-query expansion is enabled, the system SHALL generate multiple distinct query variants for the initial retrieval attempt — at minimum the original question, an existing synonym/bilingual expansion, and a technical-register paraphrase — and SHALL run a separate vector similarity search for each variant, instead of relying on a single combined query string.

#### Scenario: A colloquially-phrased question is rescued by a technical paraphrase
- **WHEN** a user asks an in-corpus question using informal or imprecise vocabulary, such that the raw embedding of the question as typed does not clear the refusal floor
- **THEN** if any generated variant (e.g. the technical-register paraphrase) produces a candidate that clears the refusal floor, that candidate is included in the retrieval result

#### Scenario: Multi-query expansion can be disabled without a code change
- **WHEN** multi-query expansion needs to be turned off (e.g. to isolate a regression or control cost)
- **THEN** it can be disabled through configuration, reverting to single-query retrieval, without modifying retrieval code

### Requirement: Multi-query results are merged by maximum similarity, preserving calibration
Results from the per-variant vector searches SHALL be merged into a single ranked candidate list by keeping, for each unique chunk, the highest raw cosine similarity it received across all variants — not by rank-fusion — so that the existing similarity-calibrated refusal floor and context-selection thresholds apply unchanged to the merged list.

#### Scenario: The refusal floor is evaluated against the best variant's similarity
- **WHEN** a chunk is retrieved by multiple query variants with different similarity scores
- **THEN** the merged candidate list records that chunk's similarity as the maximum of those scores, and the refusal floor and context-selection logic operate on that value exactly as they do for single-query retrieval

#### Scenario: Multi-query fusion does not require recalibrating existing thresholds
- **WHEN** multi-query expansion is enabled
- **THEN** the refusal floor, context relative margin, absolute floor, minimum-fill, and maximum-chunk thresholds all keep their existing calibrated values, unchanged by this feature

### Requirement: Semantic context grading still runs whenever any variant clears the refusal floor
The context-sufficiency judgment (`grade_context`) SHALL be invoked normally whenever the merged multi-query retrieval produces a non-empty result, so that a question rescued by multi-query expansion still passes through the same strict sufficiency judge used for single-query retrieval, rather than bypassing it.

#### Scenario: A rescued question is still subject to the sufficiency judge
- **WHEN** multi-query expansion produces context that clears the refusal floor for a question that would have been refused under single-query retrieval
- **THEN** the sufficiency judge evaluates that context before an answer is generated, and can still classify it as insufficient if the context does not genuinely address the question

### Requirement: Multi-query expansion does not alter the retry/reformulation path
The single rule-based reformulation retry (used when the initial retrieval is judged insufficient) SHALL remain unchanged by this feature — it continues to use rule-based query rewriting rather than generating additional LLM-based variants, regardless of whether multi-query expansion is enabled for the initial attempt.

#### Scenario: Reformulation after an insufficient multi-query attempt uses the existing rule-based rewrite
- **WHEN** the initial multi-query retrieval attempt is judged insufficient
- **THEN** the single reformulation retry proceeds exactly as it does today, using rule-based query rewriting, without generating further LLM-based query variants
