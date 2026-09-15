## ADDED Requirements

### Requirement: Unexpected server errors never expose internal exception text to the client
When an endpoint catches an exception it did not deliberately raise as a domain-level error (i.e. an `except Exception` boundary around library/infrastructure calls), the HTTP response's error detail SHALL be a generic, stable message and SHALL NOT include the caught exception's string representation.

#### Scenario: A Supabase/PostgREST failure does not leak internal details
- **WHEN** an unexpected exception from the Supabase client (or any other third-party library) is caught by an endpoint's generic exception handler
- **THEN** the HTTP response body contains a generic error message, not the library's exception text (table/column/constraint names, connection details, etc.)

#### Scenario: Deliberate domain errors are unaffected
- **WHEN** an endpoint raises or catches an application-level exception with a message deliberately written for the end user (e.g. "Arquivo inválido")
- **THEN** that message is still returned to the client, unchanged by this requirement

### Requirement: Unexpected errors are logged server-side before responding
Every code path that replaces an exception's text with a generic client-facing message SHALL log the original exception (including a stack trace) on the server before responding.

#### Scenario: Diagnostic information remains available to operators
- **WHEN** an unexpected exception is caught and a generic message is returned to the client
- **THEN** the server's log output for that request includes the full exception type, message, and stack trace
