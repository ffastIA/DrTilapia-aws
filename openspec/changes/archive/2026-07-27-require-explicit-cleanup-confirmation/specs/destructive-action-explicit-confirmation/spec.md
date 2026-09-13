## ADDED Requirements

### Requirement: Vector base cleanup never executes destructively without explicit confirmation
`POST /admin/vector-base/cleanup` SHALL treat a missing or empty `confirmation_phrase` as a request for a dry-run preview, never as an implicit confirmation of the real destructive cleanup.

#### Scenario: Empty body does not wipe data
- **WHEN** `POST /admin/vector-base/cleanup` is called with an empty body (`{}`) by an admin
- **THEN** the response is a dry-run preview (no `documents`/`ingestion_logs` rows or Storage objects are deleted), not a real execution

#### Scenario: Explicit confirmation still performs the real cleanup
- **WHEN** `POST /admin/vector-base/cleanup` is called with `confirmation_phrase` resolving to the backend's real confirmation phrase (e.g. `"CONFIRMADO"`, normalized internally)
- **THEN** the real cleanup executes exactly as before this change

### Requirement: Individual file deletion requires an explicit confirmation phrase
`POST /admin/vector-base/files/{original_file_id}/delete` SHALL reject the request (validation error, not deletion) when `confirmation_phrase` is missing or empty, rather than defaulting to the real confirmation phrase.

#### Scenario: Empty body does not delete the file
- **WHEN** `POST /admin/vector-base/files/{original_file_id}/delete` is called with an empty body (`{}`) or `confirmation_phrase` omitted
- **THEN** the request is rejected with a validation error, and the file's documents/storage are not deleted

#### Scenario: Admin UI's delete flow still works
- **WHEN** the admin panel's "delete file" action is used
- **THEN** it sends an explicit confirmation phrase and the deletion succeeds exactly as before this change

### Requirement: Confirmation coercion from non-string types is removed
`VectorAdminService.cleanup`/`delete_file` SHALL require an explicit string confirmation phrase from the caller and SHALL NOT synthesize a confirmation phrase from a boolean argument.

#### Scenario: Boolean argument no longer authorizes deletion
- **WHEN** `VectorAdminService.cleanup`/`delete_file` is invoked (at the Python level) with a boolean value in the confirmation-phrase parameter
- **THEN** the call does not resolve to the destructive confirmation phrase as a side effect of the argument's type
