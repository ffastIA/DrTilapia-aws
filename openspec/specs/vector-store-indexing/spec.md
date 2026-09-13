# vector-store-indexing Specification

## Purpose
TBD - defined by change fix-vector-index-and-db-hygiene. Update Purpose after archiving.

## Requirements

### Requirement: The vector index covers the column used by similarity search
The vector similarity index SHALL be defined on the same column that the similarity search reads. No vector index may exist on a column that the search path does not query.

#### Scenario: Index and search target the same column
- **WHEN** the vector index definition and the similarity search function are inspected
- **THEN** both reference the same embedding column

#### Scenario: Query planner can use the index
- **WHEN** the similarity search query is explained against a table volume where an index scan is advantageous
- **THEN** the plan uses the vector index rather than a sequential scan

### Requirement: A single embedding column is the source of truth
The `documents` table SHALL have exactly one embedding column. A second, unpopulated embedding column SHALL NOT be retained.

#### Scenario: Only one embedding column exists
- **WHEN** the columns of `documents` are inspected
- **THEN** exactly one column of vector type is present

#### Scenario: Batch insert writes only the surviving column
- **WHEN** the batch insert function is inspected
- **THEN** it writes the embedding to the single surviving embedding column and references no other vector column

### Requirement: Similarity search remains behaviourally unchanged
Correcting the index SHALL NOT change which chunks a given query returns, nor their similarity scores or ordering.

#### Scenario: Same query returns same results after the change
- **WHEN** the same query embedding is searched before and after the indexing correction
- **THEN** the returned chunk ids, similarity scores, and their order are unchanged

#### Scenario: Soft-deleted chunks stay excluded
- **WHEN** a similarity search runs after the change
- **THEN** chunks with a non-null deletion timestamp are still excluded from the results

### Requirement: RAG database functions have a fixed search path
Every Postgres function in the RAG path SHALL declare an explicit `search_path`.

#### Scenario: Search and insert functions declare search_path
- **WHEN** the similarity search and batch insert functions are inspected
- **THEN** each declares an explicit `search_path` configuration

#### Scenario: Security advisor is clean for these functions
- **WHEN** the database security advisor is run
- **THEN** it reports no mutable-search-path finding for the RAG functions

### Requirement: Row-level security policies on documents are not duplicated
The `documents` table SHALL NOT carry multiple permissive policies granting the same operation to the same role, and role checks in policies SHALL be evaluated once per query rather than once per row.

#### Scenario: No duplicate permissive policies
- **WHEN** the policies on `documents` are inspected
- **THEN** no two permissive policies grant the same command to the same role

#### Scenario: Backend access is preserved
- **WHEN** the backend queries `documents` with its privileged key after the policy consolidation
- **THEN** the query succeeds and returns the same rows as before

### Requirement: The application does not query a non-existent table
Code paths that read or delete from an ingestion-log table SHALL be removed, and API responses SHALL NOT report counters derived from them.

#### Scenario: No reference to the absent table remains
- **WHEN** the backend source is searched for the ingestion-log table
- **THEN** no query against it remains

#### Scenario: Admin operations no longer report a constant-zero counter
- **WHEN** a file deletion or a base cleanup completes
- **THEN** the response omits the ingestion-log counter rather than reporting a value that is always zero

#### Scenario: Repeated admin calls produce no error logs from the absent table
- **WHEN** file deletion or cleanup is invoked repeatedly
- **THEN** no warning about a missing ingestion-log table is emitted
