# documents-file-id-backfill Specification

## Purpose
TBD - defined by change fix-chat-rpc-and-backfill-file-ids. Update Purpose after archiving.

## Requirements

### Requirement: Legacy documents have their top-level file identifiers backfilled
For rows in `public.documents` where the top-level `original_file_id` (or `original_file_name`) column is `NULL` but the equivalent value exists inside the `metadata` JSON column, the value SHALL be copied into the top-level column.

#### Scenario: Backfill fills only missing top-level values
- **WHEN** the backfill runs against a row with `original_file_id IS NULL` and `metadata->>'original_file_id'` set to a non-null value
- **THEN** the row's top-level `original_file_id` is updated to match the value from `metadata`

#### Scenario: Backfill never overwrites an existing top-level value
- **WHEN** the backfill runs against a row that already has a non-null top-level `original_file_id`
- **THEN** that row's `original_file_id` is left unchanged, regardless of what `metadata` contains

### Requirement: Delete operations match legacy documents after backfill
After the backfill, deleting a file by its `original_file_id` (individually via `/admin/vector-base/files/{id}/delete`, or in bulk via `/admin/vector-base/cleanup` with confirmation) SHALL match and remove the corresponding rows in `documents`, including rows that originated from the legacy ingestion (previously non-matching due to a `NULL` top-level column).

#### Scenario: A previously non-matching legacy file can now be targeted for deletion
- **WHEN** a `SELECT` query filters `documents` by `original_file_id = eq.<id>` for a file that previously had `NULL` in that column
- **THEN** the query returns all of that file's chunk rows, confirming a subsequent `DELETE` with the same filter would match them
