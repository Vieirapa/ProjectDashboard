#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-projectdashboard}"
APP_GROUP="${APP_GROUP:-projectdashboard}"
INSTALL_DIR="${INSTALL_DIR:-/opt/projectdashboard}"
PORT="${PORT:-8765}"
DOMAIN="${DOMAIN:-}"                 # ex.: dashboard.seudominio.com
LE_EMAIL="${LE_EMAIL:-}"             # e-mail para Let's Encrypt
ENABLE_NGINX="${ENABLE_NGINX:-yes}"  # yes|no
ENABLE_HTTPS="${ENABLE_HTTPS:-yes}"  # yes|no
ENABLE_BACKUP_TIMER="${ENABLE_BACKUP_TIMER:-yes}" # yes|no
BACKUP_DIR="${BACKUP_DIR:-/var/backups/projectdashboard}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
ADMIN_USER="admin"
ADMIN_PASSWORD="admin"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este instalador precisa ser executado como root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

prompt_default() {
  local var_name="$1"; shift
  local prompt_text="$1"; shift
  local current_value="$1"; shift
  local input=""
  read -r -p "${prompt_text} [${current_value}]: " input || true
  if [[ -n "${input}" ]]; then
    printf -v "$var_name" '%s' "$input"
  fi
}

if [[ -t 0 ]]; then
  echo "=== Instalador ProjectDashboard v2 ==="
  prompt_default PORT "Porta interna da aplicação" "$PORT"
  prompt_default DOMAIN "Domínio público (vazio para sem proxy/https)" "$DOMAIN"
  if [[ -n "$DOMAIN" ]]; then
    prompt_default LE_EMAIL "E-mail para Let's Encrypt" "$LE_EMAIL"
  fi
fi

if [[ -z "$DOMAIN" ]]; then
  ENABLE_HTTPS="no"
fi

echo "[1/9] Instalando dependências..."
apt-get update -y
apt-get install -y python3 python3-venv rsync curl
if [[ "$ENABLE_NGINX" == "yes" ]]; then
  apt-get install -y nginx
fi
if [[ "$ENABLE_HTTPS" == "yes" ]]; then
  apt-get install -y certbot python3-certbot-nginx
fi

if ! getent group "${APP_GROUP}" >/dev/null; then
  echo "[2/9] Criando grupo ${APP_GROUP}..."
  groupadd --system "${APP_GROUP}"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "[2/9] Criando usuário ${APP_USER}..."
  useradd --system --create-home --home-dir /var/lib/projectdashboard --gid "${APP_GROUP}" --shell /usr/sbin/nologin "${APP_USER}"
fi

echo "[3/9] Copiando aplicação para ${INSTALL_DIR}..."
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

echo "[4/9] Criando ambiente virtual..."
if [[ ! -d "${INSTALL_DIR}/.venv" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
fi

APP_HOST="0.0.0.0"
if [[ "$ENABLE_NGINX" == "yes" ]]; then
  APP_HOST="127.0.0.1"
fi

cat > /etc/projectdashboard.env <<EOF
PDASH_HOST=${APP_HOST}
PDASH_PORT=${PORT}
PDASH_INITIAL_PASSWORD=${ADMIN_PASSWORD}
EOF
chmod 640 /etc/projectdashboard.env
chown root:"${APP_GROUP}" /etc/projectdashboard.env

echo "[5/9] Inicializando banco e garantindo admin/admin..."
sudo -u "${APP_USER}" bash -lc "cd '${INSTALL_DIR}' && '${INSTALL_DIR}/.venv/bin/python' - <<'PY'
import app
app.init_db()
with app.db() as conn:
    row = conn.execute(\"SELECT username FROM users WHERE username=?\", (\"admin\",)).fetchone()
    if row:
        conn.execute(\"UPDATE users SET password_hash=?, role='admin' WHERE username=?\", (app.hash_password(\"admin\"), \"admin\"))
    else:
        conn.execute(\"INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)\", (\"admin\", app.hash_password(\"admin\"), app.now_iso()))
PY"

echo "[6/9] Configurando serviço systemd da aplicação..."
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

if [[ "$ENABLE_NGINX" == "yes" ]]; then
  echo "[7/9] Configurando Nginx reverse proxy..."
  NGINX_CONF="/etc/nginx/sites-available/projectdashboard"
  if [[ -n "$DOMAIN" ]]; then
    SERVER_NAME="$DOMAIN"
  else
    SERVER_NAME="_"
  fi

  cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${SERVER_NAME};

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/projectdashboard
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx

  if [[ "$ENABLE_HTTPS" == "yes" && -n "$DOMAIN" && -n "$LE_EMAIL" ]]; then
    echo "[8/9] Emitindo certificado TLS com Let's Encrypt..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$LE_EMAIL" --redirect || {
      echo "Aviso: falha ao emitir certificado automaticamente."
      echo "Você pode tentar depois: certbot --nginx -d $DOMAIN"
    }
  else
    echo "[8/9] HTTPS automático ignorado (sem domínio/e-mail ou desabilitado)."
  fi
else
  echo "[7/9] Nginx desabilitado."
  echo "[8/9] HTTPS automático desabilitado."
fi

if [[ "$ENABLE_BACKUP_TIMER" == "yes" ]]; then
  echo "[9/9] Configurando backup automático diário..."
  mkdir -p "$BACKUP_DIR"
  chown root:root "$BACKUP_DIR"
  chmod 750 "$BACKUP_DIR"

  mkdir -p "${INSTALL_DIR}/scripts"
  cat > "${INSTALL_DIR}/scripts/backup.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
STAMP=\$(date +%F_%H%M%S)
OUT_DIR="${BACKUP_DIR}"
SRC_DIR="${INSTALL_DIR}/data"
mkdir -p "\$OUT_DIR"
if [[ -f "\$SRC_DIR/projectdashboard.db" ]]; then
  cp "\$SRC_DIR/projectdashboard.db" "\$OUT_DIR/projectdashboard-db-\$STAMP.sqlite3"
fi
if [[ -d "\$SRC_DIR/docs_repo" ]]; then
  tar -czf "\$OUT_DIR/projectdashboard-docs-\$STAMP.tar.gz" -C "\$SRC_DIR" docs_repo
fi
find "\$OUT_DIR" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete
EOF
  chmod +x "${INSTALL_DIR}/scripts/backup.sh"

  cat > /etc/systemd/system/projectdashboard-backup.service <<EOF
[Unit]
Description=Backup do ProjectDashboard

[Service]
Type=oneshot
ExecStart=${INSTALL_DIR}/scripts/backup.sh
EOF

  cat > /etc/systemd/system/projectdashboard-backup.timer <<EOF
[Unit]
Description=Timer diário de backup do ProjectDashboard

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable --now projectdashboard-backup.timer
else
  echo "[9/9] Backup automático desabilitado."
fi

echo
echo "Instalação concluída ✅"
if [[ "$ENABLE_NGINX" == "yes" && -n "$DOMAIN" ]]; then
  echo "Acesso: http://${DOMAIN}/login.html"
  if [[ "$ENABLE_HTTPS" == "yes" ]]; then
    echo "(Se o certbot concluiu, o acesso HTTPS já foi ativado com redirecionamento.)"
  fi
elif [[ "$ENABLE_NGINX" == "yes" ]]; then
  echo "Acesso: http://<IP_DO_SERVIDOR>/login.html"
else
  echo "Acesso: http://<IP_DO_SERVIDOR>:${PORT}/login.html"
fi
echo "Usuário inicial: ${ADMIN_USER}"
echo "Senha inicial: ${ADMIN_PASSWORD}"
echo "Troque a senha do admin no primeiro acesso."
