## ADDED Requirements

### Requirement: Development reads secrets from the local .env
When `ENVIRONMENT` is `development`, the backend SHALL take its secrets from `backend/.env` and MUST NOT contact AWS Secrets Manager.

#### Scenario: Development without exported variables
- **WHEN** `ENVIRONMENT=development` is defined only inside `backend/.env` and nothing is exported in the shell
- **THEN** the backend starts using the values from `backend/.env` and does not import `boto3`

### Requirement: Non-development environments read secrets from AWS Secrets Manager
When `ENVIRONMENT` is anything other than `development` (including unset), the backend SHALL load the secret named by `SECRET_ID` (default `tilapia/backend`) from the region given by `AWS_REGION` or `AWS_DEFAULT_REGION` (default `sa-east-1`), and the secret's values MUST take precedence over values already present in the environment.

#### Scenario: Secret values are applied
- **WHEN** the backend starts with `ENVIRONMENT=production` and the secret contains `SUPABASE_URL`, `SUPABASE_KEY` and `SUPABASE_SERVICE_ROLE_KEY`
- **THEN** the Supabase clients are created with the secret's values

#### Scenario: Stale environment value is overridden
- **WHEN** `SUPABASE_URL` already exists in the environment with a different value than the secret
- **THEN** the value from the secret is used

### Requirement: Failure to load the secret aborts startup clearly
If the secret cannot be read outside development, the backend SHALL fail at startup with an error that names the secret, the region and the cause, and MUST NOT continue with partial configuration.

#### Scenario: Secret unreadable
- **WHEN** access to the secret is denied or the secret does not exist
- **THEN** startup raises an error naming the secret id, the region and the underlying error

#### Scenario: Required key missing from the secret
- **WHEN** the secret lacks `SUPABASE_SERVICE_ROLE_KEY`
- **THEN** startup fails with an error naming the missing variable

### Requirement: Secret values are never logged or included in errors
The backend SHALL log only the source of the secrets, never their values, including in startup errors.

#### Scenario: Logs and errors are free of values
- **WHEN** the backend starts or fails to start
- **THEN** no secret value appears in logs or in the error message
