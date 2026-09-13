## ADDED Requirements

### Requirement: HTTP clients verify TLS certificates by default
Every `httpx.Client`/`httpx.AsyncClient` instance constructed by the backend for outbound calls to Supabase or OpenAI SHALL verify the server's TLS certificate unless a CA bundle override is explicitly configured via environment variable.

#### Scenario: No CA override configured
- **WHEN** the backend starts with no `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` environment variable set
- **THEN** all Supabase and OpenAI HTTP clients are constructed with standard certificate verification enabled (`verify=True` equivalent), and a request to a host presenting an untrusted certificate fails with a TLS verification error

#### Scenario: CA override configured for a corporate inspection proxy
- **WHEN** `SSL_CERT_FILE` (or `REQUESTS_CA_BUNDLE`) points to a valid CA bundle file
- **THEN** all Supabase and OpenAI HTTP clients trust that CA bundle for certificate verification, and requests through the corporate TLS-inspection proxy succeed without disabling verification entirely

### Requirement: No HTTP client disables verification unconditionally
No code path in the backend SHALL construct an HTTP client with certificate verification hardcoded to disabled (`verify=False`) as the unconditional default.

#### Scenario: Source audit
- **WHEN** the backend source is searched for `verify=False`
- **THEN** no occurrence is found outside of test fixtures/mocks
