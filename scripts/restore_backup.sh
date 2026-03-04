#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-projectdashboard}"
INSTALL_DIR="${INSTALL_DIR:-/opt/projectdashboard}"
DATA_DIR="${DATA_DIR:-${INSTALL_DIR}/data}"
DB_TARGET="${DB_TARGET:-${DATA_DIR}/projectdashboard.db}"
DOCS_TARGET_DIR="${DOCS_TARGET_DIR:-${DATA_DIR}}"
APP_USER="${APP_USER:-projectdashboard}"
APP_GROUP="${APP_GROUP:-projectdashboard}"
SNAPSHOT_DIR_DEFAULT="${DATA_DIR}/restore-snapshots"

usage() {
  cat <<'EOF'
Usage:
  sudo ./scripts/restore_backup.sh \
    --db-backup /path/projectdashboard-db-YYYYMMDD-HHMMSS.sqlite3 \
    [--docs-backup /path/projectdashboard-docs-YYYYMMDD-HHMMSS.tar.gz] \
    [--service projectdashboard] \
    [--install-dir /opt/projectdashboard] \
    [--app-user projectdashboard] \
    [--app-group projectdashboard] \
    [--no-snapshot]

What it does:
  1) Stops the service
  2) Optionally snapshots current DB/docs_repo before restore
  3) Restores DB file
  4) Optionally restores docs_repo archive
  5) Fixes ownership
  6) Starts the service

Notes:
  - --db-backup is required
  - --docs-backup is optional
EOF
}

DB_BACKUP=""
DOCS_BACKUP=""
NO_SNAPSHOT="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-backup)
      DB_BACKUP="${2:-}"; shift 2 ;;
    --docs-backup)
      DOCS_BACKUP="${2:-}"; shift 2 ;;
    --service)
      SERVICE_NAME="${2:-}"; shift 2 ;;
    --install-dir)
      INSTALL_DIR="${2:-}"; shift 2
      DATA_DIR="${INSTALL_DIR}/data"
      DB_TARGET="${DATA_DIR}/projectdashboard.db"
      DOCS_TARGET_DIR="${DATA_DIR}"
      SNAPSHOT_DIR_DEFAULT="${DATA_DIR}/restore-snapshots"
      ;;
    --app-user)
      APP_USER="${2:-}"; shift 2 ;;
    --app-group)
      APP_GROUP="${2:-}"; shift 2 ;;
    --no-snapshot)
      NO_SNAPSHOT="true"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must run as root (sudo)." >&2
  exit 1
fi

if [[ -z "${DB_BACKUP}" ]]; then
  echo "Error: --db-backup is required." >&2
  usage
  exit 1
fi

if [[ ! -f "${DB_BACKUP}" ]]; then
  echo "Error: DB backup file not found: ${DB_BACKUP}" >&2
  exit 1
fi

if [[ -n "${DOCS_BACKUP}" && ! -f "${DOCS_BACKUP}" ]]; then
  echo "Error: docs backup archive not found: ${DOCS_BACKUP}" >&2
  exit 1
fi

mkdir -p "${DATA_DIR}"

STAMP="$(date +%Y%m%d-%H%M%S)"
SNAPSHOT_DIR="${SNAPSHOT_DIR_DEFAULT}/${STAMP}"

echo "[1/6] Stopping service: ${SERVICE_NAME}"
systemctl stop "${SERVICE_NAME}"

if [[ "${NO_SNAPSHOT}" != "true" ]]; then
  echo "[2/6] Creating safety snapshot: ${SNAPSHOT_DIR}"
  mkdir -p "${SNAPSHOT_DIR}"
  if [[ -f "${DB_TARGET}" ]]; then
    cp -a "${DB_TARGET}" "${SNAPSHOT_DIR}/projectdashboard.db.pre-restore"
  fi
  if [[ -d "${DATA_DIR}/docs_repo" ]]; then
    tar -czf "${SNAPSHOT_DIR}/docs_repo.pre-restore.tar.gz" -C "${DATA_DIR}" docs_repo
  fi
else
  echo "[2/6] Snapshot skipped (--no-snapshot)."
fi

echo "[3/6] Restoring DB from: ${DB_BACKUP}"
cp -a "${DB_BACKUP}" "${DB_TARGET}"

if [[ -n "${DOCS_BACKUP}" ]]; then
  echo "[4/6] Restoring docs_repo from: ${DOCS_BACKUP}"
  rm -rf "${DATA_DIR}/docs_repo"
  mkdir -p "${DOCS_TARGET_DIR}"
  tar -xzf "${DOCS_BACKUP}" -C "${DOCS_TARGET_DIR}"
else
  echo "[4/6] docs_repo restore skipped (no --docs-backup provided)."
fi

echo "[5/6] Fixing ownership (${APP_USER}:${APP_GROUP})"
chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}"

echo "[6/6] Starting service: ${SERVICE_NAME}"
systemctl start "${SERVICE_NAME}"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
  echo "Restore completed ✅"
  echo "Service is active: ${SERVICE_NAME}"
  if [[ "${NO_SNAPSHOT}" != "true" ]]; then
    echo "Safety snapshot: ${SNAPSHOT_DIR}"
  fi
else
  echo "Restore finished but service is not active ❌" >&2
  echo "Run: sudo systemctl status ${SERVICE_NAME} --no-pager" >&2
  exit 1
fi
