# rag-self-correction Specification

## Purpose
TBD - created by archiving change add-rag-self-correction-loop. Update Purpose after archive.
## Requirements
### Requirement: Context sufficiency is judged before generation
Before invoking the answer-generation model, the system SHALL assess whether the retrieved context is sufficient, partially sufficient, or insufficient to answer the question, using a judgment that considers the semantic relationship between the question and the context rather than relying solely on a numeric similarity score.

#### Scenario: Sufficient context proceeds directly to generation
- **WHEN** the retrieved context is judged sufficient to answer the question
- **THEN** the system proceeds to generate an answer without any additional retrieval attempt

#### Scenario: A context judged insufficient does not proceed to generation unchanged
- **WHEN** the retrieved context is judged insufficient to answer the question
- **THEN** the system does not generate an answer from that context as-is; it either attempts one reformulated retrieval or declines

### Requirement: Insufficient context triggers at most one reformulated retrieval attempt
When the initial context is judged insufficient, the system SHALL reformulate the retrieval query and attempt retrieval exactly once more before declining, and that reformulated attempt SHALL be subject to the same refusal floor and context-selection rules as the initial attempt.

#### Scenario: A reformulated retrieval that succeeds proceeds to generation
- **WHEN** a reformulated retrieval attempt produces context judged sufficient or partially sufficient
- **THEN** the system proceeds to generate an answer from that context

#### Scenario: A reformulated retrieval that still fails results in refusal
- **WHEN** a reformulated retrieval attempt still produces context judged insufficient
- **THEN** the system declines to answer rather than attempting retrieval a third time

#### Scenario: The reformulated attempt does not bypass the refusal floor
- **WHEN** a reformulated retrieval attempt's best-matching candidate falls below the configured refusal floor
- **THEN** the system declines, exactly as it would for a first attempt falling below the same floor — the reformulated attempt applies no relaxed or bypassed threshold

### Requirement: Numeric claims in generated answers are verified against the supplied context
After an answer is generated, the system SHALL check that every numeric value asserted in the answer is present in the context that was supplied to the generation call, using a deterministic comparison rather than a model judgment.

#### Scenario: An answer with all numbers grounded in context passes verification
- **WHEN** every numeric value in a generated answer is present in the supplied context (accounting for equivalent numeric formatting)
- **THEN** the answer passes numeric verification and is returned as-is

#### Scenario: An answer with an unsupported number triggers one corrective regeneration
- **WHEN** a generated answer contains a numeric value that does not appear anywhere in the supplied context
- **THEN** the system regenerates the answer exactly once, with an instruction identifying the specific unsupported value(s)

#### Scenario: A second unsupported-number finding does not trigger indefinite regeneration
- **WHEN** the corrective regeneration still contains a numeric value not found in the supplied context
- **THEN** the system returns that regenerated answer rather than regenerating again, so that the correction loop is bounded

### Requirement: Retry attempts never bypass the refusal floor or high-confidence context selection rules
Any retry or reformulation path in the answer pipeline SHALL apply the same refusal floor and context-selection rules as the initial attempt. No retry path SHALL disable, relax, or bypass the refusal floor as a way to produce an answer that the initial attempt would not have produced.

#### Scenario: A retry cannot rescue a below-floor question
- **WHEN** both the initial and any reformulated retrieval attempt for a question fall below the refusal floor
- **THEN** the system declines to answer, at no point generating a response from context that never cleared the floor

