# auth-endpoint-hardening Specification

## Purpose
TBD - created by archiving change auth-endpoint-hardening. Update Purpose after archive.

## Requirements

### Requirement: Login is rate-limited against rapid repeated attempts
`POST /auth/login` SHALL reject requests beyond a configured rate limit per client IP with HTTP 429, rather than processing every attempt regardless of frequency.

#### Scenario: Excessive attempts from one IP are throttled
- **WHEN** a single client IP makes more login attempts than the configured limit within the configured time window
- **THEN** subsequent attempts within that window receive `429 Too Many Requests` instead of being evaluated against stored credentials

#### Scenario: Normal login usage is unaffected
- **WHEN** a client makes login attempts within the configured rate limit
- **THEN** each attempt is evaluated normally (success or credential-based failure), with no throttling applied

### Requirement: Interactive API documentation is disabled by default outside development
The FastAPI application SHALL NOT expose `/docs`, `/redoc`, or `/openapi.json` unless explicitly running in a development environment, as determined by an environment variable.

#### Scenario: Docs are unreachable without explicit development configuration
- **WHEN** the backend starts with the environment variable that designates development mode absent or set to a non-development value
- **THEN** `GET /docs`, `GET /redoc`, and `GET /openapi.json` all respond `404`

#### Scenario: Docs remain available in explicit development mode
- **WHEN** the backend starts with the environment variable set to designate development mode
- **THEN** `GET /docs`, `GET /redoc`, and `GET /openapi.json` respond as before this change
