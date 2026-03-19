#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-projectdashboard}"
INSTALL_DIR="${INSTALL_DIR:-/opt/projectdashboard}"
DATA_DIR="${DATA_DIR:-${INSTALL_DIR}/data}"
DB_TARGET="${DB_TARGET:-${DATA_DIR}/projectdashboard.db}"
DOCS_REPO_DIR="${DOCS_REPO_DIR:-${DATA_DIR}/docs_repo}"
DOCUMENTS_DIR="${DOCUMENTS_DIR:-${INSTALL_DIR}/documents}"
APP_USER="${APP_USER:-projectdashboard}"
APP_GROUP="${APP_GROUP:-projectdashboard}"
SNAPSHOT_DIR_DEFAULT="${DATA_DIR}/restore-snapshots"

usage() {
  cat <<'EOF'
Usage:
  sudo ./scripts/restore_backup.sh \
    --db-backup /path/projectdashboard-db-YYYYMMDD-HHMMSS.sqlite3 \
    [--docs-repo-backup /path/projectdashboard-docs-repo-YYYYMMDD-HHMMSS.tar.gz] \
    [--documents-backup /path/projectdashboard-documents-YYYYMMDD-HHMMSS.tar.gz] \
    [--service projectdashboard] \
    [--install-dir /opt/projectdashboard] \
    [--app-user projectdashboard] \
    [--app-group projectdashboard] \
    [--no-snapshot]

What it does:
  1) Stops the service
  2) Optionally snapshots current DB/docs_repo/documents before restore
  3) Restores DB file
  4) Optionally restores docs_repo archive
  5) Optionally restores documents archive
  6) Fixes ownership
  7) Starts the service

Notes:
  - --db-backup is required
  - --docs-repo-backup and --documents-backup are optional
  - Legacy alias: --docs-backup (same as --docs-repo-backup)
EOF
}

DB_BACKUP=""
DOCS_REPO_BACKUP=""
DOCUMENTS_BACKUP=""
NO_SNAPSHOT="false"
ALLOW_NON_ROOT="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-backup)
      DB_BACKUP="${2:-}"; shift 2 ;;
    --docs-repo-backup|--docs-backup)
      DOCS_REPO_BACKUP="${2:-}"; shift 2 ;;
    --documents-backup)
      DOCUMENTS_BACKUP="${2:-}"; shift 2 ;;
    --service)
      SERVICE_NAME="${2:-}"; shift 2 ;;
    --install-dir)
      INSTALL_DIR="${2:-}"; shift 2
      DATA_DIR="${INSTALL_DIR}/data"
      DB_TARGET="${DATA_DIR}/projectdashboard.db"
      DOCS_REPO_DIR="${DATA_DIR}/docs_repo"
      DOCUMENTS_DIR="${INSTALL_DIR}/documents"
      SNAPSHOT_DIR_DEFAULT="${DATA_DIR}/restore-snapshots"
      ;;
    --app-user)
      APP_USER="${2:-}"; shift 2 ;;
    --app-group)
      APP_GROUP="${2:-}"; shift 2 ;;
    --no-snapshot)
      NO_SNAPSHOT="true"; shift ;;
    --allow-non-root)
      ALLOW_NON_ROOT="true"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ $EUID -ne 0 && "${ALLOW_NON_ROOT}" != "true" ]]; then
  echo "This script must run as root (sudo). Use --allow-non-root to run without service stop/start/chown." >&2
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

if [[ -n "${DOCS_REPO_BACKUP}" && ! -f "${DOCS_REPO_BACKUP}" ]]; then
  echo "Error: docs_repo backup archive not found: ${DOCS_REPO_BACKUP}" >&2
  exit 1
fi

if [[ -n "${DOCUMENTS_BACKUP}" && ! -f "${DOCUMENTS_BACKUP}" ]]; then
  echo "Error: documents backup archive not found: ${DOCUMENTS_BACKUP}" >&2
  exit 1
fi

mkdir -p "${DATA_DIR}" "${DOCUMENTS_DIR}"

STAMP="$(date +%Y%m%d-%H%M%S)"
SNAPSHOT_DIR="${SNAPSHOT_DIR_DEFAULT}/${STAMP}"

if [[ $EUID -eq 0 ]]; then
  echo "[1/7] Stopping service: ${SERVICE_NAME}"
  systemctl stop "${SERVICE_NAME}"
else
  echo "[1/7] Non-root mode: skipping service stop"
fi

if [[ "${NO_SNAPSHOT}" != "true" ]]; then
  echo "[2/7] Creating safety snapshot: ${SNAPSHOT_DIR}"
  mkdir -p "${SNAPSHOT_DIR}"
  if [[ -f "${DB_TARGET}" ]]; then
    cp -a "${DB_TARGET}" "${SNAPSHOT_DIR}/projectdashboard.db.pre-restore"
  fi
  if [[ -d "${DOCS_REPO_DIR}" ]]; then
    tar -czf "${SNAPSHOT_DIR}/docs_repo.pre-restore.tar.gz" -C "${DATA_DIR}" docs_repo
  fi
  if [[ -d "${DOCUMENTS_DIR}" ]]; then
    docs_parent="$(dirname "${DOCUMENTS_DIR}")"
    docs_name="$(basename "${DOCUMENTS_DIR}")"
    tar -czf "${SNAPSHOT_DIR}/documents.pre-restore.tar.gz" -C "${docs_parent}" "${docs_name}"
  fi
else
  echo "[2/7] Snapshot skipped (--no-snapshot)."
fi

echo "[3/7] Restoring DB from: ${DB_BACKUP}"
cp -a "${DB_BACKUP}" "${DB_TARGET}"

if [[ -n "${DOCS_REPO_BACKUP}" ]]; then
  echo "[4/7] Restoring docs_repo from: ${DOCS_REPO_BACKUP}"
  rm -rf "${DOCS_REPO_DIR}"
  mkdir -p "${DATA_DIR}"
  tar -xzf "${DOCS_REPO_BACKUP}" -C "${DATA_DIR}"
else
  echo "[4/7] docs_repo restore skipped (no --docs-repo-backup provided)."
fi

if [[ -n "${DOCUMENTS_BACKUP}" ]]; then
  echo "[5/7] Restoring documents from: ${DOCUMENTS_BACKUP}"
  rm -rf "${DOCUMENTS_DIR}"
  mkdir -p "$(dirname "${DOCUMENTS_DIR}")"
  tar -xzf "${DOCUMENTS_BACKUP}" -C "$(dirname "${DOCUMENTS_DIR}")"
else
  echo "[5/7] documents restore skipped (no --documents-backup provided)."
fi

if [[ $EUID -eq 0 ]]; then
  echo "[6/7] Fixing ownership (${APP_USER}:${APP_GROUP})"
  chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}" "${DOCUMENTS_DIR}" || true

  echo "[7/7] Starting service: ${SERVICE_NAME}"
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
else
  echo "[6/7] Non-root mode: skipping chown"
  echo "[7/7] Non-root mode: skipping service start"
  echo "Restore completed (non-root mode) ✅"
  if [[ "${NO_SNAPSHOT}" != "true" ]]; then
    echo "Safety snapshot: ${SNAPSHOT_DIR}"
  fi
fi
