# 01 — Overview

ProjectDashboard is a Kanban-oriented web app for project tracking with controlled document revisions.

## Core capabilities

- User authentication
- Role-based permissions (RBAC)
- Landing page with KPI summary by accessible projects
- Kanban board for project documents (`/kanban.html`)
- Dedicated document details/edit page
- Document attachment and revision history
- Review notes
- User administration (admin-only)
- Audit trail for sensitive actions

## Access model (summary)

- `admin`
  - full access, including user administration/invites/settings and protected deletions
- `lider_projeto`
  - admin-equivalent for operations and project governance
  - no access to user/invite/settings tools
- `member`
  - create/edit documents, no admin panel access
- `desenhista` / `colaborador`
  - edit/upload + review-resolution flow
- `revisor`
  - add review notes

## User deletion safeguards

- Admin-only action
- Cannot delete yourself
- Cannot delete other admins (by policy)
- UI uses explicit confirmation flow
- Backend enforces all critical checks (UI is not the source of truth)
