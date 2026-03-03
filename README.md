# ProjectDashboard

ProjectDashboard is a lightweight Kanban-style web application to track projects, file revisions, and team actions.

## Current highlights

- Sidebar-based UI with workspace/admin sections
- User login and role-based access control (RBAC)
- Dedicated details page for full card editing (`/edit.html?slug=...`)
- Card creation and quick status/priority updates
- Filters (text, status, priority, owner)
- Audit logging for critical operations
- User administration (`/admin-users.html`)
- Document upload with revision history (`r1`, `r2`, `r3`...)
- Review notes workflow

## Roles

- `admin`
  - Full access, user management, sensitive deletions
- `member`
  - Create/edit cards, no admin panel access
- Additional roles may exist in UI/backend depending on workflow extensions.

## Data layer

The application currently uses SQLite:

- `data/projectdashboard.db`

This keeps deployment simple while preserving a future migration path to PostgreSQL/MySQL.

## Default user

On first boot, the app creates an admin account:

- username: `admin`
- password: `admin123` (or value from `PDASH_INITIAL_PASSWORD`)

> Change this password immediately after first login.

## Run locally

```bash
cd /path/to/ProjectDashboard
python3 app.py
```

Open:

- `http://127.0.0.1:8765/login.html`

## Server installer (v2)

```bash
cd /path/to/ProjectDashboard
sudo ./install.sh
```

Installer v2 includes:

- system user/service setup (`projectdashboard`)
- deployment to `/opt/projectdashboard`
- systemd service enable/start
- optional Nginx reverse proxy
- optional Let's Encrypt HTTPS
- daily backup timer
- enforced bootstrap admin user: `admin` / `admin`

### Example with domain + HTTPS

```bash
sudo DOMAIN=dashboard.example.com LE_EMAIL=admin@example.com ./install.sh
```

### Useful installer variables

- `PORT` (default: `8765`)
- `ENABLE_NGINX=yes|no`
- `ENABLE_HTTPS=yes|no`
- `ENABLE_BACKUP_TIMER=yes|no`
- `BACKUP_DIR` (default: `/var/backups/projectdashboard`)
- `BACKUP_RETENTION_DAYS` (default: `14`)

## Full documentation

See:

- `docs/README.md`
