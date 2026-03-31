#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Vieirapa/ProjectDashboard.git}"
SRC_DIR="${SRC_DIR:-/opt/src/ProjectDashboard}"
REF="${REF:-develop}"
INSTALL_DIR="${INSTALL_DIR:-/opt/projectdashboard}"
BACKUP_SCRIPT="${BACKUP_SCRIPT:-${INSTALL_DIR}/scripts/backup.sh}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/projectdashboard}"
ENV_FILE="${ENV_FILE:-/etc/projectdashboard.env}"
SERVICE_NAME="${SERVICE_NAME:-projectdashboard}"
ENABLE_NGINX="${ENABLE_NGINX:-yes}"
ENABLE_HTTPS="${ENABLE_HTTPS:-yes}"
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER:-yes}"
ENABLE_UFW="${ENABLE_UFW:-yes}"
INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST:-yes}"
DOMAIN="${DOMAIN:-}"
LE_EMAIL="${LE_EMAIL:-}"
SMOKE_BASE_URL="${SMOKE_BASE_URL:-http://127.0.0.1:8765}"
RUN_SMOKE="${RUN_SMOKE:-yes}"

usage() {
  cat <<EOF
Usage: sudo ./scripts/safe_update.sh [options]

Safe update flow:
  1) Captures current deployed commit (if available)
  2) Runs pre-update backup
  3) Upgrades/reinstalls target ref
  4) Restarts service
  5) Optionally runs smoke test
  6) Prints backup location for rollback reference

Options:
  --ref <git-ref>            Ref/tag/commit to deploy (default: ${REF})
  --repo <url>               Repository URL (default: ${REPO_URL})
  --src-dir <path>           Source checkout directory (default: ${SRC_DIR})
  --install-dir <path>       Installed app directory (default: ${INSTALL_DIR})
  --backup-dir <path>        Backup output directory (default: ${BACKUP_DIR})
  --smoke-base-url <url>     Base URL used by smoke script (default: ${SMOKE_BASE_URL})
  --run-smoke <yes|no>       Run post-update smoke test (default: ${RUN_SMOKE})
  --domain <fqdn>            Passed to installer DOMAIN
  --le-email <email>         Passed to installer LE_EMAIL
  --enable-nginx <yes|no>    Passed to installer ENABLE_NGINX
  --enable-https <yes|no>    Passed to installer ENABLE_HTTPS
  --enable-backup <yes|no>   Passed to installer ENABLE_BACKUP_TIMER
  --enable-ufw <yes|no>      Passed to installer ENABLE_UFW
  --smoke-test <yes|no>      Passed to installer INSTALL_SMOKE_TEST
  -h, --help                 Show this help

Examples:
  sudo ./scripts/safe_update.sh --ref develop
  sudo ./scripts/safe_update.sh --ref v0.9.0-beta.2 --run-smoke yes
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="${2:-}"; shift 2 ;;
    --repo) REPO_URL="${2:-}"; shift 2 ;;
    --src-dir) SRC_DIR="${2:-}"; shift 2 ;;
    --install-dir)
      INSTALL_DIR="${2:-}"; shift 2
      BACKUP_SCRIPT="${INSTALL_DIR}/scripts/backup.sh"
      ;;
    --backup-dir) BACKUP_DIR="${2:-}"; shift 2 ;;
    --smoke-base-url) SMOKE_BASE_URL="${2:-}"; shift 2 ;;
    --run-smoke) RUN_SMOKE="${2:-}"; shift 2 ;;
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --le-email) LE_EMAIL="${2:-}"; shift 2 ;;
    --enable-nginx) ENABLE_NGINX="${2:-}"; shift 2 ;;
    --enable-https) ENABLE_HTTPS="${2:-}"; shift 2 ;;
    --enable-backup) ENABLE_BACKUP_TIMER="${2:-}"; shift 2 ;;
    --enable-ufw) ENABLE_UFW="${2:-}"; shift 2 ;;
    --smoke-test) INSTALL_SMOKE_TEST="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (sudo)." >&2
  exit 1
fi

CURRENT_DEPLOYED_COMMIT="unknown"
CURRENT_DEPLOYED_BRANCH="unknown"
if [[ -f "${ENV_FILE}" ]]; then
  CURRENT_DEPLOYED_COMMIT="$(grep -E '^PDASH_BUILD_COMMIT=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || echo unknown)"
  CURRENT_DEPLOYED_BRANCH="$(grep -E '^PDASH_BUILD_BRANCH=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || echo unknown)"
fi

PREUPDATE_LATEST_BEFORE=""
if [[ -d "${BACKUP_DIR}" ]]; then
  PREUPDATE_LATEST_BEFORE="$(find "${BACKUP_DIR}" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort | tail -n 1 || true)"
fi

echo "==> Safe update starting"
echo "==> Current deployed commit: ${CURRENT_DEPLOYED_COMMIT}"
echo "==> Current deployed branch: ${CURRENT_DEPLOYED_BRANCH}"
echo "==> Target ref: ${REF}"
echo "==> Backup dir: ${BACKUP_DIR}"

if [[ -x "${BACKUP_SCRIPT}" ]]; then
  echo "==> Running pre-update backup..."
  "${BACKUP_SCRIPT}"
else
  echo "ERROR: Backup script not found or not executable: ${BACKUP_SCRIPT}" >&2
  exit 1
fi

LATEST_AFTER_BACKUP=""
if [[ -d "${BACKUP_DIR}" ]]; then
  LATEST_AFTER_BACKUP="$(find "${BACKUP_DIR}" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort | tail -n 1 || true)"
fi

echo "==> Running upgrade helper..."
mkdir -p "$(dirname "${SRC_DIR}")"
if [[ ! -d "${SRC_DIR}/.git" ]]; then
  git clone "${REPO_URL}" "${SRC_DIR}"
fi

cd "${SRC_DIR}"
REPO_ROOT="$(pwd)"

git fetch --all --tags --prune
if git show-ref --verify --quiet "refs/tags/${REF}"; then
  git checkout -f "tags/${REF}"
elif git show-ref --verify --quiet "refs/heads/${REF}"; then
  git checkout -f "${REF}"
  git pull --ff-only origin "${REF}"
elif git show-ref --verify --quiet "refs/remotes/origin/${REF}"; then
  git checkout -B "${REF}" "origin/${REF}"
else
  git checkout -f "${REF}"
fi

TARGET_COMMIT="$(git rev-parse --short HEAD)"
TARGET_BRANCH="$(git branch --show-current 2>/dev/null || echo unknown)"

echo "==> Installing target commit: ${TARGET_COMMIT} (${TARGET_BRANCH})"
DOMAIN="${DOMAIN}" \
LE_EMAIL="${LE_EMAIL}" \
ENABLE_NGINX="${ENABLE_NGINX}" \
ENABLE_HTTPS="${ENABLE_HTTPS}" \
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER}" \
ENABLE_UFW="${ENABLE_UFW}" \
INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST}" \
./install.sh </dev/null

echo "==> Restarting service..."
systemctl restart "${SERVICE_NAME}"
sleep 2
systemctl is-active --quiet "${SERVICE_NAME}"

echo "==> Service active: ${SERVICE_NAME}"

if [[ "${RUN_SMOKE}" == "yes" ]]; then
  if [[ -x "${REPO_ROOT}/scripts/smoke_r1_r3.sh" ]]; then
    echo "==> Running post-update smoke test..."
    BASE_URL="${SMOKE_BASE_URL}" bash "${REPO_ROOT}/scripts/smoke_r1_r3.sh"
  else
    echo "WARN: smoke script not found at ${REPO_ROOT}/scripts/smoke_r1_r3.sh"
  fi
else
  echo "==> Post-update smoke skipped (--run-smoke no)"
fi

echo
echo "Safe update completed ✅"
echo "Previous deployed commit: ${CURRENT_DEPLOYED_COMMIT}"
echo "New deployed commit: ${TARGET_COMMIT}"
echo "Branch/ref: ${TARGET_BRANCH}"
if [[ -n "${LATEST_AFTER_BACKUP}" && "${LATEST_AFTER_BACKUP}" != "${PREUPDATE_LATEST_BEFORE}" ]]; then
  echo "Latest backup artifact: ${BACKUP_DIR}/${LATEST_AFTER_BACKUP}"
else
  echo "Latest backup dir: ${BACKUP_DIR}"
fi
echo "Rollback reference: use scripts/restore_backup.sh with the generated DB/docs/documents artifacts if needed."
