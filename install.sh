#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-projectdashboard}"
APP_GROUP="${APP_GROUP:-projectdashboard}"
INSTALL_DIR="${INSTALL_DIR:-/opt/projectdashboard}"
PORT="${PORT:-8765}"
ADMIN_USER="admin"
ADMIN_PASSWORD="admin"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este instalador precisa ser executado como root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/7] Instalando dependências do sistema..."
apt-get update -y
apt-get install -y python3 python3-venv rsync

if ! getent group "${APP_GROUP}" >/dev/null; then
  echo "[2/7] Criando grupo ${APP_GROUP}..."
  groupadd --system "${APP_GROUP}"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "[2/7] Criando usuário ${APP_USER}..."
  useradd --system --create-home --home-dir /var/lib/projectdashboard --gid "${APP_GROUP}" --shell /usr/sbin/nologin "${APP_USER}"
fi

echo "[3/7] Copiando aplicação para ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
rsync -a --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude 'data/server.log' \
  --exclude 'data/projectdashboard.db' \
  "${SCRIPT_DIR}/" "${INSTALL_DIR}/"

chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/data"
chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}/data"

echo "[4/7] Criando ambiente virtual..."
if [[ ! -d "${INSTALL_DIR}/.venv" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
fi

cat > /etc/projectdashboard.env <<EOF
PDASH_PORT=${PORT}
PDASH_INITIAL_PASSWORD=${ADMIN_PASSWORD}
EOF
chmod 640 /etc/projectdashboard.env
chown root:"${APP_GROUP}" /etc/projectdashboard.env

echo "[5/7] Inicializando banco e garantindo admin/admin..."
sudo -u "${APP_USER}" bash -lc "cd '${INSTALL_DIR}' && '${INSTALL_DIR}/.venv/bin/python' - <<'PY'
import app

app.init_db()
with app.db() as conn:
    row = conn.execute(\"SELECT username FROM users WHERE username=?\", (\"admin\",)).fetchone()
    if row:
        conn.execute(
            \"UPDATE users SET password_hash=?, role='admin' WHERE username=?\",
            (app.hash_password(\"admin\"), \"admin\"),
        )
    else:
        conn.execute(
            \"INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)\",
            (\"admin\", app.hash_password(\"admin\"), app.now_iso()),
        )
PY"

echo "[6/7] Configurando serviço systemd..."
cat > /etc/systemd/system/projectdashboard.service <<EOF
[Unit]
Description=ProjectDashboard
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=/etc/projectdashboard.env
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now projectdashboard.service

echo "[7/7] Instalação concluída ✅"
echo "Acesso: http://<IP_DO_SERVIDOR>:${PORT}/login.html"
echo "Usuário inicial: ${ADMIN_USER}"
echo "Senha inicial: ${ADMIN_PASSWORD}"
echo "Troque a senha do admin no primeiro acesso."
