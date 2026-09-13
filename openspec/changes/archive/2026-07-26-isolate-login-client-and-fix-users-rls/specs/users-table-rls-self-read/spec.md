## ADDED Requirements

### Requirement: Authenticated users can read their own users row
`public.users` SHALL have a Row Level Security policy allowing the `authenticated` role to `SELECT` only the row whose `id` matches `auth.uid()`. This applies regardless of which Supabase client/key context performs the read.

#### Scenario: A user can read their own row
- **WHEN** a query against `public.users` is executed under the `authenticated` Postgres role (i.e. using a user's own JWT, not service_role) filtering `id = auth.uid()`
- **THEN** exactly one row is returned: the querying user's own row, including their `role`

#### Scenario: A user cannot read another user's row
- **WHEN** a query against `public.users` is executed under the `authenticated` Postgres role for an `id` different from `auth.uid()`
- **THEN** no row is returned

### Requirement: No write access is granted to authenticated users on the users table
The new policy SHALL grant `SELECT` only. `authenticated` users SHALL NOT gain `INSERT`, `UPDATE`, or `DELETE` access to `public.users` as a result of this change.

#### Scenario: A user cannot change their own role
- **WHEN** a user authenticated as `authenticated` (not `service_role`) attempts to `UPDATE` their own row in `public.users` (e.g. to change `role` to `admin`)
- **THEN** the update is rejected by RLS (no matching policy grants `UPDATE` to `authenticated`)
