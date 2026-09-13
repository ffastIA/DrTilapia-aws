## MODIFIED Requirements

### Requirement: Cleanup dry-run must not delete any data
When `POST /admin/vector-base/cleanup` is invoked in dry-run mode (`dry_run=true` and `confirmation_phrase="SIMULACAO"`), the system SHALL NOT delete any row from the `documents` table, any row from `ingestion_logs`/`rag_ingestion_logs`, or any object from Storage. The system SHALL instead compute and return the **actual** counts of what would be deleted if the operation were executed for real, by reading current data (not a fixed/placeholder value).

#### Scenario: Simulated cleanup does not delete documents
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true` and `confirmation_phrase="SIMULACAO"` while the vector base contains one or more indexed files
- **THEN** the response reports the real number of files/documents/storage objects/ingestion-log rows that would be deleted (not a hardcoded value), and a subsequent `GET /admin/vector-base/files` call still returns the same files, unchanged

#### Scenario: Simulated cleanup does not touch storage or ingestion logs
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true` for a vector base containing files with associated Storage objects and ingestion log entries
- **THEN** no Storage object is removed and no row is deleted from `ingestion_logs`/`rag_ingestion_logs` — any log-count computation is read-only

#### Scenario: Simulated cleanup response is explicitly labeled
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true`
- **THEN** the response body includes `dry_run: true` and a message clarifying no data was deleted, distinct from the response returned for a real execution

#### Scenario: Simulation reflects an empty base accurately
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true` while the vector base contains no files
- **THEN** the response reports zero for all counts, genuinely computed (not merely because the value is hardcoded)

### Requirement: Confirmed cleanup still performs a real deletion
When `POST /admin/vector-base/cleanup` is invoked with the backend's real confirmation phrase (currently `CONFIRMAR_LIMPEZA_TOTAL`, via `confirmation_phrase="CONFIRMADO"` normalized by the request schema, or any value that resolves to it), the system SHALL perform the real deletion of all valid files' documents, associated ingestion log entries, and Storage objects, exactly as before this change.

#### Scenario: Confirmed cleanup deletes all data
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=false` and a confirmation phrase that resolves to `CONFIRMAR_LIMPEZA_TOTAL`, while the vector base contains one or more indexed files
- **THEN** all corresponding rows in `documents`, all corresponding rows in `ingestion_logs`/`rag_ingestion_logs`, and all corresponding Storage objects are deleted, and a subsequent `GET /admin/vector-base/files` call returns an empty list

#### Scenario: Confirmed cleanup response is explicitly labeled
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=false` and a valid confirmation phrase
- **THEN** the response body includes `dry_run: false`, distinct from the simulation response
