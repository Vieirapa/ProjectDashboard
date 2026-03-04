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

## Troubleshooting

- If permission errors persist, confirm:
  - the path is absolute
  - ownership matches the active service user/group
  - parent directories are accessible
- If needed, temporarily test with an app-local writable path:
  - `/opt/projectdashboard/data/backups`

