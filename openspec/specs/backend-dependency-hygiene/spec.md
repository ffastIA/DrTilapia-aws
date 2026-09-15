# backend-dependency-hygiene Specification

## Purpose
TBD - created by archiving change backend-dependency-hygiene. Update Purpose after archive.

## Requirements

### Requirement: No pinned dependency carries a known unpatched CVE
`backend/requirements.txt` SHALL NOT pin any package version with a publicly known CVE for which a fixed version is available and compatible with the codebase.

#### Scenario: python-multipart is at a patched version
- **WHEN** `backend/requirements.txt` is inspected
- **THEN** `python-multipart` is specified at a version `>=0.0.18` (the version that fixes CVE-2024-53981), not `0.0.9`

### Requirement: No unused dependency is listed
`backend/requirements.txt` SHALL NOT list a package that is not imported anywhere in the backend codebase (application code or operational scripts).

#### Scenario: Source audit finds no import of a removed package
- **WHEN** the backend source tree is searched for `import jose`, `from jose`, `import bcrypt`, `import sqlalchemy`/`from sqlalchemy`, or `import sqlmodel`/`from sqlmodel`
- **THEN** no occurrence is found, and none of `python-jose`, `bcrypt`, `sqlalchemy`, `sqlmodel` appears in `backend/requirements.txt`
