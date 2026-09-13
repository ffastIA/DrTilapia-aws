## ADDED Requirements

### Requirement: Login does not downgrade the privileged backend client
Authenticating an end user via `POST /auth/login` SHALL NOT change the effective authorization privilege used by the backend's service-role Supabase client (`supabase_admin`) for any other request, concurrent or subsequent.

#### Scenario: Admin lookup succeeds after another user logs in
- **WHEN** a regular (non-admin) user logs in via `POST /auth/login`, and immediately afterward a request is made to an `/admin/*` endpoint using a valid admin access token
- **THEN** the admin request succeeds (the backend correctly finds the admin's role in `public.users`), not a 401 caused by the previous user's login having downgraded the shared client's privilege

#### Scenario: Repeated logins return a consistent role
- **WHEN** the same user logs in via `POST /auth/login` multiple times in a row, interleaved with other users logging in
- **THEN** every login response for that user reports the same, correct `role` value from `public.users`, regardless of how many other logins happened in between

### Requirement: Service-role client is never used for end-user sign-in
The backend SHALL use a Supabase client scoped to the anon/default key (not the service-role client) for `sign_in_with_password` calls made on behalf of end users.

#### Scenario: Login uses the anon-scoped client
- **WHEN** `POST /auth/login` authenticates a user
- **THEN** the `sign_in_with_password` call is made through a client scoped to the anon/default key, not through the service-role client (`supabase_admin`)

### Requirement: Login uses a per-request client with no shared mutable auth state
The backend SHALL construct a fresh, per-request Supabase client for `sign_in_with_password` calls, rather than reusing any shared, module-level singleton client for this purpose. No client used for end-user sign-in may be reused as a data-access client (`.table()`, `.storage()`, `.rpc()`) anywhere else in the backend.

#### Scenario: Concurrent logins by different users don't share mutable state
- **WHEN** two different users log in via `POST /auth/login` at effectively the same time (interleaved requests)
- **THEN** each login's response reflects only that user's own credentials and session — neither login's internal client state is shared with, or overwritten by, the other's

#### Scenario: No other backend operation depends on the login client's identity
- **WHEN** the codebase is searched for usages of the client used to perform `sign_in_with_password`
- **THEN** that client is used for no other purpose (no `.table()`, `.storage()`, or `.rpc()` calls depend on its authorization state)
