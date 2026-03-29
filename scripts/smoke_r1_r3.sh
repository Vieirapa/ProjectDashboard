#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" /tmp/pdash-login.out /tmp/pdash-edit-target' EXIT

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

python3 - "$COOKIE_JAR" > /tmp/pdash-edit-target <<'PY'
import json
import sys
import urllib.request
from http.cookiejar import MozillaCookieJar
from urllib.request import build_opener, HTTPCookieProcessor

cookie_path = sys.argv[1]
jar = MozillaCookieJar()
jar.load(cookie_path, ignore_discard=True, ignore_expires=True)
opener = build_opener(HTTPCookieProcessor(jar))
base = 'http://127.0.0.1:8765'

try:
    with opener.open(base + '/api/projects-registry') as resp:
        projects = json.load(resp).get('projects') or []
    for p in projects:
        pid = p.get('project_id')
        if not pid:
            continue
        with opener.open(base + f'/api/documents?project_id={pid}') as resp:
            docs = json.load(resp).get('documents') or []
        if docs:
            slug = docs[0].get('slug') or ''
            if slug:
                print(f'{slug}|{pid}')
                break
    else:
        print('')
except Exception:
    print('')
PY

EDIT_TARGET="$(cat /tmp/pdash-edit-target)"
EDIT_SLUG="${EDIT_TARGET%%|*}"
EDIT_PID="${EDIT_TARGET##*|}"
if [[ -n "$EDIT_SLUG" && -n "$EDIT_PID" && "$EDIT_TARGET" == *"|"* ]]; then
  check_auth_page "/edit.html?slug=${EDIT_SLUG}&project_id=${EDIT_PID}" "GET /edit.html"
else
  echo "ℹ️ GET /edit.html skipped (no document slug available in accessible projects)"
fi

ME_CODE="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE_JAR" "$BASE_URL/api/me")"
[[ "$ME_CODE" == "200" ]] && pass "GET /api/me" || fail "GET /api/me (HTTP $ME_CODE)"

echo "✅ Smoke R1-R3 PASS"
