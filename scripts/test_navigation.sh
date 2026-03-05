#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"

echo "[nav-test] static sidebar consistency checks"

pages=(index.html projects.html profile.html admin-users.html settings.html edit.html)
for p in "${pages[@]}"; do
  f="$WEB_DIR/$p"
  grep -q 'id="sidebar-root"' "$f" || { echo "[nav-test] FAIL: $p missing sidebar-root"; exit 1; }
  grep -q 'data-active=' "$f" || { echo "[nav-test] FAIL: $p missing data-active"; exit 1; }
  grep -q '/sidebar.js' "$f" || { echo "[nav-test] FAIL: $p missing sidebar.js include"; exit 1; }
  grep -q 'Área de trabalho\|ProjectDashbord\|ProjectDashboard\|<aside class="sidebar"' "$f" || true
  echo "[nav-test] OK: $p"
done

echo "[nav-test] javascript syntax checks"
node --check "$WEB_DIR/sidebar.js"
node --check "$WEB_DIR/app.js"
node --check "$WEB_DIR/edit.js"
node --check "$WEB_DIR/projects.js"
node --check "$WEB_DIR/profile.js"
node --check "$WEB_DIR/settings.js"
node --check "$WEB_DIR/admin-users.js"

echo "[nav-test] PASS"
