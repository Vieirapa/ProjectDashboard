# Project Export & Archive — Technical Specification v1

## 1. Objective

Provide a secure, project-scoped export and archive capability in Kanban view, allowing authorized users to:

- **Download Project**: export a complete, restorable snapshot of one project.
- **Archive Project**: export the same snapshot and transition the project to archived/read-only mode.

This feature must ensure strict tenant/project isolation and produce a deterministic artifact suitable for future project restore/import.

---

## 2. Scope

### In scope (v1)
- Single ZIP export artifact per project.
- Project-only data extraction (`project_id`-scoped).
- Files export with card-level organization.
- Integrity metadata (checksums, counts, schema version).
- RBAC-gated UI buttons in Kanban top-right.
- Archive operation semantics (state transition + access behavior).
- Automated tests (unit/integration/e2e/smoke).

### Out of scope (v1)
- Full import/reopen implementation (future feature).
- Cross-project batch export.
- Encryption-at-rest of ZIP artifact (optional future enhancement).
- Differential/incremental export.

---

## 3. Functional Requirements

### FR-1 — Download Project
Authorized users can generate and download a ZIP artifact representing the current state of a single project.

### FR-2 — Archive Project
Authorized users can:
1. Generate the same ZIP artifact,
2. Mark project as archived,
3. Enforce read-only constraints for non-admin users (configurable per policy).

### FR-3 — Strict Project Isolation
Exported data and files must include only resources linked to the selected `project_id`.

### FR-4 — Deterministic Structure
Export ZIP must follow a stable folder/file contract (`schema_version` controlled).

### FR-5 — Traceability
Export must include metadata for auditability (who exported, when, app version, record counts, checksums).

---

## 4. RBAC & Permissions

Introduce module permissions:

- `projects.export_download`
- `projects.archive`

UI behavior:
- Show **Download Project** only if user has `projects.export_download`.
- Show **Archive Project** only if user has `projects.archive`.

API authorization:
- Validate permissions server-side (never trust UI-only gating).

---

## 5. UX Requirements (Kanban)

Top-right actions:
- Primary: **Download Project**
- Danger: **Archive Project**

Recommended interaction:
- Confirmation modal for archive:
  - Message: project will be exported and switched to archived mode.
  - Explicit confirmation action (e.g., “Archive Project”).

Feedback:
- Progress/toast states for export generation.
- Clear error messages for permission denied, export failure, or empty fileset edge cases.

---

## 6. Export Artifact Contract (Single ZIP)

### 6.1 Naming Convention

```text
projectarchive_<project-slug>_<project-id>_<YYYYMMDD-HHMMSSZ>_v1.zip
```

Example:
```text
projectarchive_crm-rollout_PRJ-0021_20260325-124501Z_v1.zip
```

### 6.2 ZIP Structure

```text
projectarchive_<...>_v1.zip
  manifest.json
  data/
    project-data.json
  files/
    by-card/
      card-000123/
        20260320T101530Z_doc_tecnico_v3.pdf
      card-000124/
        20260321T091000Z_memorial.docx
    by-id/
      file-98ab12cd.bin
      file-a1f4de90.bin
    manifest-files.json
  checksums/
    sha256.txt
```

---

## 7. Data Model Inside Export

### 7.1 `manifest.json`
High-level index:
- `schema_version` (e.g. `"1.0"`)
- `artifact_version` (e.g. `"v1"`)
- `exported_at` (ISO8601 UTC)
- `exported_by` (`user_id`, `display_name`)
- `project` (`project_id`, `project_name`, `project_slug`)
- `source` (`app_version`, `git_commit` if available)
- `counts` (cards, dependencies, history entries, reviews, files)
- `paths` (relative paths to inner files)
- `checksums_ref` (`checksums/sha256.txt`)

### 7.2 `data/project-data.json`
Project-scoped logical snapshot:
- `meta`
- `project`
- `cards`
- `card_history`
- `reviews`
- `dependencies`
- `attachments_index` (logical references to files)
- `users_snapshot` (minimal, non-sensitive)
- `integrity` (section hashes/counts)

### 7.3 `files/manifest-files.json`
File-level mapping:
- `file_id`
- `card_id`
- `original_name`
- `stored_name`
- `mime_type`
- `size_bytes`
- `sha256`
- `version`
- `uploaded_at`
- `path_by_card`
- `path_by_id`

This enables easy human navigation and deterministic machine restore later.

### 7.4 `checksums/sha256.txt`
SHA-256 list for all exported inner files (including `manifest.json`, `project-data.json`, `manifest-files.json`, and each binary).

---

## 8. Archive Semantics

On successful Archive action:

1. Generate export ZIP (same contract as Download).
2. Persist audit event: `project.archived`.
3. Update project state: `archived=true` (+ `archived_at`, `archived_by`).
4. Enforce read-only behavior per policy:
   - Non-admin: block create/edit/delete card operations.
   - Admin: optional override (configurable, default allowed).

If export generation fails, archive transition must **not** proceed (atomic behavior requirement).

---

## 9. Security & Compliance Requirements

- Enforce `project_id` filtering in all queries.
- Never include secrets/tokens/sessions/system-wide logs.
- Sanitize file paths to prevent zip-slip and path traversal.
- Avoid leaking data from other projects through joins.
- Validate authorization on every API call.
- Log export/archive events with `request_id`.

---

## 10. API Proposal (v1)

- `POST /api/projects/{project_id}/export`
  - Response: ZIP stream/download (or signed URL if async later).
- `POST /api/projects/{project_id}/archive`
  - Action: generate ZIP + archive transition.
  - Response: success + archive metadata (+ optional file reference).

Optional future:
- Async jobs for large exports.

---

## 11. Error Handling

Standardized error codes:
- `forbidden` (missing permission)
- `project_not_found`
- `project_archived_conflict`
- `export_generation_failed`
- `file_integrity_failed`
- `archive_transaction_failed`

All failures must be user-readable and log-correlated (`request_id`).

---

## 12. Test Requirements (v1)

- Unit tests for:
  - naming convention,
  - manifest builder,
  - checksum generator,
  - path sanitization.
- Integration tests:
  - project-scoped export correctness,
  - no cross-project leakage,
  - archive atomicity.
- RBAC tests:
  - button visibility and API enforcement.
- E2E tests:
  - Download Project flow,
  - Archive Project flow + read-only enforcement.
- Regression tests:
  - custom roles module-first behavior maintained.

---

# Phased Implementation Plan (Robustness & Security First)

## Phase 0 — Design Freeze & Contract Validation
**Goal:** lock schema/UX/API before coding.

Deliverables:
- Approved spec (this doc),
- JSON contract examples (`manifest.json`, `project-data.json`, `manifest-files.json`),
- Permission matrix update.

Tests:
- Contract lint checks (JSON examples validated).
- Peer review checklist approved.

---

## Phase 1 — Backend Export Core (No UI yet)
**Goal:** implement deterministic ZIP export service.

Tasks:
- Implement export service with strict `project_id` scoping.
- Build:
  - `manifest.json`,
  - `data/project-data.json`,
  - `files/manifest-files.json`,
  - `checksums/sha256.txt`.
- Implement path normalization/sanitization.
- Add export audit event.

Tests:
- Unit:
  - filename formatter,
  - checksum correctness,
  - zip structure validator.
- Integration:
  - exported rows/files belong only to target project.
  - cross-project leakage tests (negative).

Exit criteria:
- Export endpoint returns valid ZIP with expected structure.
- All tests green.

---

## Phase 2 — Archive Workflow + Atomicity
**Goal:** implement safe archive transition tied to successful export.

Tasks:
- Add archive endpoint/service.
- Transactional/atomic flow:
  - if export fails => no archive state change.
- Add archived metadata fields (if not existing).
- Enforce backend read-only on archived project operations.

Tests:
- Integration:
  - archive success path.
  - forced export failure rollback.
- Authorization:
  - only `projects.archive` allowed.
- Behavioral:
  - writes blocked when archived (non-admin).

Exit criteria:
- Atomic behavior proven by tests.
- Archived project protections active.

---

## Phase 3 — UI/RBAC Integration (Kanban)
**Goal:** expose feature safely in UI.

Tasks:
- Add top-right buttons:
  - Download Project,
  - Archive Project.
- Gate by module permissions.
- Add archive confirmation modal.
- Add success/error toast handling.

Tests:
- Frontend unit/component tests for visibility and states.
- E2E:
  - authorized user sees/actions buttons.
  - unauthorized user cannot access flow.
- API still enforces auth even if UI bypass attempted.

Exit criteria:
- UX approved.
- RBAC validated end-to-end.

---

## Phase 4 — Hardening & Observability
**Goal:** production-grade reliability.

Tasks:
- Structured logs with `request_id` for export/archive.
- Metrics:
  - export duration,
  - zip size,
  - failures by error code.
- Large project safeguards:
  - streaming zip generation,
  - timeout boundaries,
  - memory usage guardrails.

Tests:
- Load/smoke test with large attachments set.
- Failure-injection tests (I/O errors, interrupted writes).
- Log contract tests.

Exit criteria:
- Stable behavior under stress.
- Actionable observability in place.

---

## Phase 5 — Documentation, Ops & Release
**Goal:** safe rollout and supportability.

Deliverables:
- User guide: Download vs Archive behavior.
- Admin guide: permissions setup for new modules.
- Runbook:
  - troubleshooting,
  - known limits,
  - integrity verification.
- Changelog/release notes.

Tests:
- Release smoke checklist:
  - fresh install,
  - upgrade path,
  - role matrix sanity.
- Manual UAT with at least:
  - admin role,
  - custom role,
  - archived project scenario.

Exit criteria:
- Documentation merged.
- UAT signed off.
- Production rollout approved.
