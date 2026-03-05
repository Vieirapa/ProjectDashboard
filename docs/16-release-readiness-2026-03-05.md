# 16 - Release Readiness (2026-03-05)

Status snapshot for **ProjectDashboard** before first install-and-use presentation.

## ✅ Completed

- Global project scope enforced across Kanban and edit flows (`project_id` context).
- Scope mismatch protection added in backend and frontend (blocked edits on wrong project context).
- New top summary panel in Kanban with:
  - selected project
  - project start date
  - collaborator count (distinct owners)
  - status counters with percentages (Backlog / Em andamento / Em revisão / Concluído)
- UI polish for presentation:
  - title row + right-aligned action buttons in Kanban area
  - branding updates in sidebar and login screen
- Base reset procedure validated for demo start (`admin/admin` only).

## ⚠️ Open known issue

- `BUG-2026-03-05-001` (post-login first render may show empty Kanban despite selected project)
- Tracked in: `docs/15-known-bugs.md`

## Installer and docs checks

- `install.sh` reviewed (service setup and timers unchanged and valid for current package structure).
- `README.md` + `docs/` index aligned.
- Settings default repo URL corrected to `https://github.com/Vieirapa/ProjectDashboard.git`.

## Suggested next gate (after presentation)

1. Fix `BUG-2026-03-05-001` with deterministic first-render flow + instrumentation.
2. Cut a version tag (e.g., `v0.1.0-demo`).
3. Publish a short “Quick Install + First Login” video/GIF in docs.
