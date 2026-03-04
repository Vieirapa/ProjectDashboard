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
- runtime folders fixed under install path (`/opt/projectdashboard/data`, `/opt/projectdashboard/data/docs_repo`, `/opt/projectdashboard/projects`)
- `projectdashboard.service` enabled at boot
- environment file at `/etc/projectdashboard.env` (preserves SMTP keys on reinstall)
- dedicated projects directory (`PDASH_PROJECTS_DIR`, default `/opt/projectdashboard/projects`)
- optional Nginx reverse proxy
- optional Let's Encrypt HTTPS
- daily backup timer (`projectdashboard-backup.timer`)
- optional Ubuntu UFW setup (`ENABLE_UFW=yes`, default)
- bootstrap admin account: `admin` / `admin`

After first login as admin, configure operational settings in `/settings.html` (SMTP, defaults, periodic reports, backup policy, diagnostics).

## Next installer enhancement (scheduled)

- Add `--dry-run` mode to `install.sh` (planned for next installer update) to simulate changes without applying them.

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
