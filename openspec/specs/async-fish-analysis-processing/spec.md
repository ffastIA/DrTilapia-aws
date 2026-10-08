# async-fish-analysis-processing Specification

## Purpose
TBD - created by archiving change async-fish-analysis-processing. Update Purpose after archive.
## Requirements
### Requirement: Job creation responds immediately
`POST /fish/analyses/process` SHALL validate the request (existence and ownership of both images), create a persisted analysis job with status `queued`, schedule the processing in the background and respond with HTTP 202 and a body containing `job_id` and `status`, without waiting for image processing to complete.

#### Scenario: Valid request creates a job
- **WHEN** an authenticated user posts a valid `lateral_id` and `superior_id` that belong to them
- **THEN** the response is HTTP 202 with a `job_id` and `status` of `queued` (or `processing`), returned before the image processing finishes

#### Scenario: Response time is independent of processing time
- **WHEN** the image processing for a job takes longer than 60 seconds
- **THEN** the `POST` request has already completed within a few seconds and no HTTP request in the flow is held open for the duration of the processing

#### Scenario: Image not found or not owned
- **WHEN** either image does not exist or belongs to another user
- **THEN** the response is 404 or 403 respectively and no job is created

### Requirement: Job status and result can be queried
`GET /fish/analyses/jobs/{job_id}` SHALL return the job's `status` (`queued`, `processing`, `done` or `error`). When `status` is `done` the response SHALL include `analysis_id` and a `result` with the same fields as the previous synchronous `ProcessResponse`. When `status` is `error` the response SHALL include a sanitized `error` message.

#### Scenario: Polling a running job
- **WHEN** the owner requests the job while processing is in progress
- **THEN** the response is 200 with `status` `queued` or `processing` and no `result`

#### Scenario: Polling a completed job
- **WHEN** the owner requests the job after processing succeeded
- **THEN** the response is 200 with `status` `done`, the `analysis_id` of the created analysis, and a `result` containing the dimensions, `kvol`, per-image metrics, visualizations and warnings

#### Scenario: Polling a failed job
- **WHEN** the owner requests the job after processing failed
- **THEN** the response is 200 with `status` `error` and a generic error message that exposes no internal exception details

### Requirement: Jobs are isolated per user
Rows in `public.fish_analysis_jobs` SHALL be protected by Row Level Security so that a user can only read and modify their own jobs, and the application SHALL access the table with a client authenticated with the calling user's token and also verify ownership in Python.

#### Scenario: Another user's job is not accessible
- **WHEN** a user requests a `job_id` created by a different user
- **THEN** the response is 404 and no data from that job is disclosed

#### Scenario: RLS blocks cross-user access without an application filter
- **WHEN** a query on `fish_analysis_jobs` runs with a user-scoped client and no `user_id` filter
- **THEN** only rows owned by the authenticated user are returned

### Requirement: Job state is durable across workers
The job state SHALL be stored in the database, not only in process memory, so that any backend worker can serve the status query for a job started by another worker.

#### Scenario: Status is served by a different worker
- **WHEN** a job is started by one backend worker process and the status request is handled by another worker process
- **THEN** the status returned reflects the job's actual current state

### Requirement: Orphaned jobs are recovered
A job whose status remains `queued` or `processing` for longer than the configured staleness limit SHALL be treated as failed: its status SHALL become `error` with a message indicating the processing was interrupted, and it SHALL NOT block new jobs for the same images.

#### Scenario: Worker dies mid-processing
- **WHEN** the worker executing a job terminates unexpectedly and the staleness limit elapses
- **THEN** the next status query (or job creation for the same images) marks the job `error` and the user can submit the analysis again

### Requirement: Duplicate submissions are idempotent
If the same user submits the same `lateral_id` and `superior_id` while a non-stale job for that pair is `queued` or `processing`, the system SHALL return the existing job instead of creating another one, so that only one analysis is produced.

#### Scenario: Double click on process
- **WHEN** a user posts the same image pair twice while the first job is still running
- **THEN** both responses carry the same `job_id` and only one row is created in `fish_analyses`

#### Scenario: Resubmission after completion
- **WHEN** a user posts the same image pair after the previous job finished (`done` or `error`)
- **THEN** a new job is created

### Requirement: Processing concurrency is bounded
Each backend process SHALL limit the number of analysis jobs executing image processing concurrently to a configurable maximum; additional jobs SHALL remain `queued` until a slot is free.

#### Scenario: More jobs than slots
- **WHEN** more jobs are created than the concurrency limit allows
- **THEN** the surplus jobs stay `queued`, later transition to `processing` and eventually `done`, without failing due to the limit

### Requirement: Processing logic and result format are preserved
The background execution SHALL reuse the existing processing logic (download, scale detection, background removal, metrics, Kvol, analysis creation, image status updates) and the `result` SHALL keep the same fields as the previous `ProcessResponse`, so that existing UI consumers keep working.

#### Scenario: Same analysis outcome as before
- **WHEN** a job completes successfully
- **THEN** a `fish_analyses` row exists with the same `comprimento_cm`, `altura_cm`, `largura_cm` and `kvol` that the synchronous flow would have produced, and both images are linked to it with `processing_status` `done`

### Requirement: Frontend waits for completion by polling
The frontend SHALL create the job and poll its status until it reaches `done` or `error`, presenting progress to the user and resolving with the same result shape used before. Polling SHALL stop on unmount and after a maximum wait time.

#### Scenario: Analysis completes while the user waits
- **WHEN** the user starts an analysis and the job finishes after 40 seconds
- **THEN** the UI shows a progress state during the wait and then displays the same result and success feedback as before, with no 504 error

#### Scenario: Job fails
- **WHEN** polling observes `status` `error`
- **THEN** the UI shows the error message and lets the user retry

#### Scenario: Polling exceeds the maximum wait
- **WHEN** the job is still not finished after the maximum wait time
- **THEN** the UI stops polling and shows a message that the processing is taking longer than expected

#### Scenario: Transient network failure during polling
- **WHEN** a single polling request fails with a network error
- **THEN** polling continues and only aborts after several consecutive failures

