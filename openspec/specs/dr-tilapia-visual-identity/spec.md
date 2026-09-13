# dr-tilapia-visual-identity

## Purpose

Defines the "Dr. Tilap-IA" public-facing visual identity: a single canonical
landing page, and a shared design-token system (typography, color palette,
spacing) applied consistently across the landing page and the authentication
screens (login, forgot password), without altering authentication behavior
or weakening backend TLS trust configuration.

## Requirements

### Requirement: A single public landing page exists
The application SHALL expose exactly one active marketing landing page. No unreferenced or competing landing route may remain reachable.

#### Scenario: Root route serves the landing page
- **WHEN** a visitor requests `/`
- **THEN** the response is the "Dr. Tilap-IA" landing page (nav, hero, services, about, footer)

#### Scenario: No duplicate landing route remains
- **WHEN** the previous `/landing` route is requested
- **THEN** it returns a 404, and no application code references that route

### Requirement: The landing page and auth screens share one visual identity
The home page and the authentication screens (login, forgot password) SHALL use the same design tokens (typography, color palette, spacing) derived from the provided design reference, scoped so they do not affect other routes.

#### Scenario: Login and forgot-password share the landing's design tokens
- **WHEN** `/auth/login` or `/auth/forgot-password` is rendered
- **THEN** it uses the same font families, color tokens, and component styling (buttons, form fields, cards) as the home page

#### Scenario: Other routes are unaffected
- **WHEN** a route under `/main/*` or the unmodified auth screens (`/auth/signup`, `/auth/callback`) is rendered
- **THEN** its existing typography and color theme are unchanged

### Requirement: Visual restyling does not alter authentication behavior
Restyling the login and forgot-password screens SHALL NOT change any authentication state, request, error handling, or redirect behavior.

#### Scenario: Login flow behavior is unchanged
- **WHEN** a user submits valid or invalid credentials on the restyled login screen
- **THEN** the same requests, error messages, success message, and post-login redirect occur as before the restyle

#### Scenario: Forgot-password flow behavior is unchanged
- **WHEN** a user submits an email on the restyled forgot-password screen
- **THEN** the same validation, request, and response handling occur as before the restyle

### Requirement: Backend TLS trust remains configurable and never disabled
The backend's outbound HTTPS clients SHALL continue to support a locally-trusted CA bundle for environments with TLS-inspecting proxies (e.g. antivirus software), and SHALL NOT disable certificate verification to work around a stale or missing local root certificate.

#### Scenario: A stale local CA bundle causes real TLS failures, not silent bypass
- **WHEN** the configured CA bundle does not include the certificate authority currently intercepting outbound TLS connections
- **THEN** requests fail with a certificate verification error rather than the backend disabling verification to route around it

#### Scenario: Regenerating the local CA bundle restores connectivity
- **WHEN** the local CA bundle is regenerated to include the current locally-trusted root certificates
- **THEN** outbound calls to Supabase succeed without any code change to the verification mechanism
