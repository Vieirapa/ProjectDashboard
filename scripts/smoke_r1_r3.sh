#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" /tmp/pdash-login.out' EXIT

pass() { echo "✅ $1"; }
fail() { echo "❌ $1"; exit 1; }

check_get() {
  local path="$1"
  local label="$2"
  curl -fsS -o /dev/null "$BASE_URL$path" && pass "$label" || fail "$label"
}

check_auth_page() {
  local path="$1"
  local label="$2"
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE_JAR" "$BASE_URL$path")"
  [[ "$code" == "200" ]] && pass "$label" || fail "$label (HTTP $code)"
}

USERNAME="${PDASH_SMOKE_USER:-admin}"
PASSWORD="${PDASH_SMOKE_PASS:-admin}"

check_get "/login.html" "GET /login.html"

LOGIN_CODE="$(curl -sS -o /tmp/pdash-login.out -w '%{http_code}' -c "$COOKIE_JAR" -H 'Content-Type: application/json' -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" "$BASE_URL/api/login")"
[[ "$LOGIN_CODE" == "200" ]] || fail "POST /api/login (HTTP $LOGIN_CODE)"
pass "POST /api/login"

check_auth_page "/" "GET /"
check_auth_page "/projects.html" "GET /projects.html"
check_auth_page "/kanban.html" "GET /kanban.html"
check_auth_page "/settings.html" "GET /settings.html"
check_auth_page "/admin-users.html" "GET /admin-users.html"
check_auth_page "/profile.html" "GET /profile.html"

ME_CODE="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE_JAR" "$BASE_URL/api/me")"
[[ "$ME_CODE" == "200" ]] && pass "GET /api/me" || fail "GET /api/me (HTTP $ME_CODE)"

echo "✅ Smoke R1-R3 PASS"
