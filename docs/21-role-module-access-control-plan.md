# Role-Based Module Access Control Plan

## Objective

Evolve ProjectDashboard from the current access model (focused on Tools/menu visibility) to a **module-based access control model** managed by administrators, with robust backend enforcement.

This plan defines the phased implementation to:

- Modularize existing forms/areas into explicit modules.
- Standardize module naming for UI and technical references.
- Introduce role × module permission management.
- Enforce permissions in both UI and backend.

---

## Architectural Principles

1. **Two-layer authorization (mandatory)**
   - **UI layer:** show/hide modules according to permission.
   - **Backend/API layer:** enforce access server-side (return 403 when denied).

2. **Stable technical module IDs**
   - Labels can change over time.
   - `module_id` values must stay stable for compatibility and auditing.

3. **Immutable ADMIN role**
   - `ADMIN` is not editable in role-module matrix.
   - `ADMIN` always has full access to all modules.

4. **Auditability by default**
   - All permission changes must generate auditable events.

---

## Phase 1 — Module Cataloging and Naming Standardization

### 1.1 Current areas mapped as modules

#### `projects.html`
- `projects.create_edit` → **Create/Edit Project**
- `projects.list` → **Registered Projects**
- `projects.cards_list` → **Cards List**

#### `admin-users.html`
- `admin_users.create` → **Create User**
- `admin_users.invite` → **Invite New User**
- `admin_users.list` → **Registered Users**
- `admin_users.audit_log` → **Audit Log**

#### `settings.html`
- `settings.smtp` → **Email Sending (SMTP)**
- `settings.system_behavior` → **System Behavior**
- `settings.backup` → **System Backup**
- `settings.backup_restore` → **Backup Recovery**
- `settings.system_diagnostics` → **System Diagnostics**
- `settings.recoverable_documents` → **Recoverable Documents**
- `settings.periodic_reports` → **Periodic Reports**
- `settings.roles_control` → **Roles Control** *(new module introduced in Phase 3)*

### 1.2 UI label adjustments

- "New project creation form (...)" → **Create/Edit Project**
- "Create user directly" → **Create User**
- "Generate invitation" → **Invite New User**
- "Deleted documents (Admin)" → **Recoverable Documents**

### Phase 1 Deliverables

- Official module catalog (`module_id`, `page`, `label`, `description`).
- Updated labels in UI.
- Documentation update describing module boundaries.

---

## Phase 2 — Permission Data Model (Backend)

### 2.1 New database structures

#### `app_modules`
Canonical module registry.

- `module_id` (PK, e.g., `settings.smtp`)
- `page_key` (e.g., `settings.html`)
- `label`
- `active` (boolean)
- `created_at`

#### `role_modules`
Role-module permission matrix.

- `id`
- `role_name`
- `module_id` (FK to `app_modules.module_id`)
- `can_access` (boolean)
- `updated_at`
- `updated_by`

### 2.2 Business rules

- `ADMIN` always resolves to `can_access=true` for all modules.
- Editing `ADMIN` permissions is blocked by API.
- Invalid `role_name` or `module_id` returns validation error.
- New-role default behavior must be defined during implementation:
  - Option A: deny-all by default.
  - Option B: baseline read-only profile.

### 2.3 API endpoints (proposed)

- `GET /modules/catalog` → module catalog
- `GET /roles/modules` → full role × module matrix
- `PUT /roles/{role}/modules` → batch update role permissions
- `POST /modules/catalog/sync` *(admin-only, optional)* → sync known modules from code/config

### Phase 2 Deliverables

- DB migration + seed for module catalog.
- Validated role-module APIs.
- Unit/integration tests for core rules.

---

## Phase 3 — New "Roles Control" Module in `settings.html`

### 3.1 UI matrix

Render a table with:

- Rows: roles
- Columns: modules
- Cells: checkbox (`can_access`)

### 3.2 UX requirements

- "Select all" / "Clear all" per role
- Module search/filter
- Single "Save changes" action (batch update)
- Visual badge for `ADMIN` row (`Full access / Locked`)

### 3.3 Access rules for this module

- `settings.roles_control` should be visible only to authorized role(s).
- Recommended default: only `ADMIN`.

### Phase 3 Deliverables

- Working role-module matrix in settings.
- Batch save flow with success/error feedback.
- Locked behavior for `ADMIN` row.

---

## Phase 4 — Real Enforcement (Backend + Frontend)

### 4.1 Backend enforcement (mandatory)

- Introduce permission guard/middleware by `module_id`.
- Map sensitive routes/actions to module IDs.
- Return 403 for unauthorized access attempts.

### 4.2 Frontend enforcement

- Render module sections conditionally.
- Prevent navigation to unauthorized modules.
- Show friendly "Access denied" fallback where needed.

### 4.3 Auditing

Record permission change events, including:

- Actor user ID / role
- Target role
- Before/after permission diff
- Timestamp
- Event key (e.g., `roles.modules.updated`)

### Phase 4 Deliverables

- End-to-end access enforcement.
- Reliable audit logs for governance.
- Anti-bypass tests (direct URL/API attempts).

---

## Phase 5 — QA, Rollout, and Operational Safety

### 5.1 Test matrix (minimum)

- `ADMIN` can access all modules.
- Custom role A can access only granted modules.
- Custom role B is denied where not granted.
- Direct API access without permission returns 403.
- Attempts to modify `ADMIN` matrix are blocked.

### 5.2 Safe rollout

1. Pre-deploy backup (DB + documents/data).
2. Deploy to validation/staging environment.
3. Smoke test critical flows.
4. Deploy to production.
5. Keep rollback steps ready and tested.

---

## Definition of Done

- [ ] All listed modules defined with stable IDs.
- [ ] Naming updates applied in UI.
- [ ] Role-module matrix persisted in DB.
- [ ] "Roles Control" module available in settings.
- [ ] `ADMIN` immutable + full-access behavior enforced.
- [ ] Backend route protection enabled.
- [ ] Audit trail for permission changes enabled.
- [ ] Authorization tests passing.

---

## Decisions Pending Review

1. **Default permissions for newly created roles**
   - A) Deny all
   - B) Baseline read profile

2. **Who can access Roles Control**
   - A) Only `ADMIN`
   - B) `ADMIN` + selected governance roles

3. **Initial rollout scope**
   - A) Only modules listed in this plan (MVP)
   - B) Extend immediately to all existing modules/routes
