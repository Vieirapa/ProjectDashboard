# ProjectDashboard

ProjectDashboard is a lightweight Kanban-style web application to track documents, file revisions, and team actions.

## Current highlights

- Landing page (`/`) with project summary KPIs
- Dedicated Kanban page (`/kanban.html?project_id=...`)
- Sidebar-based UI with workspace/admin sections
- User login and role-based access control (RBAC)
- Dedicated details page for full document editing (`/edit.html?slug=...`)
- Document creation and quick status/priority updates
- Filters (text, status, priority, owner)
- Audit logging for critical operations
- User administration (`/admin-users.html`) and invites
- Document upload with revision history (`r1`, `r2`, `r3`...)
- Review notes workflow
- Deleted documents management (restore + permanent purge)
- Backup + diagnostics in admin settings
- Profile behavior customization (optional card color by priority per user)

## Roles

- `admin`
  - Full access, including Users/Invites and Settings
- `lider_projeto`
  - Admin-equivalent for operations, Kanban and Projects
  - Does **not** access Users/Invites and Settings
- `member`
  - Create/edit documents, no admin panel access
- `desenhista`
  - Edit documents and resolve review notes
- `colaborador`
  - Same operational permissions as `desenhista`
- `revisor`
  - Add review notes (stage-restricted)
- `cliente`
  - Read-only style/project-restricted access (according to project role allowlist)

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

For customer-facing installation and validation docs, use:

- `docs/08-operacao-deploy.md` (installation and deployment)
- `docs/12-backup-permissions-setup.md` (backup/restore and permissions)
- `docs/tests/checklists/ubuntu-ubuntu-server-acceptance-checklist.md` (acceptance checklist)
- `docs/tests/runs/` (test execution history)


```bash
cd /path/to/ProjectDashboard
sudo ./install.sh
```

Installer v2 includes (Ubuntu Server or Desktop):

- system user/service setup (`projectdashboard`)
- deployment to `/opt/projectdashboard`
- systemd service enable/start (auto-start on machine boot)
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
- `DOCUMENTS_DIR` (default: `/opt/projectdashboard/documents`)
- `ENABLE_NGINX=yes|no`
- `ENABLE_HTTPS=yes|no`
- `ENABLE_BACKUP_TIMER=yes|no`
- `BACKUP_DIR` (default: `/var/backups/projectdashboard`)
- `BACKUP_RETENTION_DAYS` (default: `14`)
- `INSTALL_SMOKE_TEST=yes|no` (default: `no`)

## Simple Ubuntu installation (step-by-step)

Use this when you want the fastest setup on a fresh Ubuntu server.

### 1) Connect to the server

```bash
ssh <your-user>@<your-server-ip>
```

### 2) Install Git (if needed)

```bash
sudo apt-get update
sudo apt-get install -y git
```

### 3) Clone the repository

```bash
git clone https://github.com/Vieirapa/ProjectDashboard.git
cd ProjectDashboard
```

### 4) Run the installer

Basic install (no domain/HTTPS yet):

```bash
sudo ./install.sh
```

Install with domain + automatic HTTPS:

```bash
sudo DOMAIN=dashboard.example.com LE_EMAIL=admin@example.com ./install.sh
```

### 5) Check that services are running

```bash
sudo systemctl status projectdashboard --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status projectdashboard-backup.timer --no-pager
```

### 6) Open firewall (if UFW is enabled)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 7) Access the app

- With domain: `https://dashboard.example.com/login.html`
- Without domain: `http://<server-ip>/login.html` (or `http://<server-ip>:8765/login.html` if Nginx is disabled)

### 8) First login

- username: `admin`
- password: `admin`

Then immediately change the admin password.

### 9) Configure email + periodic reports

After login as admin, open:

- `/settings.html`

From there you can configure:

- SMTP parameters (host, port, user, password, sender, TLS)
- Invite default message template
- SMTP test send
- Default due-days behavior
- Periodic report schedules

## Post-install access checklist (VM + host machine)

Use this checklist to validate that installation and networking are working.

### A) Validate services inside the Ubuntu VM

```bash
sudo systemctl status projectdashboard --no-pager
sudo systemctl status nginx --no-pager
sudo ss -ltnp | grep -E ':80|:8765' || true
curl -i http://127.0.0.1/
```

Expected:

- `projectdashboard`: active (running)
- `nginx`: active (running)
- port `80` listening (nginx)
- `curl http://127.0.0.1/` returns HTTP 200 (not 502)

If `projectdashboard` fails:

```bash
sudo journalctl -u projectdashboard -n 120 --no-pager
```

### B) Validate host -> VM access (VirtualBox)

#### Option 1: NAT mode (requires port forwarding)

Create a NAT rule in VirtualBox:

- Host Port: `8080`
- Guest Port: `80`
- Protocol: `TCP`

Then access from host machine:

- `http://127.0.0.1:8080/`

#### Option 2: Bridged Adapter mode

Get VM IP:

```bash
ip a
```

Then access from host machine:

- `http://<VM_IP>/`

### C) Firewall check (inside VM)

If UFW is enabled:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw status
```

## SMTP setup for invite emails

Detailed guide:

- `docs/11-email-smtp-setup.md`

Helper scripts:

- `scripts/setup_smtp_env.sh` (interactive SMTP env setup in `/etc/projectdashboard.env`)
- `scripts/test_smtp.py` (send a test email using current env vars)

Quick usage:

```bash
sudo ./scripts/setup_smtp_env.sh
set -a; source /etc/projectdashboard.env; set +a
./scripts/test_smtp.py your@email.com
```

## Upgrade from GitHub (SSH-only friendly)

Use the upgrade helper script on the server:

```bash
sudo /opt/src/ProjectDashboard/scripts/upgrade_from_github.sh
```

Deploy a specific version/tag:

```bash
sudo /opt/src/ProjectDashboard/scripts/upgrade_from_github.sh --ref v0.9.0-beta.2
```

This script:
- fetches from GitHub
- checks out latest `develop` (or your `--ref`)
- runs pre-upgrade backup (when available)
- runs `install.sh` with your selected flags

## Full documentation

See:

- `docs/README.md`
