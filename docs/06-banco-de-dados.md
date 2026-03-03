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

### `projects`
- slug (unique)
- name
- description
- status
- priority
- owner
- due_date
- document metadata
- created_by / updated_at

### `document_versions`
Stores immutable document revision metadata per project.

### `review_notes`
Stores review comments tied to project/revision workflow.

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
