## MODIFIED Requirements

### Requirement: Multi-turn follow-up questions are part of the evaluation set
The evaluation set SHALL include multi-turn sequences where a later question is only interpretable given the preceding turns, so that conversational context handling can be measured. Both retrieval-only and full evaluation modes SHALL exercise that history — a follow-up entry SHALL NOT be evaluated using only the literal text of its final turn.

#### Scenario: Follow-up depends on prior turn
- **WHEN** the evaluation set contains a sequence whose second question omits its subject (e.g. "e para alevinos?")
- **THEN** the entry carries the preceding turns, and evaluation of that entry exercises the system with that history

#### Scenario: Retrieval-only evaluation of a follow-up uses history
- **WHEN** a retrieval-only evaluation run processes an entry that carries prior conversation turns
- **THEN** the retrieval query used is derived from the question together with that history, using the same history-aware retrieval path the production system uses — not the bare final-turn text evaluated in isolation

### Requirement: Answer grounding is measured
The evaluation SHALL report, for each generated answer, whether its claims are supported by the retrieved context, using an assessment independent of the model call that produced the answer. The grounding assessment SHALL be made against the same context that was actually supplied to the answer-generating call, not a context obtained through an independent, differently-configured retrieval.

#### Scenario: Ungrounded answer is flagged
- **WHEN** a generated answer asserts information that is absent from the context supplied to it
- **THEN** the run flags that answer as ungrounded

#### Scenario: Grounding assessment is independent of generation
- **WHEN** grounding is assessed for an answer
- **THEN** the assessment is produced by a separate evaluation step, not by the same call that generated the answer

#### Scenario: Grounding is judged against the context the answer actually saw
- **WHEN** grounding is assessed for a generated answer
- **THEN** the judge receives the exact context that was passed to the generation call for that answer, not context obtained by re-running retrieval with different parameters

### Requirement: Runs are recorded with the configuration that produced them
Each evaluation run's persisted configuration record SHALL include, in one place, the embedding model, chunk size and overlap, similarity threshold, retrieval `k`, and whether LLM-based query expansion was enabled — so that the configuration record alone (not fields scattered elsewhere in the run, and not the run's filename or label) is sufficient to compare two runs meaningfully.

#### Scenario: Run records its configuration
- **WHEN** an evaluation run completes
- **THEN** its persisted configuration record includes the embedding model, chunk size, chunk overlap, similarity threshold, retrieval `k`, and query-expansion setting used, all in the same place

#### Scenario: Two runs are compared
- **WHEN** a previous run and a current run are compared
- **THEN** the comparison shows both the metric deltas and the configuration differences between them, read from each run's recorded configuration

### Requirement: Out-of-scope questions are part of the evaluation set
The evaluation set SHALL include questions whose answers are absent from the indexed documents, so that the system's ability to decline honestly can be measured. This SHALL include both questions that are lexically unrelated to the corpus and questions that share vocabulary, entities, or structure with the corpus but ask about something the corpus does not cover — so that refusal is calibrated against genuinely hard negatives, not only easy ones.

#### Scenario: Question outside the corpus is marked as such
- **WHEN** the evaluation set contains a question about a subject not covered by any indexed document
- **THEN** that entry is explicitly marked as out-of-scope and its expected outcome is a refusal rather than an answer

#### Scenario: Near-miss out-of-scope question shares vocabulary with the corpus
- **WHEN** the evaluation set contains a question that reuses in-corpus terminology, metrics, or named studies but changes the subject (e.g. the correct species, pathogen, or entity swapped for an incorrect one)
- **THEN** that entry is marked out-of-scope with the same refusal expectation as a lexically distant question

## ADDED Requirements

### Requirement: Mention-coverage scoring is robust to equivalent numeric formatting
When comparing a required mention against generated text, the evaluation SHALL treat numerically equivalent representations (decimal comma vs. decimal point, and equivalent digit notations) as matching, so that a factually correct answer is not scored as missing a value due to formatting differences alone.

#### Scenario: Decimal separator does not affect coverage
- **WHEN** a required mention specifies a value using a comma decimal separator (e.g. "64,10%") and the generated answer contains the same value with a period decimal separator (e.g. "64.10%")
- **THEN** the mention is scored as covered

### Requirement: Refusal detection is not coupled to answer length
The evaluation SHALL detect a refusal by matching against the system's actual refusal responses (or an explicit refusal signal from the answer-generation path), not by a length threshold on the answer text.

#### Scenario: A long answer containing a refusal is still detected as a refusal
- **WHEN** a generated answer is longer than any length-based heuristic threshold but matches the system's refusal response or refusal signal
- **THEN** the run classifies that answer as a refusal

#### Scenario: A short substantive answer is not misclassified as a refusal
- **WHEN** a generated answer is short but does not match the system's refusal response or refusal signal
- **THEN** the run does not classify that answer as a refusal solely due to its length

### Requirement: Retrieved context size is measured
Each evaluation run SHALL report, per question and in aggregate, how many chunks were selected into the answer context and how large that context was, so that context starvation and context flooding are visible as explicit metrics rather than only inferable from answer quality.

#### Scenario: Run reports context size distribution
- **WHEN** an evaluation run completes
- **THEN** it reports the mean number of chunks selected per question and the 95th-percentile context size in characters

#### Scenario: Starved questions are identified
- **WHEN** a question's selected context falls below a documented minimum chunk count
- **THEN** the run flags that question in a starvation-rate metric

### Requirement: Answer usefulness is measured independently of context grounding
The evaluation SHALL assess, for each non-refused answer, whether it directly and specifically answers the question — using a judgment that does not have access to the retrieved context — as a signal distinct from grounding. An answer that is fully consistent with a poor or empty context SHALL NOT automatically score well on this measure.

#### Scenario: An empty-skeleton answer scores poorly on usefulness despite being grounded
- **WHEN** a generated answer consists of formal placeholders or explicit "not available" content with no substantive information, and is fully consistent with the (possibly poor) context it was given
- **THEN** the usefulness assessment scores it low, independent of any grounding score for the same answer

#### Scenario: Usefulness judgment does not see the retrieved context
- **WHEN** the usefulness of an answer is assessed
- **THEN** the judge is given only the question and the answer, not the retrieved context

### Requirement: Empty-skeleton responses are measured
The evaluation SHALL detect, per question, whether a non-refused answer matches the pattern of a formal but substantively empty response, and SHALL report an aggregate rate of this pattern across a run.

#### Scenario: Run reports skeleton rate
- **WHEN** an evaluation run completes
- **THEN** it reports the fraction of non-refused answers that matched the empty-skeleton pattern

### Requirement: Citation accuracy is measured
For questions where the evaluation set declares an expected source document, each evaluation run SHALL report whether the answer's cited sources match the expected source, so that over-citation or citation of unused documents is visible as a metric.

#### Scenario: Run reports citation precision
- **WHEN** an evaluation run completes and answers include cited sources
- **THEN** it reports, for questions with a declared expected source, the fraction whose cited sources match that expected source

#### Scenario: Over-citation is visible
- **WHEN** an answer cites source documents beyond the one(s) declared as expected for that question
- **THEN** the run's per-question detail records the discrepancy rather than silently averaging it away
