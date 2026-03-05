# 05 — Frontend

## Pages and responsibilities

- `index.html` + `app.js`
  - main board rendering
  - document creation
  - quick status/priority changes
  - filtering/searching

- `edit.html` + `edit.js`
  - full project editing
  - document upload
  - revision history (`r1`, `r2`, ...)
  - review notes panel

- `login.html` + `login.js`
  - user authentication

- `signup.html` + `signup.js`
  - invitation/token-based signup flow (if enabled)

- `admin-users.html` + `admin-users.js`
  - user administration (admin-only in backend)

## Navigation and sidebar

The UI is split into workspace and admin sections.
Admin controls may be hidden in the frontend for non-admin users.

## Important security note

Frontend visibility is a UX layer only.
All critical access checks are enforced server-side.
