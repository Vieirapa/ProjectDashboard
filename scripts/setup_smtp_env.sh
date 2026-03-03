#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/projectdashboard.env}"
SERVICE_NAME="${SERVICE_NAME:-projectdashboard}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE"
  exit 1
fi

read -r -p "SMTP host (e.g. smtp.gmail.com): " SMTP_HOST
read -r -p "SMTP port [587]: " SMTP_PORT
SMTP_PORT="${SMTP_PORT:-587}"
read -r -p "SMTP username: " SMTP_USER
read -r -s -p "SMTP password/app-password: " SMTP_PASS
echo
read -r -p "From email (e.g. noreply@yourdomain.com): " SMTP_FROM
read -r -p "Use TLS? (true/false) [true]: " SMTP_TLS
SMTP_TLS="${SMTP_TLS:-true}"

backup_file="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$ENV_FILE" "$backup_file"
echo "Backup created: $backup_file"

set_or_replace() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

set_or_replace "PDASH_SMTP_HOST" "$SMTP_HOST"
set_or_replace "PDASH_SMTP_PORT" "$SMTP_PORT"
set_or_replace "PDASH_SMTP_USER" "$SMTP_USER"
set_or_replace "PDASH_SMTP_PASS" "$SMTP_PASS"
set_or_replace "PDASH_SMTP_FROM" "$SMTP_FROM"
set_or_replace "PDASH_SMTP_TLS" "$SMTP_TLS"

chmod 640 "$ENV_FILE"

echo "SMTP settings written to $ENV_FILE"

read -r -p "Restart ${SERVICE_NAME} now? (y/N): " RESTART
if [[ "${RESTART,,}" == "y" ]]; then
  systemctl restart "$SERVICE_NAME"
  systemctl status "$SERVICE_NAME" --no-pager || true
fi

echo "Done."
