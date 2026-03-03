# 08 — Operations and Deployment

## Automated server installation

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

Installer output includes:

- deployment to `/opt/projectdashboard`
- `projectdashboard.service` enabled at boot
- environment file at `/etc/projectdashboard.env` (preserves SMTP keys on reinstall)
- dedicated projects directory (`PDASH_PROJECTS_DIR`, default `/opt/projectdashboard/projects`)
- optional Nginx reverse proxy
- optional Let's Encrypt HTTPS
- daily backup timer (`projectdashboard-backup.timer`)
- bootstrap admin account: `admin` / `admin`

After first login as admin, configure operational settings in `/settings.html` (SMTP, defaults, periodic reports).

## Manual execution

```bash
cd /path/to/ProjectDashboard
python3 app.py
```

Access:
- `http://127.0.0.1:8765/login.html`

## Dependencies

- Python 3.10+
- SQLite (bundled in Python)

## Backup

Essential artifacts:

- `data/projectdashboard.db`
- `data/docs_repo/` (if document git storage is enabled)

## Restore

1. restore data files/directories
2. restart service
3. validate login and key endpoints
