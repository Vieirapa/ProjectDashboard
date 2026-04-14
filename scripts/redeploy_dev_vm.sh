#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENABLE_NGINX="${ENABLE_NGINX:-no}"
ENABLE_HTTPS="${ENABLE_HTTPS:-no}"
ENABLE_UFW="${ENABLE_UFW:-no}"
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER:-no}"
INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST:-yes}"
PORT="${PORT:-8765}"
HOST_ACCESS_IP="${HOST_ACCESS_IP:-127.0.0.11}"

cd "${ROOT_DIR}"

echo "[redeploy] ProjectDashboard dev VM redeploy"
echo "[redeploy] root: ${ROOT_DIR}"
echo "[redeploy] flags: NGINX=${ENABLE_NGINX} HTTPS=${ENABLE_HTTPS} UFW=${ENABLE_UFW} BACKUP_TIMER=${ENABLE_BACKUP_TIMER} SMOKE_TEST=${INSTALL_SMOKE_TEST} PORT=${PORT}"

echo
echo "[redeploy] running local test suite..."
python3 -m unittest \
  scripts.test_install_contracts \
  scripts.test_recovery_and_reports \
  scripts.test_roles_delete_regression \
  scripts.test_inactive_role_lockdown

echo
echo "[redeploy] running installer..."
if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
  sudo \
    ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
    ENABLE_NGINX="${ENABLE_NGINX}" \
    ENABLE_HTTPS="${ENABLE_HTTPS}" \
    ENABLE_UFW="${ENABLE_UFW}" \
    ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER}" \
    INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST}" \
    PORT="${PORT}" \
    ./install.sh
else
  sudo \
    ENABLE_NGINX="${ENABLE_NGINX}" \
    ENABLE_HTTPS="${ENABLE_HTTPS}" \
    ENABLE_UFW="${ENABLE_UFW}" \
    ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER}" \
    INSTALL_SMOKE_TEST="${INSTALL_SMOKE_TEST}" \
    PORT="${PORT}" \
    ./install.sh
fi

echo
echo "[redeploy] service status"
sudo systemctl status projectdashboard --no-pager || true

echo
echo "[redeploy] listening port check"
ss -ltnp | grep ":${PORT}" || true

echo
echo "[redeploy] local HTTP GET check"
curl -fsS "http://127.0.0.1:${PORT}/login.html" >/dev/null && echo "OK: local login page reachable"

echo
echo "[redeploy] host access URL"
echo "http://${HOST_ACCESS_IP}:${PORT}/login.html"
