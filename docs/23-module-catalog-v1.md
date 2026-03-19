# Module Catalog v1

## Purpose

Define the initial canonical list of UI modules that will be controlled by role-based access in the next implementation phases.

This catalog is the source of truth for:
- module identifiers (`module_id`)
- page mapping
- user-facing labels
- initial status

---

## Naming Rules

- `module_id` must be stable and lowercase with dot notation.
- Prefix by page/domain (`projects`, `admin_users`, `settings`).
- Labels are user-facing and can be localized.
- IDs should not change after release (unless a migration is applied).

---

## Modules

| module_id | Page | Label (EN) | Status |
|---|---|---|---|
| `projects.create_edit` | `projects.html` | Create/Edit Project | Active |
| `projects.list` | `projects.html` | Registered Projects | Active |
| `projects.cards_list` | `projects.html` | Cards List | Active |
| `admin_users.create` | `admin-users.html` | Create User | Active |
| `admin_users.invite` | `admin-users.html` | Invite New User | Active |
| `admin_users.list` | `admin-users.html` | Registered Users | Active |
| `admin_users.audit_log` | `admin-users.html` | Audit Log | Active |
| `settings.smtp` | `settings.html` | Email Sending (SMTP) | Active |
| `settings.system_behavior` | `settings.html` | System Behavior | Active |
| `settings.backup` | `settings.html` | System Backup | Active |
| `settings.backup_restore` | `settings.html` | System Backup Recovery | Active |
| `settings.system_diagnostics` | `settings.html` | System Diagnostics | Active |
| `settings.recoverable_documents` | `settings.html` | Recoverable Documents | Active |
| `settings.periodic_reports` | `settings.html` | Periodic Reports | Active |
| `settings.roles_control` | `settings.html` | Roles Control | Planned (Phase 3) |

---

## Notes

- `ADMIN` will have full access to all modules and will be immutable in matrix editing.
- This v1 catalog maps existing UI sections first; backend enforcement is planned in later phases.
- Future new modules must be appended here before implementation.
