# 07 — Security and Access Control

## Authentication

- Username/password login
- HttpOnly session cookie with `SameSite=Strict`
- Server-side session validation

## HTTP Security Headers

All responses include the following security headers (added 2026-04-16):

| Header | Value |
|---|---|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'` |

Session cookie flags: `HttpOnly; SameSite=Strict; Path=/`

## Password storage

- Salted password hashing
- No plaintext password storage

## Authorization (RBAC)

Permissions are enforced in backend routes, including:

- project create/edit/delete constraints
- document/review-note actions
- admin-only user/invite/settings operations
- role-scoped admin behavior (`lider_projeto` without user/invite/settings access)

## Protection rules

- Prevent deleting admin accounts (policy)
- Prevent self-delete actions
- Require strong confirmation on destructive UI actions

## Auditing

Critical actions are recorded in `audit_logs`, including:

- user create/update/delete
- project create/update/delete
- document workflow events

## Rate Limiting

Login endpoint (`POST /api/login`) is protected by IP-based rate limiting (added 2026-04-16):

- **Window:** 5 attempts per 5 minutes per IP
- **Lockout:** 15-minute block after limit exceeded
- **Response:** HTTP 429 with wait time in seconds
- **Audit:** Every failed login is recorded in `audit_logs` with action `login.failed` and client IP

## Password Policy

New passwords are validated at all entry points (added 2026-04-16):

- Minimum 8 characters
- At least one letter (a-z or A-Z)
- At least one number or special character (`0-9`, `!@#$%^&*` etc.)

Validation is applied to: user creation, admin password update, own change-password, and signup via invite. Existing passwords are **not** retroactively invalidated.

## Hardening roadmap

1. Move sessions to Redis/DB-backed storage
2. ~~Add HTTP security headers and SameSite=Strict cookie~~ ✅ Implemented 2026-04-16
3. ~~Add rate limiting on login endpoint~~ ✅ Implemented 2026-04-16
4. ~~Add password complexity policy~~ ✅ Implemented 2026-04-16
5. Add CSRF token protections for mutating endpoints (mitigated by SameSite=Strict)
6. Centralize session invalidation controls
