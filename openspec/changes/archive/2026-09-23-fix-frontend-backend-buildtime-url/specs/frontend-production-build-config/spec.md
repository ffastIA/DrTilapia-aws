## ADDED Requirements

### Requirement: Production Frontend Image Is Built With the Real Backend Address
The production build pipeline (`deploy/build-and-push.ps1`) SHALL build the frontend Docker image
with the `BACKEND_INTERNAL_URL` build argument set to the backend's actual reachable address in the
target deployment's network (the backend EC2's private IP), never a value that is only meaningful
inside the local development Docker Compose network.

#### Scenario: Published frontend image's proxy targets the real backend address
- **WHEN** `deploy/build-and-push.ps1` builds and publishes the frontend image to ECR
- **THEN** the resulting image's `.next/routes-manifest.json` rewrite destination for
  `/api-proxy/*` points to the backend's configured production address, not `http://backend:8000`

### Requirement: Production Build Does Not Depend on the Local Development Compose File
The production frontend image build SHALL NOT read its `BACKEND_INTERNAL_URL` (or the
`NEXT_PUBLIC_SUPABASE_*` build args) from the root `docker-compose.yml`'s build configuration. The
production build pipeline SHALL supply these values independently, so that changing the local
development default does not silently change what gets published to ECR, and vice versa.

#### Scenario: Local development build is unaffected by production build configuration
- **WHEN** a developer runs `docker compose build frontend` locally using the root
  `docker-compose.yml`
- **THEN** the resulting local image still resolves `BACKEND_INTERNAL_URL` to `http://backend:8000`
  (the Compose service DNS name), regardless of what value `deploy/build-and-push.ps1` uses for
  production builds

#### Scenario: Production build values are explicit, not inherited
- **WHEN** an operator inspects `deploy/build-and-push.ps1`
- **THEN** the values used for `BACKEND_INTERNAL_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and
  `NEXT_PUBLIC_SUPABASE_ANON_KEY` in the frontend image build are declared directly in the script,
  not derived from `docker-compose.yml`
