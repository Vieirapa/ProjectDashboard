# Acceptance Tests — ProjectDashboard

This folder centralizes functional and operational tests to keep an auditable history.

## Structure

- `checklists/`: reusable base checklists (official templates)
- `runs/`: completed executions (history with evidence and outcomes)

## How to use

1. Pick a checklist in `checklists/`.
2. Copy it to `runs/YYYY-MM-DD-<environment>-<purpose>.md`.
3. Fill status (`[x]`, `[ ]`, `N/A`), evidence, and notes.
4. Commit the run file to preserve test history.

## Recommended conventions

- Run filename: `YYYY-MM-DD-ubuntu-ubuntu-server-acceptance.md`
- Always record:
  - tested commit/branch
  - environment (Ubuntu version, VM/cloud/local)
  - final result (`PASS` or `FAIL`)
  - open issues
