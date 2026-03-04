# 13 — Future Wishlist

This file tracks future ideas and improvements for ProjectDashboard.

> Purpose: keep a lightweight backlog of enhancements that are not immediate priorities, so we can resume them later.

## Current wishlist

### UX / Kanban

- Add search/filter in **Deleted Projects** admin section
  - filter by name/slug
  - filter by deleted date range
  - filter by deleted-by user
- Add pagination for Deleted Projects list (for large environments)
- Add optional "health badge" UI (green/yellow/red) in System Diagnostics
- Short label mode for ordering dropdown (compact text)
- Run a final UI language QA pass with a checklist (PT-BR consistency, accents, terminology, and microcopy clarity)

### Operations / Installer

- Add `--dry-run` mode to `install.sh` (simulate changes without applying)
- Add post-install command to print detected runtime service user/group and backup path

### Backup / Restore

- Add "Test backup path permissions" button in Settings
- Add helper script to list available backups with interactive selection
- Add one-click restore assistant in admin UI (guided validation + warning step)

### Diagnostics / Observability

- Expand diagnostics with disk usage checks
- Add service-level checks (systemd status summary from backend-safe probes)
- Add optional reminder banner when a newer GitHub version is available

## How to add new ideas

When a new idea appears:

1. Add a short title under the most relevant section.
2. Add one sentence describing expected value.
3. (Optional) Add acceptance criteria bullets.

Keep entries concise and actionable.
