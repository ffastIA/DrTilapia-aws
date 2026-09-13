## MODIFIED Requirements

### Requirement: Login does not downgrade the privileged backend client
Authenticating, registering, or resetting credentials for an end user via any `/auth/*` endpoint (`login`, `signup`, `resend-confirmation`, `forgot-password`, `reset-password`) SHALL NOT change the effective authorization privilege used by the backend's service-role Supabase client (`supabase_admin`) for any other request, concurrent or subsequent.

#### Scenario: Admin lookup succeeds after another user logs in
- **WHEN** a regular (non-admin) user logs in via `POST /auth/login`, and immediately afterward a request is made to an `/admin/*` endpoint using a valid admin access token
- **THEN** the admin request succeeds (the backend correctly finds the admin's role in `public.users`), not a 401 caused by the previous user's login having downgraded the shared client's privilege

#### Scenario: Repeated logins return a consistent role
- **WHEN** the same user logs in via `POST /auth/login` multiple times in a row, interleaved with other users logging in
- **THEN** every login response for that user reports the same, correct `role` value from `public.users`, regardless of how many other logins happened in between

#### Scenario: Admin lookup succeeds after a signup or password reset
- **WHEN** a visitor completes `POST /auth/signup` or `POST /auth/reset-password`, and immediately afterward a request is made to an `/admin/*` endpoint using a valid admin access token
- **THEN** the admin request succeeds, unaffected by the signup/reset operation's use of the Supabase Auth API

### Requirement: Service-role client is never used for end-user sign-in
The backend SHALL use a Supabase client scoped to the anon/default key (not the service-role client) for all end-user-facing GoTrue calls: `sign_in_with_password`, `sign_up`, `resend`, and `reset_password_for_email`.

#### Scenario: Login uses the anon-scoped client
- **WHEN** `POST /auth/login` authenticates a user
- **THEN** the `sign_in_with_password` call is made through a client scoped to the anon/default key, not through the service-role client (`supabase_admin`)

#### Scenario: Signup and resend use the anon-scoped client
- **WHEN** `POST /auth/signup` or `POST /auth/resend-confirmation` is handled
- **THEN** the `sign_up`/`resend` call is made through a client scoped to the anon/default key, not through the service-role client (`supabase_admin`); the `public.users` upsert that follows a successful signup still uses `supabase_admin`, since writing another user's profile row requires the privileged client

#### Scenario: Password reset request uses the anon-scoped client
- **WHEN** `POST /auth/forgot-password` is handled
- **THEN** the `reset_password_for_email` call is made through a client scoped to the anon/default key, not through the service-role client (`supabase_admin`)

### Requirement: Login uses a per-request client with no shared mutable auth state
The backend SHALL construct a fresh, per-request Supabase client for every end-user GoTrue call (`sign_in_with_password`, `sign_up`, `resend`, `reset_password_for_email`), rather than reusing any shared, module-level singleton client for these purposes. No client used for these operations may be reused as a data-access client (`.table()`, `.storage()`, `.rpc()`) anywhere else in the backend.

#### Scenario: Concurrent logins by different users don't share mutable state
- **WHEN** two different users log in via `POST /auth/login` at effectively the same time (interleaved requests)
- **THEN** each login's response reflects only that user's own credentials and session — neither login's internal client state is shared with, or overwritten by, the other's

#### Scenario: Concurrent auth operations of different kinds don't share mutable state
- **WHEN** a login, a signup, and a password-reset request happen at effectively the same time (interleaved requests)
- **THEN** each operation's response reflects only its own inputs — none of these operations' internal client state is shared with, or overwritten by, another

#### Scenario: No other backend operation depends on any auth-call client's identity
- **WHEN** the codebase is searched for usages of the clients used to perform `sign_in_with_password`, `sign_up`, `resend`, or `reset_password_for_email`
- **THEN** none of those clients are used for any other purpose (no `.table()`, `.storage()`, or `.rpc()` calls depend on their authorization state)
