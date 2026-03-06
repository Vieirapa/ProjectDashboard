# 12 — Backup and Restore Setup (Ubuntu)

This guide covers backup path permissions and restore procedures for ProjectDashboard on Ubuntu.

## Why this matters

If backup or restore operations fail with `Permission denied`, ownership or parent-directory permissions are usually misconfigured.

## 1) Check service runtime identity

```bash
systemctl show -p User,Group projectdashboard
```

Example output:

```text
User=projectdashboard
Group=projectdashboard
```

Use these values when fixing ownership for `/opt/projectdashboard/data` and `/opt/projectdashboard/documents`.

## 2) Create and protect backup directory

Installer default backup path:
- `/var/backups/projectdashboard`

Recommended baseline:

```bash
sudo mkdir -p /var/backups/projectdashboard
sudo chown root:root /var/backups/projectdashboard
sudo chmod 750 /var/backups/projectdashboard
```

> The installer-generated backup timer runs through a root-owned oneshot service, so root ownership is expected for the backup output path.

## 3) Trigger and verify backup

```bash
sudo systemctl start projectdashboard-backup.service
sudo systemctl status projectdashboard-backup.service --no-pager
sudo ls -lh /var/backups/projectdashboard
```

Expected files:

- `projectdashboard-db-YYYY-MM-DD_HHMMSS.sqlite3`
- `projectdashboard-docs-repo-YYYY-MM-DD_HHMMSS.tar.gz`
- `projectdashboard-documents-YYYY-MM-DD_HHMMSS.tar.gz`

## 4) Manual restore (step-by-step)

### A) Stop service

```bash
sudo systemctl stop projectdashboard
```

### B) Optional safety snapshot

```bash
sudo mkdir -p /opt/projectdashboard/data/restore-snapshots
sudo cp -a /opt/projectdashboard/data/projectdashboard.db /opt/projectdashboard/data/restore-snapshots/projectdashboard.db.pre-restore
sudo tar -czf /opt/projectdashboard/data/restore-snapshots/docs_repo.pre-restore.tar.gz -C /opt/projectdashboard/data docs_repo
sudo tar -czf /opt/projectdashboard/data/restore-snapshots/documents.pre-restore.tar.gz -C /opt/projectdashboard documents
```

### C) Restore DB

```bash
sudo cp -a /var/backups/projectdashboard/projectdashboard-db-YYYY-MM-DD_HHMMSS.sqlite3 /opt/projectdashboard/data/projectdashboard.db
```

### D) Restore docs_repo (optional)

```bash
sudo rm -rf /opt/projectdashboard/data/docs_repo
sudo tar -xzf /var/backups/projectdashboard/projectdashboard-docs-repo-YYYY-MM-DD_HHMMSS.tar.gz -C /opt/projectdashboard/data
```

### E) Restore documents (optional)

```bash
sudo rm -rf /opt/projectdashboard/documents
sudo tar -xzf /var/backups/projectdashboard/projectdashboard-documents-YYYY-MM-DD_HHMMSS.tar.gz -C /opt/projectdashboard
```

### F) Re-apply ownership and start service

```bash
sudo chown -R projectdashboard:projectdashboard /opt/projectdashboard/data /opt/projectdashboard/documents
sudo systemctl start projectdashboard
sudo systemctl status projectdashboard --no-pager
```

## 5) Automated restore script

Script:
- `scripts/restore_backup.sh`

### Full restore

```bash
sudo ./scripts/restore_backup.sh \
  --db-backup /var/backups/projectdashboard/projectdashboard-db-YYYY-MM-DD_HHMMSS.sqlite3 \
  --docs-repo-backup /var/backups/projectdashboard/projectdashboard-docs-repo-YYYY-MM-DD_HHMMSS.tar.gz \
  --documents-backup /var/backups/projectdashboard/projectdashboard-documents-YYYY-MM-DD_HHMMSS.tar.gz
```

### DB-only restore

```bash
sudo ./scripts/restore_backup.sh \
  --db-backup /var/backups/projectdashboard/projectdashboard-db-YYYY-MM-DD_HHMMSS.sqlite3
```

### Useful options

- `--service <name>` (default: `projectdashboard`)
- `--install-dir <path>` (default: `/opt/projectdashboard`)
- `--app-user <user>` (default: `projectdashboard`)
- `--app-group <group>` (default: `projectdashboard`)
- `--no-snapshot` (skip pre-restore safety snapshot)

Help:

```bash
./scripts/restore_backup.sh --help
```

## Troubleshooting

- Confirm backup files exist and match expected naming.
- Confirm parent folders are accessible (`/opt/projectdashboard`, `/var/backups/projectdashboard`).
- Confirm service user/group ownership on runtime folders (`data`, `documents`).
- Review service logs:

```bash
sudo journalctl -u projectdashboard -n 120 --no-pager
```
