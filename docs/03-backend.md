# 03 — Backend

## Configuration constants

Defined in `app.py` (environment-aware where applicable):

- host/port
- data paths
- session settings
- status/priority enumerations

## Utility functions

Backend utilities include:

- slug generation
- password hashing/verification
- JSON helpers
- DB access wrappers
- lightweight schema bootstrap/migration helpers

## Project domain routines

Main routines handle:

- project listing and retrieval
- project creation/update/deletion
- document upload and revision persistence
- review note lifecycle
- audit log generation

## Session management

Session flow is cookie-based with server-side session state.

- create session on successful login
- resolve current user from cookie token
- invalidate on logout/expiry

## Request handling

`Handler` routes HTTP methods and paths to domain routines.

- static file serving
- auth endpoints
- project endpoints
- admin endpoints

All sensitive routes validate authentication and role permissions in backend code.
