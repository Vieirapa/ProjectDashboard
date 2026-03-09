# 05 — Frontend

## Pages and responsibilities

- `index.html` + `dashboard.js`
  - landing page with summary KPIs
  - project-level quick metrics table
  - excludes template projects from summary/statistics

- `kanban.html` + `app.js`
  - main board rendering
  - document creation
  - quick status/priority changes
  - filtering/searching
  - per-user behavior support (optional priority-based card colors)

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
Admin controls are shown only for `admin`.
`lider_projeto` sees workspace tools (Início, Projetos, Kanban, Meu perfil) but not Users/Invites and Settings links.

## Important security note

Frontend visibility is a UX layer only.
All critical access checks are enforced server-side.
