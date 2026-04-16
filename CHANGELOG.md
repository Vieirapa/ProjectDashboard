# Changelog

## Unreleased

### Security
- Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, and `Content-Security-Policy` headers to all HTTP responses.
- Upgrade session cookie to `SameSite=Strict` (was `SameSite=Lax`).
- Add IP-based rate limiting on `/api/login`: 5 attempts per 5-minute window, 15-minute lockout. Failed logins are now recorded in `audit_logs`.
- Enforce 100 MB request body limit in `_read_json()` and raise decoded file size limit from 12 MB to 50 MB. Expose `uploadLimitMb` in `/api/me` response.

### Fixed
- System diagnostics now default to the `develop` branch when no explicit `system.git_branch` setting is stored, aligning version checks with the active development flow.

## v0.9.0-beta.2 (2026-03-09)

### Added
- New landing page (`/`) with project summary KPIs.
- Dedicated Kanban route (`/kanban.html?project_id=...`).
- New roles: `colaborador` and `lider_projeto`.
- Per-user behavior settings in Profile, including optional priority-based card colors.

### Changed
- Sidebar and RBAC behavior refined for `lider_projeto`:
  - has access to Home, Projects, Kanban, Profile, Logout
  - no access to Users/Invites and Settings tools
- Landing page now excludes template projects from visible lists and KPI calculations.
- Project cards list in `projects.html` no longer shows the `Slug` column.
- Allowed roles persistence fixed: empty selection now correctly means admin-only project access.

### Docs & Ops
- Documentation refreshed (overview, API, frontend, security, DB, deploy, known bugs, wishlist).
- Ubuntu installer aligned with current behavior and routes.
- Added optional installer smoke test mode: `INSTALL_SMOKE_TEST=yes`.
