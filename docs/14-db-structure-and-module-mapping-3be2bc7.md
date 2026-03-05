# 14 — Database Structure and Module Mapping (baseline: `3be2bc7`)

This document describes the **current SQLite data model** and how each ProjectDashboard module interacts with it at the baseline commit:

- `3be2bc75a9c5b8f4e5a9de10f81e9969d02c6b78`

## 1) Database overview

- Engine: **SQLite**
- Main file: `data/projectdashboard.db`
- Initialization/migrations: `init_db()` in `app.py`
- Pattern: table creation + additive migrations via `ensure_column(...)`

## 2) Tables

### `users`
Authentication identities + roles + profile fields.

Main columns:
- `id` (PK)
- `username` (UNIQUE)
- `password_hash`
- `role`
- `created_at`
- `email`, `phone`, `extension`, `work_area`, `notes`

### `projects`
Kanban document cards.

Main columns:
- `id` (PK)
- `slug` (UNIQUE)
- `name`, `status`, `priority`, `owner`, `due_date`
- `description`, `path`, `updated_at`
- `document_status`, `document_name`, `document_mime`, `document_path`
- `created_by`, `opened_at`, `released_at`

### `invites`
Invitation links for onboarding.

Columns:
- `id` (PK), `token` (UNIQUE), `role`, `created_by`, `used_by`, `expires_at`, `created_at`

### `audit_logs`
Audit trail.

Columns:
- `id` (PK), `actor`, `action`, `target`, `details`, `created_at`

### `document_versions`
Document version metadata/history.

Columns:
- `id` (PK)
- `document_slug`, `version`
- `document_name`, `document_mime`, `document_status`
- `file_rel_path`, `git_commit`, `checksum`
- `created_by`, `created_at`

Constraint:
- `UNIQUE(document_slug, version)`

### `review_notes`
Review notes and resolution state.

Columns:
- `id` (PK)
- `document_slug`, `note`, `created_by`, `created_at`
- `resolved_by`, `resolved_at`, `is_resolved`

### `app_settings`
System key-value settings.

Columns:
- `key` (PK), `value`, `updated_by`, `updated_at`

### `periodic_reports`
Periodic reporting configuration + runtime state.

Columns:
- `id` (PK), `name`
- `statuses_json`, `priorities_json`, `roles_json`, `weekdays_json`
- `run_time`, `message`, `active`, `last_run_key`
- `created_by`, `created_at`, `updated_by`, `updated_at`

### `deleted_documents`
Soft-delete archive for deleted cards/documents.

Columns:
- `id` (PK), `slug`, `name`, `deleted_at`, `deleted_by`, `trash_path`
- `project_json`, `review_notes_json`, `document_versions_json`

## 3) Module → DB mapping

### A) Authentication / Identity
Frontend:
- `web/login.html`, `web/login.js`, `web/profile.html`, `web/profile.js`

Backend/API:
- `/api/login`, `/api/logout`, `/api/me`, `/api/me/change-password`

Tables:
- `users`, `audit_logs`

### B) Kanban (document cards)
Frontend:
- `web/index.html`, `web/app.js`, `web/edit.html`, `web/edit.js`

Backend/API:
- `/api/projects` (GET/POST)
- `/api/documents/{slug}` (GET/PATCH/DELETE)

Tables:
- `projects`, `audit_logs`

### C) Document upload + history
Frontend:
- Edit screen (document upload + version list)

Backend/API:
- `/api/documents/{slug}/document` (POST/GET)
- `/api/documents/{slug}/document/versions`

Tables:
- `projects`, `document_versions`

Storage:
- `data/docs_repo/...`

### D) Review notes
Frontend:
- Edit screen review panel

Backend/API:
- `/api/documents/{slug}/review-notes` (GET/POST)
- `/api/documents/{slug}/review-notes/{id}` (PATCH)

Tables:
- `review_notes`, `projects`, `audit_logs`

### E) Admin users + invites
Frontend:
- `web/admin-users.html`, `web/admin-users.js`

Backend/API:
- `/api/admin/users`
- `/api/admin/invites`

Tables:
- `users`, `invites`, `audit_logs`

### F) Settings, backup, diagnostics
Frontend:
- `web/settings.html`, `web/settings.js`

Backend/API:
- `/api/admin/settings`
- `/api/admin/settings/test-smtp`
- `/api/admin/system/backup/run`
- `/api/admin/system/diagnostics`

Tables:
- `app_settings`, `audit_logs`

### G) Periodic reports
Frontend:
- Settings > periodic reports section

Backend/API:
- `/api/admin/reports` (+ run/update/delete)

Tables:
- `periodic_reports`, `users`, `projects`, `audit_logs`

### H) Deleted documents lifecycle
Frontend:
- Settings > deleted documents section

Backend/API:
- list deleted documents
- restore
- permanent delete

Tables:
- `deleted_documents`, `projects`, `review_notes`, `document_versions`, `audit_logs`

Storage:
- `data/deleted_documents/...`

## 4) Quick ER diagram (Mermaid)

```mermaid
erDiagram
    USERS {
        int id PK
        string username UK
        string password_hash
        string role
        string created_at
        string email
        string phone
        string extension
        string work_area
        string notes
    }

    DOCUMENTS {
        int id PK
        string slug UK
        string name
        string status
        string priority
        string owner
        string due_date
        string description
        string path
        string updated_at
        string document_status
        string document_name
        string document_mime
        string document_path
        string created_by
        string opened_at
        string released_at
    }

    DOCUMENT_VERSIONS {
        int id PK
        string document_slug
        int version
        string document_name
        string document_mime
        string document_status
        string file_rel_path
        string git_commit
        string checksum
        string created_by
        string created_at
    }

    REVIEW_NOTES {
        int id PK
        string document_slug
        string note
        string created_by
        string created_at
        string resolved_by
        string resolved_at
        int is_resolved
    }

    INVITES {
        int id PK
        string token UK
        string role
        string created_by
        string used_by
        string expires_at
        string created_at
    }

    AUDIT_LOGS {
        int id PK
        string actor
        string action
        string target
        string details
        string created_at
    }

    APP_SETTINGS {
        string key PK
        string value
        string updated_by
        string updated_at
    }

    PERIODIC_REPORTS {
        int id PK
        string name
        string statuses_json
        string priorities_json
        string roles_json
        string weekdays_json
        string run_time
        string message
        int active
        string last_run_key
        string created_by
        string created_at
        string updated_by
        string updated_at
    }

    DELETED_DOCUMENTS {
        int id PK
        string slug
        string name
        string deleted_at
        string deleted_by
        string trash_path
        string project_json
        string review_notes_json
        string document_versions_json
    }

    PROJECTS ||--o{ DOCUMENT_VERSIONS : "slug -> document_slug"
    PROJECTS ||--o{ REVIEW_NOTES : "slug -> document_slug"
```

## 5) Compact ER diagram (meeting view)

```mermaid
erDiagram
    USERS {
        int id PK
        string username UK
        string role
    }

    DOCUMENTS {
        int id PK
        string slug UK
        string name
        string status
        string priority
        string owner
    }

    DOCUMENT_VERSIONS {
        int id PK
        string document_slug
        int version
    }

    REVIEW_NOTES {
        int id PK
        string document_slug
        int is_resolved
    }

    APP_SETTINGS {
        string key PK
        string value
    }

    PERIODIC_REPORTS {
        int id PK
        string name
        int active
    }

    DELETED_DOCUMENTS {
        int id PK
        string slug
        string deleted_at
    }

    PROJECTS ||--o{ DOCUMENT_VERSIONS : "document history"
    PROJECTS ||--o{ REVIEW_NOTES : "review flow"
```

## 6) Logical relations

- `projects.slug` ↔ `review_notes.document_slug`
- `projects.slug` ↔ `document_versions.document_slug`
- `deleted_documents` stores serialized snapshot data for restore.

Note: consistency is primarily enforced by application logic (not strict SQL foreign keys).
