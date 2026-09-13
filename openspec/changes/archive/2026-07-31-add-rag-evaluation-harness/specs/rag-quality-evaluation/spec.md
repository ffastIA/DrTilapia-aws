## ADDED Requirements

### Requirement: Versioned evaluation set
The system SHALL provide a versioned evaluation set ("golden set") of questions derived from the documents actually indexed in the vector base. Each entry SHALL declare the expected source document and the passage(s) that a correct retrieval must return, and SHALL be stored as reviewable data separate from execution code.

#### Scenario: Answerable question declares its expected sources
- **WHEN** an evaluation entry describes a question that the indexed documents can answer
- **THEN** the entry names the source document and the passage(s) that retrieval is expected to return

#### Scenario: Evaluation set is reviewable in isolation
- **WHEN** a question is added, changed, or removed from the evaluation set
- **THEN** the change is visible as a data diff without modifying the evaluation execution code

### Requirement: Out-of-scope questions are part of the evaluation set
The evaluation set SHALL include questions whose answers are absent from the indexed documents, so that the system's ability to decline honestly can be measured.

#### Scenario: Question outside the corpus is marked as such
- **WHEN** the evaluation set contains a question about a subject not covered by any indexed document
- **THEN** that entry is explicitly marked as out-of-scope and its expected outcome is a refusal rather than an answer

### Requirement: Multi-turn follow-up questions are part of the evaluation set
The evaluation set SHALL include multi-turn sequences where a later question is only interpretable given the preceding turns, so that conversational context handling can be measured.

#### Scenario: Follow-up depends on prior turn
- **WHEN** the evaluation set contains a sequence whose second question omits its subject (e.g. "e para alevinos?")
- **THEN** the entry carries the preceding turns, and evaluation of that entry exercises the system with that history

### Requirement: Retrieval quality is measured independently of answer generation
The evaluation SHALL report retrieval metrics — whether the expected passages were retrieved, and at what similarity — without requiring answer generation, so that retrieval changes can be evaluated cheaply.

#### Scenario: Retrieval-only evaluation run
- **WHEN** an evaluation run is executed in retrieval-only mode
- **THEN** it reports, per question, whether the expected passages were retrieved and their similarity scores, and it does not invoke answer generation

#### Scenario: Missed passage is visible
- **WHEN** an expected passage is not present in the retrieved results for a question
- **THEN** the run reports that question as a retrieval miss rather than silently passing

### Requirement: Answer grounding is measured
The evaluation SHALL report, for each generated answer, whether its claims are supported by the retrieved context, using an assessment independent of the model call that produced the answer.

#### Scenario: Ungrounded answer is flagged
- **WHEN** a generated answer asserts information that is absent from the context supplied to it
- **THEN** the run flags that answer as ungrounded

#### Scenario: Grounding assessment is independent of generation
- **WHEN** grounding is assessed for an answer
- **THEN** the assessment is produced by a separate evaluation step, not by the same call that generated the answer

### Requirement: Correct refusal is measured
The evaluation SHALL report whether out-of-scope questions produced a refusal, and SHALL treat an answer to an out-of-scope question as a failure.

#### Scenario: System answers an out-of-scope question
- **WHEN** an out-of-scope question receives a substantive answer instead of a refusal
- **THEN** the run reports that entry as a failure

### Requirement: Runs are recorded with the configuration that produced them
Each evaluation run SHALL be persisted together with the RAG configuration in effect — at minimum the embedding model, chunk size and overlap, similarity threshold, and retrieval `k` — so that two runs can be compared meaningfully.

#### Scenario: Run records its configuration
- **WHEN** an evaluation run completes
- **THEN** its persisted result includes the embedding model, chunk size, chunk overlap, similarity threshold, and retrieval `k` used

#### Scenario: Two runs are compared
- **WHEN** a previous run and a current run are compared
- **THEN** the comparison shows both the metric deltas and the configuration differences between them

### Requirement: Runs report cost and latency
Each evaluation run SHALL report the latency per question and the API cost incurred, so that quality gains can be weighed against their operational cost.

#### Scenario: Run reports its cost
- **WHEN** an evaluation run completes
- **THEN** it reports the total API cost of the run and the per-question latency

### Requirement: A baseline of the current system is recorded
A baseline evaluation run SHALL be recorded against the RAG configuration as it exists before any optimization change, and retained for comparison.

#### Scenario: Baseline exists before optimization
- **WHEN** a subsequent RAG optimization change is evaluated
- **THEN** a stored baseline run produced by the pre-optimization configuration is available to compare against
