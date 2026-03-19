# Technical Execution Plan — Role-Based Module Access Control

## Scope

This document defines the implementation sequence for the role-based module access control initiative, including commit order and target files per phase.

Related plan: `docs/21-role-module-access-control-plan.md`

---

## Branching Strategy

- Base branch: `develop`
- Work branch (recommended): `feature/role-module-access-control`
- Merge strategy: squash merge into `develop` after each validated phase or grouped milestones.

> For this cycle, we can also deliver directly in `develop` with small, traceable commits.

---

## Commit Order (by phase)

## Phase 1 — Module Catalog + Naming Standardization

### Commit 1.1 — Add execution artifacts and module catalog
**Goal:** create canonical inventory of modules and labels.

**Files:**
- `docs/22-technical-execution-plan-role-modules.md` (this file)
- `docs/23-module-catalog-v1.md` *(new)*

**Commit message (suggested):**
- `docs: add technical execution plan and v1 module catalog`

### Commit 1.2 — Apply UI naming updates and module boundaries
**Goal:** make module names explicit in UI and align with catalog.

**Files:**
- `web/projects.html`
- `web/admin-users.html`
- `web/settings.html`
- `docs/05-frontend.md` *(optional reference update)*

**Changes:**
- Rename visible module titles:
  - Create/Edit Project
  - Create User
  - Invite New User
  - Recoverable Documents
- Add stable `data-module-id` markers at section level.

**Commit message (suggested):**
- `feat(ui): standardize module names and add module-id markers`

### Commit 1.3 — Validate and document
**Goal:** ensure no regressions and preserve traceability.

**Files:**
- `docs/CHANGELOG.md` or `CHANGELOG.md` (if used)
- `docs/23-module-catalog-v1.md` (status updates if needed)

**Checks:**
- Navigation/static checks
- Smoke loading of affected pages

**Commit message (suggested):**
- `docs: record phase-1 module standardization completion`

---

## Phase 2 — Data Model + APIs

### Commit 2.1 — DB migration for module registry and role matrix
**Files (expected):**
- `app.py` *(or DB migration helper area in project structure)*
- `data/...` migration script(s) if available
- `docs/06-banco-de-dados.md`

**Commit message:**
- `feat(authz): add app_modules and role_modules persistence`

### Commit 2.2 — Seed module catalog and backend service methods
**Files (expected):**
- `app.py`
- `docs/04-api.md`

**Commit message:**
- `feat(authz): seed module catalog and add role-module service layer`

### Commit 2.3 — Expose role-module endpoints
**Files (expected):**
- `app.py`
- `docs/04-api.md`

**Commit message:**
- `feat(api): add role-module catalog and matrix endpoints`

---

## Phase 3 — Settings UI: Roles Control Module

### Commit 3.1 — Add settings module container and table scaffold
**Files:**
- `web/settings.html`
- `web/styles.css` (if layout tweaks needed)

**Commit message:**
- `feat(settings): add roles control module scaffold`

### Commit 3.2 — Implement roles matrix interaction
**Files:**
- `web/settings.js`
- `web/settings.html`

**Commit message:**
- `feat(settings): implement role-module matrix interactions`

### Commit 3.3 — Save flow + locked ADMIN behavior
**Files:**
- `web/settings.js`
- `app.py`

**Commit message:**
- `feat(authz): persist matrix updates with immutable admin role`

---

## Phase 4 — Authorization Enforcement

### Commit 4.1 — Backend guard by module ID
**Files:**
- `app.py`

**Commit message:**
- `feat(authz): enforce module-level permissions on protected routes`

### Commit 4.2 — Frontend gating by module permissions
**Files:**
- `web/sidebar.js`
- `web/settings.js`
- `web/projects.js`
- `web/admin-users.js`

**Commit message:**
- `feat(ui): gate module rendering and navigation by permissions`

### Commit 4.3 — Audit events for permission updates
**Files:**
- `app.py`
- `docs/07-seguranca-acessos.md`

**Commit message:**
- `feat(audit): log role-module permission changes with diffs`

---

## Phase 5 — QA + Rollout Safety

### Commit 5.1 — Add/expand authorization tests
**Files:**
- `docs/tests/*` and/or existing test scripts
- `scripts/*` (if smoke automation added)

**Commit message:**
- `test(authz): add matrix access and anti-bypass coverage`

### Commit 5.2 — Rollout checklist + rollback documentation
**Files:**
- `docs/08-operacao-deploy.md`
- `docs/09-manutencao-evolucao.md`

**Commit message:**
- `docs(ops): add rollout and rollback guide for role-module control`

---

## Validation Checklist per Phase

For every phase:

1. Run local checks (navigation/static + relevant smoke tests).
2. Verify no unauthorized UI regressions.
3. Validate API behavior for allowed/denied users.
4. Commit in small units with explicit messages.
5. Push to GitHub and report checkpoint:
   - Done
   - In progress
   - Next step

---

## Current Execution State

- [x] Plan document (`21`) created and pushed.
- [ ] Technical execution plan (`22`) created and pushed.
- [ ] Phase 1 implementation started.
- [ ] Phase 1 completed and pushed.
