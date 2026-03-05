# 01 — Overview

ProjectDashboard is a Kanban-oriented web app for project tracking with controlled document revisions.

## Core capabilities

- User authentication
- Role-based permissions (RBAC)
- Kanban board for project documents
- Dedicated document details/edit page
- Document attachment and revision history
- Review notes
- User administration (admin-only)
- Audit trail for sensitive actions

## Access model (summary)

- `admin`
  - full access, including user administration and protected deletions
- `member`
  - create/edit documents, no admin panel access

## User deletion safeguards

- Admin-only action
- Cannot delete yourself
- Cannot delete other admins (by policy)
- UI uses explicit confirmation flow
- Backend enforces all critical checks (UI is not the source of truth)
