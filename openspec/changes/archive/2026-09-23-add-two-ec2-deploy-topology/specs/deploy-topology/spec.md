## ADDED Requirements

### Requirement: Backend Runs on an Isolated Private Host
The backend container SHALL run on a dedicated EC2 instance with no public IP address, reachable
only over the private VPC network from the frontend EC2 instance's security group. The container
port 8000 SHALL be published on all interfaces of that host (`0.0.0.0:8000:8000`) and protection
against unauthorized access SHALL be enforced at the network layer (Security Group rule referencing
the frontend EC2's security group as source — never `0.0.0.0/0` or a broad CIDR block), not by
binding to loopback.

#### Scenario: Frontend host can reach the backend over the private network
- **WHEN** the Next.js server on the frontend EC2 issues a request to the backend's private address
  on port 8000
- **THEN** the request reaches the FastAPI application and receives a response

#### Scenario: Backend port is not reachable from outside the frontend's security group
- **WHEN** a host outside the frontend EC2's security group attempts to connect to the backend's
  private IP on port 8000
- **THEN** the connection is rejected at the network layer (Security Group), before reaching the
  FastAPI application

### Requirement: Nginx Reverse-Proxies the Frontend EC2's Public Traffic
The frontend EC2 SHALL run an Nginx container listening on port 80, forwarding all traffic to the
Next.js container on port 3000. The Next.js container SHALL NOT publish port 3000 to the host's
public interface — it SHALL be reachable only from Nginx over the deploy compose's internal network.

#### Scenario: Public HTTP request reaches Next.js through Nginx
- **WHEN** an HTTP request arrives at the frontend EC2 on port 80
- **THEN** Nginx forwards it to the Next.js container on port 3000 and returns the Next.js response
  to the caller

#### Scenario: Next.js port is not directly reachable from outside the host
- **WHEN** a client attempts to connect directly to port 3000 on the frontend EC2's public IP
- **THEN** the connection does not succeed (port 3000 is not published to the host's public
  interface)

### Requirement: Nginx Accommodates the Backend's Configured Upload Limits
Nginx's `client_max_body_size` and proxy timeouts SHALL be large enough to pass through the largest
upload type the backend accepts (video uploads, configured via `MAX_UPLOAD_SIZE_VIDEO_MB` in
`backend/app/utils/upload_validation.py`, default 200MB), plus a safety margin, without rejecting
the request before it reaches the Next.js proxy.

#### Scenario: A video upload at the backend's configured size limit succeeds through Nginx
- **WHEN** a client uploads a video file at or below the backend's configured
  `MAX_UPLOAD_SIZE_VIDEO_MB` limit
- **THEN** Nginx forwards the full request body to Next.js without returning a 413 (Request Entity
  Too Large) response

#### Scenario: A long-running upload/processing request is not cut off by Nginx before the backend responds
- **WHEN** a request takes longer than Nginx's default proxy timeouts to complete (e.g., a large
  upload combined with backend image processing)
- **THEN** Nginx's configured proxy timeouts are long enough that the connection remains open until
  the backend responds, rather than Nginx terminating it first

### Requirement: Nginx Signals the Original Viewer Protocol to Upstream Services
Nginx SHALL set the `X-Forwarded-Proto` header to `https` on every request forwarded upstream,
rather than deriving it from the scheme of its own incoming connection. This is necessary because
the connection between CloudFront and Nginx is always plain HTTP (CloudFront terminates TLS for the
viewer connection but uses HTTP-only to the origin), so the scheme of Nginx's own incoming
connection would always read as `http` regardless of the viewer's real protocol.

#### Scenario: Upstream services observe the viewer's real protocol
- **WHEN** Nginx forwards a request to the Next.js container (and, transitively, to the backend via
  the Next.js rewrite proxy)
- **THEN** the forwarded request carries `X-Forwarded-Proto: https`, regardless of the fact that the
  CloudFront→Nginx connection itself was HTTP

### Requirement: Frontend and Backend Deploy Independently as Separate Compose Stacks
The production deploy artifacts SHALL be split into one Docker Compose file per host role (frontend:
Nginx + Next.js; backend: FastAPI only), each deployable and restartable independently. No compose
file SHALL declare a cross-host service dependency (e.g., a `depends_on` health condition on a
service defined in the other host's compose file), since Docker Compose cannot evaluate health
conditions across separate hosts.

#### Scenario: The backend stack can be deployed and restarted without touching the frontend host
- **WHEN** an operator runs `docker compose -f docker-compose.backend.yml up -d` on the backend EC2
- **THEN** the backend service starts successfully without requiring any action on the frontend EC2

#### Scenario: The frontend stack can be deployed and restarted without touching the backend host
- **WHEN** an operator runs `docker compose -f docker-compose.frontend.yml up -d` on the frontend EC2
- **THEN** the Nginx and frontend services start successfully without requiring any action on the
  backend EC2

### Requirement: CloudFront Origin Targets the Frontend EC2's Nginx Port
The CloudFront distribution's origin SHALL point to the frontend EC2's port 80 (Nginx), not port
3000 (the Next.js container directly), so that all public traffic passes through the Nginx layer
described above.

#### Scenario: CloudFront forwards viewer requests to Nginx, not directly to Next.js
- **WHEN** CloudFront forwards a viewer request to its configured origin
- **THEN** the request arrives at the frontend EC2 on port 80 (Nginx), not port 3000
