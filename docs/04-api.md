# 04 — API Reference

## Auth / Session

### `POST /api/login`
Authenticates user credentials and creates a session cookie.

### `POST /api/logout`
Terminates current session.

### `GET /api/me`
Returns current authenticated user context.

## Projects

### `GET /api/projects`
Returns board data (projects + enumerations).

### `POST /api/projects`
Creates a new project card.

### `GET /api/documents/:slug`
Returns one project.

### `PATCH /api/documents/:slug`
Updates project fields (name, description, status, priority, owner, due date).

### `DELETE /api/documents/:slug`
Deletes a project (permission-protected).

## Documents and revisions

### `POST /api/documents/:slug/document`
Uploads/replaces project document and creates a new revision record.

### `GET /api/documents/:slug/document`
Downloads latest or selected revision document.

### `GET /api/documents/:slug/document/versions`
Returns revision timeline metadata.

## Review notes

### `GET /api/documents/:slug/review-notes`
Lists notes attached to project review stage.

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
