# 10 — File Map

## Root

- `app.py`
  - HTTP server, routing, auth/session, RBAC, persistence logic
- `install.sh`
  - automated deployment script (systemd/nginx/https/backup)
- `scripts/setup_smtp_env.sh`
  - interactive SMTP environment setup helper
- `scripts/test_smtp.py`
  - SMTP test message utility
- `README.md`
  - project overview and quick start

## `web/`

- `index.html`, `app.js` — board UI and document operations
- `edit.html`, `edit.js` — details page, uploads, revisions, review notes
- `login.html`, `login.js` — authentication UI
- `signup.html`, `signup.js` — signup/invite flow
- `admin-users.html`, `admin-users.js` — admin user management
- `styles.css` — global styles

## `docs/`

Technical and operational reference files.

## `data/`

Runtime artifacts (generated at runtime):

- SQLite database
- optional logs
- optional document storage repository
