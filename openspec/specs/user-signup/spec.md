# user-signup Specification

## Purpose
TBD - created by archiving change add-signup-email-confirmation-and-password-reset. Update Purpose after archive.
## Requirements
### Requirement: Public self-registration
The system SHALL allow any visitor to create a new account by submitting an email and password to `POST /auth/signup`, without requiring an existing session or admin action.

#### Scenario: New email signs up successfully
- **WHEN** a visitor submits `POST /auth/signup` with an email that has no existing account and a valid password
- **THEN** the system creates a Supabase Auth user, creates a corresponding `public.users` row with `role="user"`, triggers a confirmation email, and returns a generic success message

#### Scenario: Already-registered email signs up again
- **WHEN** a visitor submits `POST /auth/signup` with an email that already has an account (confirmed or not)
- **THEN** the system returns the exact same HTTP status and response body as the new-email case, and does not create a duplicate `public.users` row or reveal that the account already exists

### Requirement: Email confirmation required before first login
The system SHALL reject `POST /auth/login` for an account whose email has not been confirmed, with a distinct, machine-readable error code rather than the generic invalid-credentials error.

#### Scenario: Login attempt on unconfirmed account
- **WHEN** a user who signed up but never clicked the confirmation link submits `POST /auth/login` with the correct email and password
- **THEN** the system returns HTTP 403 with `detail: "email_not_confirmed"`, distinct from the 401 returned for wrong credentials

#### Scenario: Login succeeds after confirmation
- **WHEN** a user clicks the confirmation link from their email and then submits `POST /auth/login` with the correct email and password
- **THEN** the system returns HTTP 200 with a valid access token and the user's role, exactly as for any other successful login

### Requirement: Resend confirmation email
The system SHALL allow a user to request a new confirmation email via `POST /auth/resend-confirmation`, without revealing whether the submitted email exists or is already confirmed.

#### Scenario: Resend for a genuinely unconfirmed account
- **WHEN** `POST /auth/resend-confirmation` is called with the email of an account that signed up but has not confirmed
- **THEN** the system sends a new confirmation email and returns a generic success message

#### Scenario: Resend for a nonexistent or already-confirmed email
- **WHEN** `POST /auth/resend-confirmation` is called with an email that has no account, or with an email that is already confirmed
- **THEN** the system returns the exact same HTTP status and response body as the genuinely-unconfirmed case, and does not send any email

### Requirement: New user profile exists immediately after signup
The system SHALL create the `public.users` row (`id`, `email`, `role="user"`) at signup time, before the user has confirmed their email, so that role lookups succeed the instant the user completes their first login.

#### Scenario: Profile row present before confirmation
- **WHEN** a user has signed up but not yet clicked the confirmation link
- **THEN** a `public.users` row already exists for that user's `id` with `role="user"`

