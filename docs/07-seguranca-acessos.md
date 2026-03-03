# 07 — Security and Access Control

## Authentication

- Username/password login
- HttpOnly session cookie
- Server-side session validation

## Password storage

- Salted password hashing
- No plaintext password storage

## Authorization (RBAC)

Permissions are enforced in backend routes, including:

- project create/edit/delete constraints
- document/review-note actions
- admin-only user management operations

## Protection rules

- Prevent deleting admin accounts (policy)
- Prevent self-delete actions
- Require strong confirmation on destructive UI actions

## Auditing

Critical actions are recorded in `audit_logs`, including:

- user create/update/delete
- project create/update/delete
- document workflow events

## Hardening roadmap

1. Move sessions to Redis/DB-backed storage
2. Add CSRF token protections for mutating endpoints
3. Add password complexity/rotation policies
4. Centralize session invalidation controls
