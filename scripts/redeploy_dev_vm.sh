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
echo "[redeploy] storage health snapshot"
sudo python3 - <<'PY'
import sqlite3
from pathlib import Path

DB = Path('/opt/projectdashboard/data/projectdashboard.db')
DOCS = Path('/opt/projectdashboard/data/docs_repo')
if not DB.exists():
    print('WARN: database not found at', DB)
    raise SystemExit(0)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
broken_documents = 0
broken_versions = 0
for r in conn.execute("SELECT slug, document_path FROM documents ORDER BY id"):
    p = str(r['document_path'] or '').strip()
    if p and not Path(p).exists():
        broken_documents += 1
for r in conn.execute("SELECT document_slug, version, file_rel_path FROM document_versions ORDER BY id"):
    rel = str(r['file_rel_path'] or '').strip()
    if rel and not (DOCS / rel).exists():
        broken_versions += 1
print(f"storage-health: broken_documents={broken_documents} broken_versions={broken_versions}")
PY

echo
echo "[redeploy] host access URL"
echo "http://${HOST_ACCESS_IP}:${PORT}/login.html"
