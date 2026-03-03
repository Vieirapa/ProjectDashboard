# 02 — Architecture

## Runtime model

- Single Python backend (`app.py`) using `http.server`
- SQLite persistence (`data/projectdashboard.db`)
- Multi-page frontend in `web/`
- Optional systemd + Nginx deployment via `install.sh`

## Directory structure (high level)

- `app.py` — backend routes, auth, RBAC, persistence logic
- `web/` — static pages and JS modules
- `docs/` — technical documentation
- `data/` — runtime database/log/storage
- `install.sh` — server installer (v2)

## Main components

1. **HTTP Backend**
   - serves static frontend assets
   - exposes REST-style JSON API
   - validates sessions and permissions

2. **Persistence**
   - stores users, projects, invitations, audit logs, revision records

3. **Frontend pages**
   - `index.html` + `app.js`: Kanban board
   - `edit.html` + `edit.js`: full card details and revision timeline
   - `login/signup/admin-users` pages for auth/admin operations

## High-level flow

1. User logs in (`/api/login`)
2. Backend issues session cookie
3. Frontend consumes API endpoints for CRUD and workflow actions
4. Backend applies RBAC checks
5. Sensitive actions are stored in audit logs
