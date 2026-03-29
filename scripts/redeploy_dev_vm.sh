#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENABLE_NGINX="${ENABLE_NGINX:-no}"
ENABLE_HTTPS="${ENABLE_HTTPS:-no}"
ENABLE_UFW="${ENABLE_UFW:-no}"
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER:-no}"
INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST:-yes}"

cd "${ROOT_DIR}"

echo "[redeploy] ProjectDashboard dev VM redeploy"
echo "[redeploy] root: ${ROOT_DIR}"
echo "[redeploy] flags: NGINX=${ENABLE_NGINX} HTTPS=${ENABLE_HTTPS} UFW=${ENABLE_UFW} BACKUP_TIMER=${ENABLE_BACKUP_TIMER} SMOKE_TEST=${INSTALL_SMOKE_TEST}"

sudo \
  ENABLE_NGINX="${ENABLE_NGINX}" \
  ENABLE_HTTPS="${ENABLE_HTTPS}" \
  ENABLE_UFW="${ENABLE_UFW}" \
  ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER}" \
  INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST}" \
  ./install.sh

echo
echo "[redeploy] service status"
sudo systemctl status projectdashboard --no-pager || true

echo
echo "[redeploy] local HTTP check"
curl -i http://127.0.0.1:8765/login.html || true
