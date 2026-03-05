# 04 — API Reference

## Auth / Session

### `POST /api/login`
Authenticates user credentials and creates a session cookie.

### `POST /api/logout`
Terminates current session.

### `GET /api/me`
Returns current authenticated user context.

## Documents

### `GET /api/documents`
Returns board data (documents + enumerations).

### `POST /api/documents`
Creates a new document.

### `GET /api/documents/:slug`
Returns one document.

### `PATCH /api/documents/:slug`
Updates document fields (name, description, status, priority, owner, due date).

### `DELETE /api/documents/:slug`
Deletes a document (permission-protected).

## Documents and revisions

### `POST /api/documents/:slug/document`
Uploads/replaces document file and creates a new revision record.

### `GET /api/documents/:slug/document`
Downloads latest or selected revision file.

### `GET /api/documents/:slug/document/versions`
Returns revision timeline metadata.

## Review notes

### `GET /api/documents/:slug/review-notes`
Lists notes attached to document review stage.

### `POST /api/documents/:slug/review-notes`
Creates a review note (permission/stage validation applies).

## Admin

### `GET /api/admin/users`
List users and role/account metadata (admin-only).

### `POST /api/admin/users`
Create user (admin-only).

### `PATCH /api/admin/users/:username`
Update role/password (admin-only).

### `DELETE /api/admin/users/:username`
Delete user with safety constraints (admin-only).

### `GET /api/admin/settings`
Returns admin settings (SMTP, workflow defaults, backups, diagnostics).

### `PATCH /api/admin/settings`
Updates admin settings.

### `POST /api/admin/settings/test-smtp`
Send SMTP test email.

### `POST /api/admin/system/backup/run`
Run system backup now.

### `GET /api/admin/system/diagnostics`
Run system diagnostics.

### `GET /api/admin/deleted-documents`
List deleted documents and retention policy.

### `POST /api/admin/deleted-documents/:id/restore`
Restore a deleted document.

### `DELETE /api/admin/deleted-documents/:id`
Permanently delete a deleted document.

### `GET /api/admin/reports`
List periodic reports.

### `POST /api/admin/reports`
Create periodic report.

### `PATCH /api/admin/reports/:id`
Update periodic report.

### `DELETE /api/admin/reports/:id`
Delete periodic report.

### `POST /api/admin/reports/:id/run`
Run periodic report now.
