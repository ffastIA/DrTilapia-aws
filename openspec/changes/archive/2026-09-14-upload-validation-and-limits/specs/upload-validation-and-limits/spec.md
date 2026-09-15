## ADDED Requirements

### Requirement: Uploads are size-limited before being fully materialized in memory
Every file upload endpoint (`/admin/upload`, `/videos/upload`, `/fish/images/upload`) SHALL enforce a maximum size per upload type, checked incrementally while reading the request body, rejecting with HTTP 413 before the entire file is read into memory.

#### Scenario: Oversized upload is rejected
- **WHEN** a client uploads a file larger than the configured limit for that endpoint's type
- **THEN** the server responds with `413 Payload Too Large` and does not pass the file to downstream processing (PDF ingestion, video storage, or image analysis)

#### Scenario: Upload within the limit is unaffected
- **WHEN** a client uploads a file at or below the configured limit
- **THEN** the upload proceeds exactly as before this change

### Requirement: File type is validated from content, not filename extension
Every file upload endpoint SHALL determine the file's actual type by inspecting its content (magic bytes/signature), and SHALL reject the upload with HTTP 400 when the detected type does not match a type allowed for that endpoint, regardless of the filename's extension.

#### Scenario: Renamed file is rejected
- **WHEN** a client uploads a file whose content does not match any allowed type for that endpoint but whose filename carries an allowed extension (e.g. an executable renamed to `.pdf`)
- **THEN** the server responds with `400` and does not process or persist the file

#### Scenario: Genuine file of an allowed type is accepted
- **WHEN** a client uploads a file whose content matches an allowed type for that endpoint
- **THEN** the upload proceeds regardless of minor filename/extension mismatches

### Requirement: Persisted filenames are sanitized
The original filename supplied by the client SHALL be sanitized (normalized, restricted to a safe character set, length-bounded) before being persisted as metadata or rendered in any UI, without altering how the file's storage path is generated.

#### Scenario: Filename with unsafe characters is sanitized
- **WHEN** a client uploads a file whose original filename contains control characters, HTML-significant characters, or exceeds a reasonable length
- **THEN** the value persisted and later displayed is the sanitized form, not the raw client-supplied string
