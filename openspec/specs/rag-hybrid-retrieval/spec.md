# rag-hybrid-retrieval Specification

## Purpose
TBD - created by archiving change add-hybrid-lexical-vector-search. Update Purpose after archive.
## Requirements
### Requirement: Retrieval combines semantic and lexical search
The system SHALL retrieve candidate chunks using both vector similarity search and full-text lexical search, and SHALL combine the two result sets by rank fusion rather than by comparing their raw scores directly, since the two searches produce scores on incompatible scales.

#### Scenario: An exact-term question benefits from lexical matching
- **WHEN** a question's correct answer depends on an exact term, abbreviation, or numeric value that appears verbatim in the corpus but is not the dominant semantic topic of any single chunk
- **THEN** the chunk containing that exact term is ranked among the selected context, having been surfaced by the lexical search leg

#### Scenario: A purely semantic question is not degraded by lexical fusion
- **WHEN** a question has no exact-term dependency and is well-served by vector similarity alone
- **THEN** the fused ranking does not demote the chunks that vector search alone would have selected

#### Scenario: Hybrid retrieval can be disabled without a code change
- **WHEN** hybrid retrieval needs to be turned off (e.g. to isolate a regression)
- **THEN** it can be disabled through configuration, reverting to vector-only retrieval, without modifying retrieval code

### Requirement: The refusal decision is based on vector similarity, not fused rank score
The refusal floor SHALL continue to be evaluated against the raw vector-similarity score of the best-matching candidate, not against the fused rank-fusion score, since the refusal floor was calibrated against vector similarity specifically and a fused score has no equivalent calibration.

#### Scenario: Refusal floor uses cosine similarity even when hybrid retrieval is active
- **WHEN** hybrid retrieval is enabled and a question's best-matching candidate (by cosine similarity) falls below the refusal floor
- **THEN** the system declines to answer, regardless of that candidate's position in the fused ranking

### Requirement: A lexical coverage signal supplements the similarity-based refusal decision
For questions whose best vector-similarity score falls in the intermediate range between the refusal floor and the high-confidence threshold, the system SHALL additionally check whether any discriminative term from the question matches the corpus lexically, and SHALL treat the complete absence of such a match as an additional signal favoring refusal. A term SHALL be considered discriminative only if it does not match a large majority of the corpus.

#### Scenario: No lexical match in the intermediate similarity zone strengthens refusal
- **WHEN** a question's best vector-similarity score is in the intermediate zone and none of its discriminative terms match the corpus lexically
- **THEN** this absence of lexical support is used as an additional signal, alongside the vector-similarity zone, that the question is likely out of scope

#### Scenario: Generic domain terms do not count as discriminative
- **WHEN** a candidate term from the question matches a large majority of the corpus's chunks
- **THEN** that term is excluded from the discriminative-term count used for the lexical coverage signal

#### Scenario: A lexical match does not override a below-floor similarity score
- **WHEN** a question's best vector-similarity score is below the refusal floor, even if discriminative terms from the question match the corpus lexically
- **THEN** the system still declines, since the refusal floor itself is not altered by the lexical signal

