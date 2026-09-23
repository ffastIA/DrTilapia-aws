## ADDED Requirements

### Requirement: Authentication and UI-State Cookies Are Marked Secure
The frontend application SHALL set the `Secure` attribute on every cookie that carries
authentication or auth-related UI state (`accessToken`, `user`, `profileComplete`,
`profileGateSeen`), whether written client-side (via `js-cookie` in
`frontend/store/authStore.ts`) or server-side (via `NextResponse` in `frontend/middleware.ts`).

#### Scenario: Login sets the access token cookie as Secure
- **WHEN** a user successfully logs in and the application sets the `accessToken` cookie
- **THEN** the cookie is written with the `Secure` attribute

#### Scenario: Profile-completion gate cookies are Secure
- **WHEN** the middleware sets `profileComplete` or `profileGateSeen` after evaluating the
  onboarding gate
- **THEN** both cookies are written with the `Secure` attribute

#### Scenario: Local development over `localhost` still authenticates successfully
- **WHEN** a developer logs in against the application running at `http://localhost:3000`
- **THEN** the `Secure` cookies are still sent and read correctly, since browsers treat `localhost`
  as a secure context regardless of scheme
