# 08 — Operations and Deployment

## Automated Ubuntu Installation (Server/Desktop)

Script:
- `install.sh` (v2)

Basic usage:

```bash
cd /path/to/ProjectDashboard
sudo ./install.sh
```

Domain + HTTPS example:

```bash
sudo DOMAIN=dashboard.example.com LE_EMAIL=admin@example.com ./install.sh
```

## Installer Behavior (Current)

The installer configures:

- deployment into `/opt/projectdashboard`
- runtime folders under install path:
  - `/opt/projectdashboard/data`
  - `/opt/projectdashboard/data/docs_repo`
- domain folders:
  - `/opt/projectdashboard/documents`
  - `/opt/projectdashboard/projects`
- `projectdashboard.service` enabled at boot
- environment file `/etc/projectdashboard.env`
- environment keys:
  - `PDASH_HOST`
  - `PDASH_PORT`
  - `PDASH_PROJECTS_DIR`
  - `PDASH_DOCUMENTS_DIR`
  - `PDASH_INITIAL_PASSWORD`
  - `PDASH_FORCE_SECURE_COOKIE` (recommended `true` when HTTPS is enabled)
- optional Nginx reverse proxy
- optional Let's Encrypt HTTPS
- daily backup timer (`projectdashboard-backup.timer`)
- optional Ubuntu firewall setup via UFW (`ENABLE_UFW=yes`, default)
- bootstrap admin account: `admin` with password defined by `PDASH_INITIAL_PASSWORD`

After first login as admin, change the admin password immediately, then configure `/settings.html` (SMTP, defaults, backup policy, diagnostics, recoverable documents and periodic reports).

## Installer Variables

- `PORT` (default: `8765`)
- `PROJECTS_DIR` (default: `/opt/projectdashboard/projects`)
- `DOCUMENTS_DIR` (default: `/opt/projectdashboard/documents`)
- `ENABLE_NGINX=yes|no`
- `ENABLE_HTTPS=yes|no`
- `ENABLE_BACKUP_TIMER=yes|no`
- `ENABLE_UFW=yes|no`
- `BACKUP_DIR` (default: `/var/backups/projectdashboard`)
- `BACKUP_RETENTION_DAYS` (default: `14`)
- `INSTALL_SMOKE_TEST=yes|no` (default: `no`)
- `DOMAIN` (optional)
- `LE_EMAIL` (required for automatic cert issuance)
- `PDASH_INITIAL_PASSWORD` (recommended: set explicitly during first install)
- `PDASH_FORCE_SECURE_COOKIE=true|false` (recommended: `true` behind HTTPS)

## Upgrade from GitHub

Use the provided helper script:

```bash
sudo /opt/src/ProjectDashboard/scripts/upgrade_from_github.sh
```

Specific ref/tag:

```bash
sudo /opt/src/ProjectDashboard/scripts/upgrade_from_github.sh --ref v0.9.0-beta.2
```

The script performs:
- `git fetch --all --tags --prune`
- checkout of requested ref (or latest `develop`)
- pre-upgrade backup if `/opt/projectdashboard/scripts/backup.sh` exists
- reinstall/upgrade via `install.sh`
- optional pass-through of `DOMAIN`, `LE_EMAIL`, `ENABLE_NGINX`, `ENABLE_HTTPS`, `ENABLE_BACKUP_TIMER`, `ENABLE_UFW` and `INSTALL_SMOKE_TEST`

## Manual Execution (Development)

```bash
cd /path/to/ProjectDashboard
python3 app.py
```

Access:
- `http://127.0.0.1:8765/login.html`

## Dependencies

- Python 3.10+
- SQLite (bundled with Python)

## Backup Artifacts

Expected backup files:

- `projectdashboard-db-YYYY-MM-DD_HHMMSS.sqlite3`
- `projectdashboard-docs-repo-YYYY-MM-DD_HHMMSS.tar.gz`
- `projectdashboard-documents-YYYY-MM-DD_HHMMSS.tar.gz`

## Restore Summary

1. stop service
2. restore DB and optional archives
3. re-apply ownership
4. start service
5. validate login and key endpoints (preferably with smoke)

Use:
- `scripts/restore_backup.sh --help`
