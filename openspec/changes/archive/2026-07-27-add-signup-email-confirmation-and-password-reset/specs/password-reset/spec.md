## ADDED Requirements

### Requirement: Request password reset without account enumeration
The system SHALL allow any visitor to request a password-reset email via `POST /auth/forgot-password`, returning an identical generic response regardless of whether the submitted email has an account.

#### Scenario: Existing account requests reset
- **WHEN** `POST /auth/forgot-password` is called with the email of an existing account
- **THEN** the system sends a password-reset email to that address and returns a generic success message

#### Scenario: Nonexistent email requests reset
- **WHEN** `POST /auth/forgot-password` is called with an email that has no account
- **THEN** the system returns the exact same HTTP status and response body as the existing-account case, and does not send any email

### Requirement: Complete password reset via emailed token
The system SHALL allow a user who has clicked a valid, unexpired password-reset link to set a new password via `POST /auth/reset-password`, using the tokens delivered by that link.

#### Scenario: Valid reset token
- **WHEN** `POST /auth/reset-password` is called with the `access_token`/`refresh_token` pair extracted from a valid, unexpired reset link, plus a new password
- **THEN** the system updates the account's password and returns a success message

#### Scenario: Invalid, expired, or reused reset token
- **WHEN** `POST /auth/reset-password` is called with a token that is invalid, expired, or has already been consumed
- **THEN** the system returns a clear error (HTTP 400) rather than a silent failure or a misleading success message

#### Scenario: Login reflects the new password
- **WHEN** a user successfully completes `POST /auth/reset-password` and then attempts `POST /auth/login`
- **THEN** login fails with the old password and succeeds with the new password
