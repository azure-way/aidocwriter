# Phase 5 – Access Control Hardening Plan

## Objectives & Success Criteria
- **Isolate artifacts per user** so every blob path is rooted at `jobs/{user_id}/{job_id}` with role-based access enforced by the API and any Functions/Container Apps identity.
- **Persist owner metadata** for each job record and validate all `/jobs`, `/timeline`, and artifact lookups against that owner so only the creator can view their assets.
- **Keep observability intact** by extending current telemetry/status events to include the user context required for auditing.

## Current State Snapshot
- Blob paths (`src/docwriter/storage.py`, `src/docwriter/artifacts.py`, Azure Functions under `src/functions_*`) are scoped to `jobs/{job_id}/…` and assume trust in the API layer for isolation.
- The FastAPI layer (`src/api/routers/jobs.py`) already filters Table storage queries by `PartitionKey=user_id`, but blob downloads rely on path validation only.
- Status topic events already include `user_id`, enabling auditing even though no end-user notification fan-out exists today.
- Terraform (`infra/terraform/modules/storage`, `infra/terraform/modules/service_bus`) provisions a single private container and topic without per-user authorization boundaries.

## Workstream A – Storage Partitioning & Access Guards
1. **Blob path contract**
   - Update `BlobStore.allocate_document_blob` and all call sites (queue handlers, agents, workers) to require `user_id` and emit `jobs/{user_id}/{job_id}/…` paths.
   - Introduce helper(s) to resolve canonical sub-paths (`intake`, `draft`, `artifacts`, `images`, `metrics`) to avoid string literals across modules.
2. **Writers & Functions**
   - Review each Azure Function (`src/functions_*`) to ensure inbound messages carry `user_id`; reject/poison messages without it.
   - Thread `user_id` into file operations inside stage processors (`src/docwriter/stages/*`, `src/docwriter/diagram_renderer.py`, exporters in `src/docwriter/artifacts.py`).
3. **Blob access policy**
   - Require managed identity or SAS tokens scoped to `jobs/{user_id}` when accessing storage outside the API (e.g., background Functions). Terraform must assign RBAC to storage container with `data_factory_role`/`storage_blob_data_contributor` limited to identities actually used.
4. **Validation & tests**
   - Unit tests covering new helper ensures unauthorized user_id/job_id combos resolve different roots.
   - Integration test simulating artifact download ensures API rejects cross-user paths even if blob exists.

## Workstream B – Metadata & Owner Enforcement
1. **Document index schema**
   - Extend `DocumentIndexStore` (`src/docwriter/document_index.py`) to maintain `owner_id`, `schema_version`, and audit timestamps.
   - Backfill owner IDs for existing rows using status history or `intake/context.json`.
2. **API guard rails**
   - Expand `current_user_dependency` to return both Auth0 subject and optional org/roles for future RBAC.
   - Update `/jobs`, `/jobs/{id}` routes to read owner metadata and enforce owner-only access before reading blobs or timelines.
   - Return `403` for unauthorized access with structured error payload for the UI.
3. **Status store enrichment**
   - Ensure `StatusTableStore.record` cascades owner metadata into the index when stage updates arrive (handle race where payload lacks `user_id`).

## Workstream C – UI & API Experience
1. **Ownership clarity**
   - Update document list cards (`ui/src/app/page.tsx`, related components) to make it explicit when the signed-in user is the owner and that documents are private by default.
2. **Unauthorized flows**
   - Handle 403 responses with a clear “Access denied” message that directs users to contact the document owner or admin, without exposing sharing mechanics.
3. **Owner tooling**
   - Provide lightweight indicators in the workspace when a document is missing owner metadata and surface audit timestamps for every job.
4. **End-to-end tests**
   - Cypress/Playwright flows covering access denial handling, owner-only document viewing, and UI surfacing of migration status.

## Testing & Acceptance
- **Unit tests** for new helpers (path resolution, ACL enforcement) and schema-version handling.
- **Integration tests** simulating owner access vs. unauthorized users plus blob isolation using Service Bus + storage emulator (Azurite).
- **Security review**: run static analysis for path traversal, include managed identity access review, and document threat model updates.
- **Acceptance criteria**
  - Unauthorized user can never fetch blobs/status for another user (verified via automated tests + manual pen test).
  - Storage hierarchy keeps every job under the correct `jobs/{user_id}/{job_id}` prefix with no orphaned data.

## Proposed Timeline (2 Sprints)
- **Sprint 1**: Storage refactor, ACL metadata schema, Terraform updates.
- **Sprint 2**: UI/UX hardening, e2e validation, documentation updates.
