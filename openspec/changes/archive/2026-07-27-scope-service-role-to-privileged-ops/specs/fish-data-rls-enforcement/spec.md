## ADDED Requirements

### Requirement: Fish image/analysis table queries run as the calling user
Reads and writes against `public.fish_images` and `public.fish_analyses` initiated on behalf of an authenticated end user SHALL be executed using a Supabase client authenticated with that user's own access token (activating Row Level Security), not the `service_role` client.

#### Scenario: A user's own data is still reachable
- **WHEN** an authenticated user requests their own fish images or analyses via `/fish/images` or `/fish/analyses`
- **THEN** the request succeeds and returns exactly the rows owned by that user, identical to the current behavior

#### Scenario: RLS blocks cross-user access even if an application check is missing
- **WHEN** a table query for `fish_images`/`fish_analyses` is executed with a user-scoped client and no `user_id` filter is applied by the calling code
- **THEN** the database's Row Level Security policies (`*_select_own`, `*_insert_own`, `*_update_own`, `*_delete_own`) still restrict the result to rows owned by the authenticated user

### Requirement: Storage access for fish images is explicitly out of scope
This change SHALL NOT alter which Supabase client is used for Storage operations (`upload`, `download`, `remove`, `create_signed_url`) on the `fish-images` bucket, since no Row Level Security policies exist yet on `storage.objects` for that bucket.

#### Scenario: Storage operations continue to work exactly as before
- **WHEN** a fish image is uploaded, downloaded, or deleted through the existing endpoints after this change
- **THEN** the Storage operation behaves identically to before this change (still authorized via the service-role client)

### Requirement: Python-level ownership checks are retained as defense in depth
Existing Python-level ownership checks (comparing `row["user_id"]` to the authenticated user's id) in `fish_image_service.py` and `main.py` SHALL remain in place after this change, not be removed.

#### Scenario: Ownership check still present after the change
- **WHEN** the code for `delete_image`, `delete_analysis`, and the inline check in `/fish/analyses/process` is reviewed after this change
- **THEN** the `user_id` comparison raising `PermissionError`/403 on mismatch is still present
