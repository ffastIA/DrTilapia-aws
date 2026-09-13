## ADDED Requirements

### Requirement: Admin endpoints require an authenticated admin user
Every endpoint under the `/admin/*` prefix in the backend (upload, list vector files, get vector file, get vector file chunks, get vector file content, get vector file diagnosis, delete vector file, cleanup vector base, reindex vector base) SHALL require a valid Supabase-issued access token belonging to a user whose `role` in the `users` table is `admin`. Requests without a valid admin token SHALL be rejected before any business logic executes.

#### Scenario: Request without a token
- **WHEN** a client calls any `/admin/*` endpoint without an `Authorization` header
- **THEN** the API responds with HTTP 401 and does not execute the underlying operation (no upload, no read, no delete, no cleanup, no reindex)

#### Scenario: Request with an invalid or expired token
- **WHEN** a client calls any `/admin/*` endpoint with an `Authorization: Bearer <token>` header whose token is invalid or expired
- **THEN** the API responds with HTTP 401 and does not execute the underlying operation

#### Scenario: Request with a valid token for a non-admin user
- **WHEN** a client calls any `/admin/*` endpoint with a valid access token belonging to a user whose `role` is not `admin`
- **THEN** the API responds with HTTP 403 and does not execute the underlying operation

#### Scenario: Request with a valid admin token
- **WHEN** a client calls any `/admin/*` endpoint with a valid access token belonging to a user whose `role` is `admin`
- **THEN** the API executes the underlying operation and returns its normal response

### Requirement: Chat endpoint requires an authenticated user
The `POST /consultoria/chat` endpoint SHALL require a valid Supabase-issued access token belonging to any authenticated user (admin or non-admin). Requests without a valid token SHALL be rejected before the RAG pipeline runs.

#### Scenario: Chat request without a token
- **WHEN** a client calls `POST /consultoria/chat` without an `Authorization` header
- **THEN** the API responds with HTTP 401 and does not invoke the RAG/LLM pipeline

#### Scenario: Chat request with an invalid or expired token
- **WHEN** a client calls `POST /consultoria/chat` with an invalid or expired token
- **THEN** the API responds with HTTP 401 and does not invoke the RAG/LLM pipeline

#### Scenario: Chat request with a valid token for any authenticated user
- **WHEN** a client calls `POST /consultoria/chat` with a valid access token for any user, admin or non-admin
- **THEN** the API invokes the RAG/LLM pipeline and returns the normal chat response
