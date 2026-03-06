# Acceptance Checklist — Ubuntu + Ubuntu Server

> Project: **ProjectDashboard**

## Run Metadata

- Date:
- Executor:
- Environment(s): Ubuntu Desktop / Ubuntu Server
- Ubuntu version(s): 22.04 / 24.04 (fill in)
- Tested commit:
- Branch:
- Final result: `PASS` / `FAIL`

---

## 1) Prerequisites

- [ ] `apt-get update` completed successfully
- [ ] `git` and `curl` installed
- [ ] Repository cloned successfully
- [ ] Project directory accessible

Base commands:

```bash
sudo apt-get update
sudo apt-get install -y git curl
git clone git@github.com:Vieirapa/ProjectDashboard.git
cd ProjectDashboard
```

---

## 2) Installation Scenario A (no domain/HTTPS)

- [ ] Installer executed: `sudo ENABLE_NGINX=yes ENABLE_HTTPS=no ./install.sh`
- [ ] `projectdashboard` enabled at boot
- [ ] `projectdashboard` active
- [ ] `nginx` enabled at boot
- [ ] `nginx` active
- [ ] `curl -I http://127.0.0.1/login.html` returned 200/302

---

## 3) Installation Scenario B (domain + HTTPS)

- [ ] Installer executed with `DOMAIN` and `LE_EMAIL`
- [ ] `projectdashboard` active
- [ ] `nginx` active
- [ ] Certificate present in `certbot certificates`
- [ ] HTTPS access to `/login.html` is valid

Base command:

```bash
sudo DOMAIN=dashboard.example.com LE_EMAIL=admin@example.com ./install.sh
```

---

## 4) Functional Acceptance

- [ ] Login with `admin/admin`
- [ ] Admin password changed
- [ ] Project created in `projects.html`
- [ ] Kanban card created
- [ ] Card status/priority updated
- [ ] RBAC validated (admin full access + role-based restriction)

---

## 5) Backup and Restore

### 5.1 Backup

- [ ] `projectdashboard-backup.timer` is active
- [ ] `projectdashboard-backup.service` executed manually
- [ ] DB backup generated (`projectdashboard-db-*.sqlite3`)
- [ ] docs_repo backup generated (`projectdashboard-docs-repo-*.tar.gz`)
- [ ] documents backup generated (`projectdashboard-documents-*.tar.gz`)

### 5.2 Restore

- [ ] `restore_backup.sh` executed with DB + docs_repo + documents backups
- [ ] Service returned active after restore
- [ ] Restored data validated

Base command:

```bash
sudo ./scripts/restore_backup.sh \
  --db-backup /var/backups/projectdashboard/projectdashboard-db-AAAA-MM-DD_HHMMSS.sqlite3 \
  --docs-repo-backup /var/backups/projectdashboard/projectdashboard-docs-repo-AAAA-MM-DD_HHMMSS.tar.gz \
  --documents-backup /var/backups/projectdashboard/projectdashboard-documents-AAAA-MM-DD_HHMMSS.tar.gz
```

---

## 6) Reboot Test

- [ ] Machine rebooted
- [ ] `projectdashboard` auto-started after reboot
- [ ] `nginx` auto-started after reboot
- [ ] App accessible after reboot

---

## 7) Ubuntu Desktop Validation

- [ ] Local browser access works (`http://127.0.0.1/login.html`)
- [ ] Basic user flow works

## 8) Ubuntu Server Validation

- [ ] Remote access via IP/DNS works
- [ ] UFW rules are correct (`OpenSSH`, `Nginx Full` or explicit app ports)
- [ ] No manual intervention needed after reboot

---

## Evidence

- Logs/commands:
- Screenshots/URLs:
- Notes:

## Open Issues

- Item:
- Owner:
- Due date:
