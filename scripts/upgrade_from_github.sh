#!/usr/bin/env bash
set -euo pipefail

# Upgrade ProjectDashboard directly from GitHub.
# - Default: latest develop
# - Optional: specific ref/tag/commit via --ref

REPO_URL="${REPO_URL:-https://github.com/Vieirapa/ProjectDashboard.git}"
SRC_DIR="${SRC_DIR:-/opt/src/ProjectDashboard}"
DEFAULT_REF="${DEFAULT_REF:-develop}"
REF=""

# Installer pass-through flags (optional)
DOMAIN="${DOMAIN:-}"
LE_EMAIL="${LE_EMAIL:-}"
ENABLE_NGINX="${ENABLE_NGINX:-yes}"
ENABLE_HTTPS="${ENABLE_HTTPS:-yes}"
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER:-yes}"
ENABLE_UFW="${ENABLE_UFW:-yes}"
INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST:-yes}"

usage() {
  cat <<EOF
Usage: sudo ./scripts/upgrade_from_github.sh [options]

Options:
  --ref <git-ref>            Upgrade to specific ref/tag/commit (e.g. v0.9.0-beta.2)
  --repo <url>               GitHub repository URL (default: ${REPO_URL})
  --src-dir <path>           Local source directory (default: ${SRC_DIR})
  --default-ref <branch>     Branch used when --ref is not provided (default: ${DEFAULT_REF})

  --domain <fqdn>            Passed to installer DOMAIN
  --le-email <email>         Passed to installer LE_EMAIL
  --enable-nginx <yes|no>    Passed to installer ENABLE_NGINX
  --enable-https <yes|no>    Passed to installer ENABLE_HTTPS
  --enable-backup <yes|no>   Passed to installer ENABLE_BACKUP_TIMER
  --enable-ufw <yes|no>      Passed to installer ENABLE_UFW
  --smoke-test <yes|no>      Passed to installer INSTALL_SMOKE_TEST

Examples:
  sudo ./scripts/upgrade_from_github.sh
  sudo ./scripts/upgrade_from_github.sh --ref v0.9.0-beta.2
  sudo ./scripts/upgrade_from_github.sh --ref develop --domain dashboard.example.com --le-email admin@example.com
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="${2:-}"; shift 2 ;;
    --repo) REPO_URL="${2:-}"; shift 2 ;;
    --src-dir) SRC_DIR="${2:-}"; shift 2 ;;
    --default-ref) DEFAULT_REF="${2:-}"; shift 2 ;;
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --le-email) LE_EMAIL="${2:-}"; shift 2 ;;
    --enable-nginx) ENABLE_NGINX="${2:-}"; shift 2 ;;
    --enable-https) ENABLE_HTTPS="${2:-}"; shift 2 ;;
    --enable-backup) ENABLE_BACKUP_TIMER="${2:-}"; shift 2 ;;
    --enable-ufw) ENABLE_UFW="${2:-}"; shift 2 ;;
    --smoke-test) INSTALL_SMOKE_TEST="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (sudo)."
  exit 1
fi

if [[ -z "${REF}" && -t 0 ]]; then
  read -r -p "Git ref to deploy [${DEFAULT_REF}]: " ans || true
  REF="${ans:-$DEFAULT_REF}"
fi
REF="${REF:-$DEFAULT_REF}"

echo "==> Using source dir: ${SRC_DIR}"
echo "==> Using repo: ${REPO_URL}"
echo "==> Target ref: ${REF}"

mkdir -p "$(dirname "$SRC_DIR")"
if [[ ! -d "${SRC_DIR}/.git" ]]; then
  echo "==> Cloning repository..."
  git clone "${REPO_URL}" "${SRC_DIR}"
fi

cd "${SRC_DIR}"
echo "==> Fetching latest from GitHub..."
git fetch --all --tags --prune

# Resolve and checkout target ref robustly.
if git show-ref --verify --quiet "refs/tags/${REF}"; then
  git checkout -f "tags/${REF}"
elif git show-ref --verify --quiet "refs/heads/${REF}"; then
  git checkout -f "${REF}"
  git pull --ff-only origin "${REF}"
elif git show-ref --verify --quiet "refs/remotes/origin/${REF}"; then
  git checkout -B "${REF}" "origin/${REF}"
else
  # Try direct commit-ish (hash)
  git checkout -f "${REF}"
fi

echo "==> Deployed source commit: $(git rev-parse --short HEAD)"

# Safety backup before reinstall/upgrade
if [[ -x /opt/projectdashboard/scripts/backup.sh ]]; then
  echo "==> Running pre-upgrade backup..."
  /opt/projectdashboard/scripts/backup.sh || echo "WARN: backup script returned non-zero; continuing"
else
  echo "==> Backup script not found at /opt/projectdashboard/scripts/backup.sh (skipping)"
fi

if [[ ! -x ./install.sh ]]; then
  echo "ERROR: install.sh not found in ${SRC_DIR}"
  exit 1
fi

echo "==> Running installer..."
DOMAIN="${DOMAIN}" \
LE_EMAIL="${LE_EMAIL}" \
ENABLE_NGINX="${ENABLE_NGINX}" \
ENABLE_HTTPS="${ENABLE_HTTPS}" \
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER}" \
ENABLE_UFW="${ENABLE_UFW}" \
INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST}" \
./install.sh </dev/null

echo
echo "Upgrade completed ✅"
echo "Ref: ${REF}"
echo "Commit: $(git rev-parse --short HEAD)"
echo "Service check: systemctl status projectdashboard --no-pager"
