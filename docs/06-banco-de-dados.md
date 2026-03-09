# 06 — Database

## Engine

- SQLite (`data/projectdashboard.db`)

## Main tables

### `users`
- id
- username (unique)
- password_hash
- role
- created_at
- email/phone/extension/work_area/notes
- profile behavior preferences:
  - `priority_color_enabled`
  - `priority_colors_json`

### `documents`
- slug (unique)
- name
- description
- status
- priority
- owner
- due_date
- document metadata (document_status, document_name, document_mime, document_path)
- created_by / updated_at / opened_at / released_at

### `document_versions`
Stores immutable document revision metadata per document.

### `review_notes`
Stores review comments tied to document/revision workflow.

### `deleted_documents`
Soft-delete archive for removed documents (restore/purge).

### `app_settings`
Key-value operational settings.

### `periodic_reports`
Periodic report schedules and settings.

### `invites`
User invitation tokens.

### `audit_logs`
Stores sensitive action audit records.

## Migration approach (current)

The app uses lightweight bootstrap/migration logic in code:

- `CREATE TABLE IF NOT EXISTS`
- targeted `ensure_column(...)` style additions

## Recommended future direction

Adopt formal migrations for growth and team collaboration:

- Alembic (if SQLAlchemy is adopted)
- or versioned SQL migration scripts
