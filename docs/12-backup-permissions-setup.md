# 12 — Backup Permissions Setup (Ubuntu)

This guide explains how to configure backup folder permissions for ProjectDashboard on Ubuntu.

## Why this matters

If backup execution returns `Permission denied` (for example on `/var/backups/projectdashboard`), the service user probably cannot write to that path.

## 1) Discover the service user and group

Use systemd to check which Linux user/group is running ProjectDashboard:

```bash
systemctl show -p User,Group projectdashboard
```

Example output:

```text
User=projectdashboard
Group=projectdashboard
```

Use these exact values in the `chown` command.

## 2) Create and configure the backup directory

Create the backup directory (if it does not exist), assign ownership to the service account, and lock down permissions:

```bash
sudo mkdir -p /var/backups/projectdashboard
sudo chown -R projectdashboard:projectdashboard /var/backups/projectdashboard
sudo chmod 750 /var/backups/projectdashboard
```

> If your service user/group differs from `projectdashboard:projectdashboard`, replace it with the values returned by `systemctl show -p User,Group projectdashboard`.

## 3) Configure the same path in ProjectDashboard

In **Settings → System Backup**:

- Set backup output path to:
  - `/var/backups/projectdashboard`
- Save policy
- Click **Run backup now** to validate

## 4) Optional verification commands

Check directory ownership and permissions:

```bash
ls -ld /var/backups/projectdashboard
```

Expected pattern (example):

```text
drwxr-x--- 2 projectdashboard projectdashboard ... /var/backups/projectdashboard
```

Check service runtime identity again:

```bash
systemctl show -p User,Group projectdashboard
```

## 5) Restore a specific backup (manual step-by-step)

Use this procedure when you need to recover a specific backup set.

### A. Identify backup files

Typical files are:

- Database backup: `projectdashboard-db-YYYYMMDD-HHMMSS.sqlite3`
- Documents backup: `projectdashboard-docs-YYYYMMDD-HHMMSS.tar.gz`

Example listing:

```bash
ls -lh /var/backups/projectdashboard
```

### B. Stop the service

```bash
sudo systemctl stop projectdashboard
```

### C. (Recommended) Snapshot current data before restore

```bash
sudo mkdir -p /opt/projectdashboard/data/restore-snapshots
sudo cp -a /opt/projectdashboard/data/projectdashboard.db /opt/projectdashboard/data/restore-snapshots/projectdashboard.db.pre-restore
sudo tar -czf /opt/projectdashboard/data/restore-snapshots/docs_repo.pre-restore.tar.gz -C /opt/projectdashboard/data docs_repo
```

### D. Restore database file

```bash
sudo cp -a /var/backups/projectdashboard/projectdashboard-db-YYYYMMDD-HHMMSS.sqlite3 /opt/projectdashboard/data/projectdashboard.db
```

### E. Restore docs repository (optional, if you have the archive)

```bash
sudo rm -rf /opt/projectdashboard/data/docs_repo
sudo tar -xzf /var/backups/projectdashboard/projectdashboard-docs-YYYYMMDD-HHMMSS.tar.gz -C /opt/projectdashboard/data
```

### F. Re-apply ownership and start service

```bash
sudo chown -R projectdashboard:projectdashboard /opt/projectdashboard/data
sudo systemctl start projectdashboard
sudo systemctl status projectdashboard --no-pager
```

## 6) Automatic restore script

A helper script is available:

- `scripts/restore_backup.sh`

### Basic usage

```bash
sudo ./scripts/restore_backup.sh \
  --db-backup /var/backups/projectdashboard/projectdashboard-db-YYYYMMDD-HHMMSS.sqlite3 \
  --docs-backup /var/backups/projectdashboard/projectdashboard-docs-YYYYMMDD-HHMMSS.tar.gz
```

### Restore only database

```bash
sudo ./scripts/restore_backup.sh \
  --db-backup /var/backups/projectdashboard/projectdashboard-db-YYYYMMDD-HHMMSS.sqlite3
```

### Useful options

- `--service <name>` (default: `projectdashboard`)
- `--install-dir <path>` (default: `/opt/projectdashboard`)
- `--app-user <user>` (default: `projectdashboard`)
- `--app-group <group>` (default: `projectdashboard`)
- `--no-snapshot` (skip pre-restore safety snapshot)

Get full help:

```bash
./scripts/restore_backup.sh --help
```

## Troubleshooting

- If permission errors persist, confirm:
  - the path is absolute
  - ownership matches the active service user/group
  - parent directories are accessible
- If needed, temporarily test with an app-local writable path:
  - `/opt/projectdashboard/data/backups`

