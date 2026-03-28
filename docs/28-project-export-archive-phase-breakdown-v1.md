# Project Export & Archive — Executable Task Breakdown (v1)

Reference spec: `docs/27-project-export-archive-spec-v1.md`

## Goal
Translate the approved spec into executable, testable delivery tasks with explicit DoD (Definition of Done) per phase.

---

## Phase 0 — Design Freeze & Contract Validation

## 0.1 Create export JSON contract examples
- Create canonical examples for:
  - `manifest.json`
  - `data/project-data.json`
  - `files/manifest-files.json`
- Place under: `docs/contracts/project-export-v1/`

**DoD**
- All 3 files exist and match the spec fields.
- JSON is valid and readable.

## 0.2 Add JSON schemas for validation
- Create JSON Schema files:
  - `manifest.schema.json`
  - `project-data.schema.json`
  - `manifest-files.schema.json`
- Place under: `docs/contracts/project-export-v1/schemas/`

**DoD**
- Schemas validate example contracts.
- Required fields are explicit.

## 0.3 Update permission/module catalog
- Add new modules:
  - `projects.export_download`
  - `projects.archive`
- Update role-module documentation in:
  - `docs/23-module-catalog-v1.md`
  - (if needed) `docs/21-role-module-access-control-plan.md`

**DoD**
- New modules documented with clear behavior.
- Role guidance (admin/custom role) defined.

## 0.4 Define archive policy baseline
- Document archived project behavior in a small policy note:
  - read-only rules for non-admin
  - admin override behavior

**DoD**
- Policy documented and linked from main spec.

## 0.5 Peer-review checklist (design gate)
- Create checklist with yes/no items for:
  - project scope isolation
  - naming convention
  - integrity/checksum
  - RBAC/UI/API consistency
  - archive atomicity rule

**DoD**
- Checklist file exists and is review-ready.

---

## Phase 1 — Backend Export Core

## 1.1 Implement export service skeleton
- Add service class/module for ZIP export generation.
- Include deterministic paths and naming convention.

## 1.2 Implement data extractors (project-scoped)
- Build extractors for project + cards + dependencies + history + reviews + attachment index.
- Hard filter by `project_id` in each query.

## 1.3 Implement files collector and folder writer
- Populate `files/by-card/` and `files/by-id/`.
- Build `files/manifest-files.json`.

## 1.4 Build checksums and top-level manifest
- Generate `checksums/sha256.txt`.
- Generate `manifest.json` with counts and references.

## 1.5 Add export API endpoint
- `POST /api/projects/{project_id}/export`

## 1.6 Add audit event + structured logs
- Log export request/result with `request_id`.

## 1.7 Tests for Phase 1
- Unit: formatter/checksum/path sanitizer
- Integration: strict scope/no leakage
- Endpoint smoke test

**Phase 1 DoD**
- Endpoint returns valid ZIP matching v1 contract.
- Tests pass.

---

## Phase 2 — Archive Workflow + Atomicity

## 2.1 Add archive state metadata
- Ensure project entity supports:
  - `archived`
  - `archived_at`
  - `archived_by`

## 2.2 Implement archive orchestration service
- Flow: export first -> archive state transition
- Fail-safe: no archive transition on export failure.

## 2.3 Add archive API endpoint
- `POST /api/projects/{project_id}/archive`

## 2.4 Enforce backend read-only guards
- Block mutating operations for archived projects (non-admin).

## 2.5 Tests for Phase 2
- Integration: archive success/failure rollback
- Authorization tests for `projects.archive`
- Behavior tests for read-only enforcement

**Phase 2 DoD**
- Archive is atomic and audited.
- Read-only protections active.

---

## Phase 3 — UI/RBAC Integration (Kanban)

## 3.1 Add top-right actions in Kanban
- Add buttons:
  - Download Project
  - Archive Project

## 3.2 Gate buttons by module permissions
- Module-first permission checks:
  - `projects.export_download`
  - `projects.archive`

## 3.3 Archive confirmation modal
- Confirm irreversible state transition.

## 3.4 UX feedback states
- Loading, success, error toasts/messages.

## 3.5 Tests for Phase 3
- Front-end visibility tests by role/module
- E2E action flow tests
- Ensure API auth still blocks bypass attempts

**Phase 3 DoD**
- Buttons visible only when authorized.
- End-to-end flow validated.

---

## Phase 4 — Hardening & Observability

## 4.1 Improve structured telemetry
- Add export/archive duration, artifact size, failure reason.

## 4.2 Handle large projects safely
- Streaming ZIP generation and memory-safe file handling.

## 4.3 Failure-injection tests
- Simulate I/O failure and verify graceful handling.

## 4.4 Operational diagnostics
- Add troubleshooting notes tied to request_id.

**Phase 4 DoD**
- Stable under stress and actionable diagnostics available.

---

## Phase 5 — Docs, Release, and UAT

## 5.1 User-facing docs
- How to use Download vs Archive.

## 5.2 Admin docs
- How to assign permissions and role examples.

## 5.3 Release checklist
- Fresh install / upgrade / role matrix / archive scenario.

## 5.4 UAT execution
- Validate with admin and custom role personas.

**Phase 5 DoD**
- Docs merged, UAT signed, release approved.

---

## Suggested Execution Order (short)
1. Phase 0 (contracts + permissions docs + checklist)
2. Phase 1 (export core)
3. Phase 2 (archive atomicity)
4. Phase 3 (UI)
5. Phase 4 (hardening)
6. Phase 5 (docs/release)
