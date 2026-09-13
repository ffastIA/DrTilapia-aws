## ADDED Requirements

### Requirement: A single Supabase project is referenced consistently
All environment configuration used by the application (backend and its Docker configuration) SHALL reference the same Supabase project.

#### Scenario: docker-compose and backend/.env agree
- **WHEN** the Supabase project URL is compared between `backend/.env` and whatever `.env` file `backend/docker-compose.yml` mounts into the container
- **THEN** both reference the same project

### Requirement: Environment variables hold keys of the intended privilege level
`SUPABASE_KEY` (or equivalently named variables intended for low-privilege/anon usage) SHALL hold an `anon`-role key, never a `service_role`-role key, in every `.env` file in the repository.

#### Scenario: No anon-labeled variable holds a service_role key
- **WHEN** every `.env` file in the repository is inspected
- **THEN** no variable conventionally intended to hold the `anon` key decodes to a JWT with `role: service_role`

### Requirement: No unused direct database credentials are present
No `.env` file in the repository SHALL contain direct Postgres connection credentials (host/port/user/password/connection string) unless the application code actually establishes a direct Postgres connection.

#### Scenario: Direct DB credentials absent when unused
- **WHEN** the application only communicates with Supabase via its REST/Auth/Storage APIs (no direct `psycopg`/`asyncpg`/SQLAlchemy connection to Postgres)
- **THEN** no `.env` file contains `SUPABASE_DB_PASSWORD`, `SUPABASE_DATABASE_URL`, or equivalent direct database credentials

### Requirement: Docker Compose references the file the application actually loads
`backend/docker-compose.yml` SHALL mount and declare as `env_file` the same `.env` file that `backend/app/database.py` resolves at runtime inside the container.

#### Scenario: Container starts successfully with the versioned compose file
- **WHEN** the backend container is started using `backend/docker-compose.yml` with a correctly populated `.env` file in place
- **THEN** `backend/app/database.py` finds `SUPABASE_URL`, `SUPABASE_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` and the application starts without raising `ValueError`

### Requirement: Exposed service_role key is rotated
A `service_role` key known to have been exposed outside its intended secure channel (e.g. pasted in a chat transcript) SHALL be rotated in the Supabase Dashboard, and the new value SHALL be the one present in `backend/.env` going forward.

#### Scenario: Rotated key is in use
- **WHEN** the backend is started after the rotation
- **THEN** `backend/.env`'s `SUPABASE_SERVICE_ROLE_KEY` matches the newly rotated key, not the previously exposed one
