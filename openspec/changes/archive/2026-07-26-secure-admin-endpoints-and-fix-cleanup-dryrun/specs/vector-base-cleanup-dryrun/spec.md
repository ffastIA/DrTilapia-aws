## ADDED Requirements

### Requirement: Cleanup dry-run must not delete any data
When `POST /admin/vector-base/cleanup` is invoked in dry-run mode (`dry_run=true`, or `dry_run` omitted and `confirmation_phrase` not equal to `"CONFIRMADO"`), the system SHALL NOT delete any row from the `documents` table, any row from `ingestion_logs`/`rag_ingestion_logs`, or any object from Storage. The system SHALL instead compute and return the counts of what would be deleted if the operation were executed for real.

#### Scenario: Simulated cleanup does not delete documents
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true` (or `confirmation_phrase="SIMULACAO"`) while the vector base contains one or more indexed files
- **THEN** the response reports the number of files/documents/storage objects that would be deleted, and a subsequent `GET /admin/vector-base/files` call still returns the same files, unchanged

#### Scenario: Simulated cleanup does not touch storage or ingestion logs
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true` for a vector base containing files with associated Storage objects and ingestion log entries
- **THEN** no Storage object is removed and no row is deleted from `ingestion_logs`/`rag_ingestion_logs`

#### Scenario: Simulated cleanup response is explicitly labeled
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `dry_run=true`
- **THEN** the response body indicates that the operation was a simulation (e.g. a `dry_run: true` field and a message clarifying no data was deleted), distinct from the response returned for a real execution

### Requirement: Confirmed cleanup still performs a real deletion
When `POST /admin/vector-base/cleanup` is invoked with an explicit confirmation (`dry_run=false` with `confirmation_phrase="CONFIRMADO"`), the system SHALL perform the real deletion of all valid files' documents, associated ingestion log entries, and Storage objects, exactly as before this change.

#### Scenario: Confirmed cleanup deletes all data
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `confirmation_phrase="CONFIRMADO"` and `dry_run=false` while the vector base contains one or more indexed files
- **THEN** all corresponding rows in `documents`, all corresponding rows in `ingestion_logs`/`rag_ingestion_logs`, and all corresponding Storage objects are deleted, and a subsequent `GET /admin/vector-base/files` call returns an empty list

#### Scenario: Confirmed cleanup response is explicitly labeled
- **WHEN** a client calls `POST /admin/vector-base/cleanup` with `confirmation_phrase="CONFIRMADO"` and `dry_run=false`
- **THEN** the response body indicates that the operation was a real execution (e.g. a `dry_run: false` field), distinct from the simulation response
