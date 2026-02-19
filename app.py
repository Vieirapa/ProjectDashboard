#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path("/home/panosso/.openclaw/workspace/projects")
WEB_DIR = Path(__file__).parent / "web"
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "projectdashboard.db"
HOST = "0.0.0.0"
PORT = 8765
STATUSES = ["Backlog", "Em andamento", "Bloqueado", "Concluído"]
PRIORITIES = ["Baixa", "Média", "Alta", "Urgente"]
SKIP_DIRS = {"ProjectDashboard", "__pycache__"}
SESSION_COOKIE = "pdash_session"
SESSION_TTL_SECONDS = 60 * 60 * 24  # 24h

# Sessões em memória (suficiente para v1). No futuro podemos persistir em Redis/DB.
SESSIONS: dict[str, dict] = {}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower() or "projeto"


def read_text_if_exists(path: Path) -> str:
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def infer_description(project_dir: Path) -> str:
    readme = read_text_if_exists(project_dir / "README.md").strip().splitlines()
    for line in readme:
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:180]
    return "Sem descrição"


def hash_password(password: str, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        candidate = hash_password(password, salt_hex=salt_hex)
        return hmac.compare_digest(candidate, f"{salt_hex}${digest_hex}")
    except Exception:
        return False


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slug TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              status TEXT NOT NULL,
              priority TEXT NOT NULL,
              owner TEXT NOT NULL DEFAULT '',
              due_date TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL,
              path TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )

        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if user_count == 0:
            initial_password = os.getenv("PDASH_INITIAL_PASSWORD", "admin123")
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                ("admin", hash_password(initial_password), now_iso()),
            )
            print("[ProjectDashboard] Usuário inicial criado: admin")
            print("[ProjectDashboard] Senha inicial: ", initial_password)
            print("[ProjectDashboard] Troque essa senha assim que possível.")


def upsert_project_meta_file(project_dir: Path, payload: dict):
    meta_path = project_dir / "project.json"
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def migrate_existing_projects():
    with db() as conn:
        for p in sorted(BASE_DIR.iterdir()):
            if not p.is_dir() or p.name in SKIP_DIRS:
                continue

            slug = p.name.lower()
            exists = conn.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone()
            if exists:
                continue

            data = {}
            meta_path = p / "project.json"
            if meta_path.exists():
                try:
                    data = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    data = {}

            status = data.get("status") if data.get("status") in STATUSES else "Backlog"
            priority = data.get("priority") if data.get("priority") in PRIORITIES else "Média"
            description = data.get("description") or infer_description(p)

            conn.execute(
                """
                INSERT INTO projects (slug, name, status, priority, owner, due_date, description, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    data.get("name") or p.name,
                    status,
                    priority,
                    data.get("owner") or "",
                    data.get("dueDate") or "",
                    description,
                    str(p),
                    data.get("updatedAt") or now_iso(),
                ),
            )


def list_projects() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT slug, name, status, priority, owner, due_date, description, path, updated_at FROM projects ORDER BY name"
        ).fetchall()
        return [
            {
                "slug": r["slug"],
                "name": r["name"],
                "status": r["status"],
                "priority": r["priority"],
                "owner": r["owner"],
                "dueDate": r["due_date"],
                "description": r["description"],
                "path": r["path"],
                "updatedAt": r["updated_at"],
            }
            for r in rows
        ]


def get_project(slug: str) -> dict | None:
    with db() as conn:
        r = conn.execute(
            "SELECT slug, name, status, priority, owner, due_date, description, path, updated_at FROM projects WHERE slug=?",
            (slug,),
        ).fetchone()
        if not r:
            return None
        return {
            "slug": r["slug"],
            "name": r["name"],
            "status": r["status"],
            "priority": r["priority"],
            "owner": r["owner"],
            "dueDate": r["due_date"],
            "description": r["description"],
            "path": r["path"],
            "updatedAt": r["updated_at"],
        }


def create_project(payload: dict) -> tuple[bool, str]:
    name = (payload.get("name") or "").strip()
    if not name:
        return False, "Nome é obrigatório"

    slug = slugify(name)
    project_dir = BASE_DIR / slug
    if project_dir.exists():
        return False, "Já existe um projeto com esse nome"

    status = payload.get("status") if payload.get("status") in STATUSES else "Backlog"
    priority = payload.get("priority") if payload.get("priority") in PRIORITIES else "Média"
    description = (payload.get("description") or "Sem descrição").strip()
    owner = (payload.get("owner") or "").strip()
    due_date = (payload.get("dueDate") or "").strip()

    project_dir.mkdir(parents=True, exist_ok=False)
    (project_dir / "README.md").write_text(f"# Projeto: {name}\n\n{description}\n", encoding="utf-8")
    (project_dir / "TASKS.md").write_text(
        "# TASKS\n\n## Done\n\n- [ ] Inicializar projeto\n\n## Next\n\n- [ ] Definir roadmap\n",
        encoding="utf-8",
    )

    record = {
        "slug": slug,
        "name": name,
        "status": status,
        "priority": priority,
        "owner": owner,
        "dueDate": due_date,
        "description": description,
        "path": str(project_dir),
        "updatedAt": now_iso(),
    }

    with db() as conn:
        conn.execute(
            """
            INSERT INTO projects (slug, name, status, priority, owner, due_date, description, path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["slug"],
                record["name"],
                record["status"],
                record["priority"],
                record["owner"],
                record["dueDate"],
                record["description"],
                record["path"],
                record["updatedAt"],
            ),
        )

    upsert_project_meta_file(project_dir, record)
    return True, "ok"


def patch_project(slug: str, payload: dict) -> tuple[bool, str]:
    current = get_project(slug)
    if not current:
        return False, "Projeto não encontrado"

    if "name" in payload and str(payload["name"]).strip():
        current["name"] = str(payload["name"]).strip()
    if "status" in payload and payload["status"] in STATUSES:
        current["status"] = payload["status"]
    if "priority" in payload and payload["priority"] in PRIORITIES:
        current["priority"] = payload["priority"]
    if "owner" in payload:
        current["owner"] = str(payload["owner"]).strip()
    if "dueDate" in payload:
        current["dueDate"] = str(payload["dueDate"]).strip()
    if "description" in payload:
        current["description"] = str(payload["description"]).strip() or "Sem descrição"

    current["updatedAt"] = now_iso()

    with db() as conn:
        conn.execute(
            """
            UPDATE projects
               SET name=?, status=?, priority=?, owner=?, due_date=?, description=?, updated_at=?
             WHERE slug=?
            """,
            (
                current["name"],
                current["status"],
                current["priority"],
                current["owner"],
                current["dueDate"],
                current["description"],
                current["updatedAt"],
                slug,
            ),
        )

    project_dir = Path(current["path"])
    upsert_project_meta_file(project_dir, current)
    return True, "ok"


def create_session(username: str) -> str:
    token = secrets.token_hex(24)
    SESSIONS[token] = {
        "username": username,
        "expires": datetime.utcnow().timestamp() + SESSION_TTL_SECONDS,
    }
    return token


def session_username(token: str | None) -> str | None:
    if not token:
        return None
    s = SESSIONS.get(token)
    if not s:
        return None
    if datetime.utcnow().timestamp() > s["expires"]:
        SESSIONS.pop(token, None)
        return None
    return s["username"]


def parse_cookie(raw_cookie: str | None) -> dict:
    if not raw_cookie:
        return {}
    jar = cookies.SimpleCookie()
    jar.load(raw_cookie)
    return {k: v.value for k, v in jar.items()}


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404)
            return
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            return True, json.loads(raw)
        except Exception:
            return False, {"error": "JSON inválido"}

    def _current_user(self) -> str | None:
        c = parse_cookie(self.headers.get("Cookie"))
        return session_username(c.get(SESSION_COOKIE))

    def _require_auth(self) -> bool:
        if self._current_user():
            return True
        self._json(401, {"ok": False, "error": "unauthorized"})
        return False

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            return self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/login.html":
            return self._serve_file(WEB_DIR / "login.html", "text/html; charset=utf-8")
        if parsed.path == "/edit.html":
            return self._serve_file(WEB_DIR / "edit.html", "text/html; charset=utf-8")
        if parsed.path == "/app.js":
            return self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/edit.js":
            return self._serve_file(WEB_DIR / "edit.js", "application/javascript; charset=utf-8")
        if parsed.path == "/login.js":
            return self._serve_file(WEB_DIR / "login.js", "application/javascript; charset=utf-8")
        if parsed.path == "/styles.css":
            return self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")

        if parsed.path == "/api/me":
            user = self._current_user()
            if not user:
                return self._json(401, {"ok": False, "error": "unauthorized"})
            return self._json(200, {"ok": True, "user": {"username": user}})

        if parsed.path == "/api/projects":
            if not self._require_auth():
                return
            return self._json(
                200,
                {"projects": list_projects(), "statuses": STATUSES, "priorities": PRIORITIES},
            )

        if parsed.path.startswith("/api/projects/"):
            if not self._require_auth():
                return
            slug = parsed.path.split("/")[3]
            project = get_project(slug)
            if not project:
                return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            return self._json(200, {"ok": True, "project": project, "statuses": STATUSES, "priorities": PRIORITIES})

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/login":
            ok, payload = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": payload["error"]})
            username = (payload.get("username") or "").strip()
            password = payload.get("password") or ""
            with db() as conn:
                row = conn.execute(
                    "SELECT username, password_hash FROM users WHERE username=?", (username,)
                ).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return self._json(401, {"ok": False, "error": "Credenciais inválidas"})

            token = create_session(username)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_TTL_SECONDS}",
            )
            body = json.dumps({"ok": True, "user": {"username": username}}, ensure_ascii=False).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/logout":
            c = parse_cookie(self.headers.get("Cookie"))
            tok = c.get(SESSION_COOKIE)
            if tok:
                SESSIONS.pop(tok, None)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")
            body = b'{"ok":true}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/projects":
            if not self._require_auth():
                return
            ok, payload = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": payload["error"]})
            done, msg = create_project(payload)
            if not done:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True})

        self.send_error(404)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/projects/"):
            if not self._require_auth():
                return
            slug = parsed.path.split("/")[3]
            ok, payload = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": payload["error"]})
            done, msg = patch_project(slug, payload)
            if not done:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True})

        self.send_error(404)


def main():
    init_db()
    migrate_existing_projects()

    server = HTTPServer((HOST, PORT), Handler)
    print(f"ProjectDashboard online em http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
