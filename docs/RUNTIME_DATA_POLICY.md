# Runtime Data Policy

This project separates **source code** from **runtime/business data**.

## Why this exists
Operational data (client cards, uploaded files, generated documents, logs, local DB files) should not be versioned in Git. Keeping runtime data out of the repository reduces risk of:

- leaking customer/business data
- accidental overwrite during deployments
- repository noise and large diffs from operational changes

## Folders and files that are runtime data

- `documents/` → business content generated/edited at runtime
- `data/` → runtime state (including local database and logs)
- `uploads/` → uploaded files generated in operation
- `*.db`, `*.sqlite`, `*.sqlite3`, `*.log`

These paths are intentionally ignored in `.gitignore`.

## Deployment and backup rule

- Deploys update **code only**.
- Runtime data must be preserved on server paths (e.g. `/opt/projectdashboard/data` and `/opt/projectdashboard/documents`).
- Before upgrades, always create backups/snapshots of runtime data.

## Practical consequence

If you see cards/documents changing in production, this must happen in runtime storage, **not** as Git commits.
