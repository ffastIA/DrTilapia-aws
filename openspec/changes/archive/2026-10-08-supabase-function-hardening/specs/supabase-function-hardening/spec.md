## ADDED Requirements

### Requirement: Privileged functions are not executable by unauthorized roles
Any `SECURITY DEFINER` Postgres function not required as a public RPC endpoint SHALL NOT be executable by the `anon` or `authenticated` roles.

#### Scenario: rls_auto_enable is not callable by ordinary users
- **WHEN** a request to `POST /rest/v1/rpc/rls_auto_enable` is made using an `anon` or `authenticated`-scoped API key/token
- **THEN** the call fails due to insufficient privilege, rather than executing with the function owner's privileges

### Requirement: RAG pipeline functions have a fixed search_path
`insert_vector_batch` and `rpc_vector_search` SHALL execute with an explicitly fixed `search_path`, not the caller's session-dependent default.

#### Scenario: Function definition declares search_path
- **WHEN** the definition of `insert_vector_batch` or `rpc_vector_search` is inspected (e.g. via `pg_proc`/`\df+`)
- **THEN** it shows an explicit `SET search_path` configuration rather than none

### Requirement: Leaked password protection is enabled
The Supabase Auth configuration for this project SHALL have leaked-password protection (HaveIBeenPwned check) enabled.

#### Scenario: Signup/password-change with a known-leaked password is rejected
- **WHEN** a user attempts to sign up or change their password to a value present in the HaveIBeenPwned leaked-password corpus
- **THEN** the request is rejected by Supabase Auth rather than succeeding
