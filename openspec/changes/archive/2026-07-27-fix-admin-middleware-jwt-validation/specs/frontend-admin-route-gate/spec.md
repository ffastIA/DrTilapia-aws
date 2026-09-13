## ADDED Requirements

### Requirement: Admin route gate derives authorization from a verifiable source
The Next.js middleware SHALL determine whether a request to `/main/admin/*` is authorized as admin by verifying the caller's role against the Supabase backend (using the request's access token), never by trusting an unverified client-writable value (such as a plain cookie holding a `role` claim).

#### Scenario: Forged role cookie does not grant admin access
- **WHEN** a request to `/main/admin` carries a client-writable cookie claiming `role: "admin"`, but the corresponding access token belongs to a non-admin user (or is invalid/expired)
- **THEN** the middleware redirects to `/main/hub`, not granting access to the admin UI

#### Scenario: Valid admin token grants access
- **WHEN** a request to `/main/admin` carries a valid, non-expired access token belonging to a user whose `public.users.role` is `admin`
- **THEN** the middleware allows the request through

#### Scenario: Valid non-admin token is denied
- **WHEN** a request to `/main/admin` carries a valid, non-expired access token belonging to a user whose `public.users.role` is not `admin`
- **THEN** the middleware redirects to `/main/hub`

#### Scenario: Verification source is unreachable fails closed
- **WHEN** the middleware cannot reach the verification source (e.g. network error) while checking a `/main/admin` request
- **THEN** the request is denied (redirected to `/main/hub`), not allowed through
