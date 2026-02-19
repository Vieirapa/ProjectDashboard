#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("/home/panosso/.openclaw/workspace/projects")
WEB_DIR = Path(__file__).parent / "web"
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "projectdashboard.db"
HOST = "0.0.0.0"
PORT = 8765
STATUSES = ["Backlog", "Em andamento", "Bloqueado", "Concluído"]
PRIORITIES = ["Baixa", "Média", "Alta", "Urgente"]
ROLES = ["admin", "member"]
SKIP_DIRS = {"ProjectDashboard", "__pycache__"}
SESSION_COOKIE = "pdash_session"
SESSION_TTL_SECONDS = 60 * 60 * 24

SESSIONS: dict[str, dict] = {}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower() or "projeto"


def hash_password(password: str, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        return hmac.compare_digest(hash_password(password, salt_hex), f"{salt_hex}${digest_hex}")
    except Exception:
        return False


def read_text_if_exists(path: Path) -> str:
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def infer_description(project_dir: Path) -> str:
    for line in read_text_if_exists(project_dir / "README.md").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:180]
    return "Sem descrição"


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, col: str, ddl: str):
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
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
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                created_by TEXT NOT NULL,
                used_by TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        ensure_column(conn, "users", "role", "role TEXT NOT NULL DEFAULT 'member'")

        if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0:
            pwd = os.getenv("PDASH_INITIAL_PASSWORD", "admin123")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                ("admin", hash_password(pwd), now_iso()),
            )
            print("[ProjectDashboard] Usuário inicial: admin / senha:", pwd)

        # Garantir que o usuário admin seja realmente admin após upgrades/migrações
        conn.execute("UPDATE users SET role='admin' WHERE username='admin'")


def audit(actor: str, action: str, target: str, details: str = ""):
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_logs (actor, action, target, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (actor, action, target, details, now_iso()),
        )


def migrate_existing_projects():
    with db() as conn:
        for p in sorted(BASE_DIR.iterdir()):
            if not p.is_dir() or p.name in SKIP_DIRS:
                continue
            slug = p.name.lower()
            if conn.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone():
                continue

            data = {}
            meta = p / "project.json"
            if meta.exists():
                try:
                    data = json.loads(meta.read_text(encoding="utf-8"))
                except Exception:
                    data = {}

            conn.execute(
                """
                INSERT INTO projects (slug, name, status, priority, owner, due_date, description, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    data.get("name") or p.name,
                    data.get("status") if data.get("status") in STATUSES else "Backlog",
                    data.get("priority") if data.get("priority") in PRIORITIES else "Média",
                    data.get("owner") or "",
                    data.get("dueDate") or "",
                    data.get("description") or infer_description(p),
                    str(p),
                    data.get("updatedAt") or now_iso(),
                ),
            )


def list_projects() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at FROM projects ORDER BY name").fetchall()
    return [{
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": r["due_date"], "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"]
    } for r in rows]


def get_project(slug: str) -> dict | None:
    with db() as conn:
        r = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at FROM projects WHERE slug=?", (slug,)).fetchone()
    if not r:
        return None
    return {
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": r["due_date"], "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"]
    }


def list_audit_logs(limit: int = 200) -> list[dict]:
    limit = max(1, min(limit, 1000))
    with db() as conn:
        rows = conn.execute(
            "SELECT actor, action, target, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def sync_project_meta(project: dict):
    p = Path(project["path"])
    (p / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_project(payload: dict) -> tuple[bool, str]:
    name = (payload.get("name") or "").strip()
    if not name:
        return False, "Nome é obrigatório"
    slug = slugify(name)
    proj_dir = BASE_DIR / slug
    if proj_dir.exists():
        return False, "Projeto já existe"

    project = {
        "slug": slug,
        "name": name,
        "status": payload.get("status") if payload.get("status") in STATUSES else "Backlog",
        "priority": payload.get("priority") if payload.get("priority") in PRIORITIES else "Média",
        "owner": (payload.get("owner") or "").strip(),
        "dueDate": (payload.get("dueDate") or "").strip(),
        "description": (payload.get("description") or "Sem descrição").strip(),
        "path": str(proj_dir),
        "updatedAt": now_iso(),
    }

    proj_dir.mkdir(parents=True, exist_ok=False)
    (proj_dir / "README.md").write_text(f"# Projeto: {project['name']}\n\n{project['description']}\n", encoding="utf-8")
    (proj_dir / "TASKS.md").write_text("# TASKS\n\n## Done\n\n- [ ] Inicializar projeto\n\n## Next\n\n- [ ] Definir roadmap\n", encoding="utf-8")

    with db() as conn:
        conn.execute(
            "INSERT INTO projects (slug,name,status,priority,owner,due_date,description,path,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (project["slug"], project["name"], project["status"], project["priority"], project["owner"], project["dueDate"], project["description"], project["path"], project["updatedAt"]),
        )
    sync_project_meta(project)
    return True, "ok"


def patch_project(slug: str, payload: dict) -> tuple[bool, str]:
    p = get_project(slug)
    if not p:
        return False, "Projeto não encontrado"
    if "name" in payload and str(payload["name"]).strip():
        p["name"] = str(payload["name"]).strip()
    if "status" in payload and payload["status"] in STATUSES:
        p["status"] = payload["status"]
    if "priority" in payload and payload["priority"] in PRIORITIES:
        p["priority"] = payload["priority"]
    if "owner" in payload:
        p["owner"] = str(payload["owner"]).strip()
    if "dueDate" in payload:
        p["dueDate"] = str(payload["dueDate"]).strip()
    if "description" in payload:
        p["description"] = str(payload["description"]).strip() or "Sem descrição"
    p["updatedAt"] = now_iso()

    with db() as conn:
        conn.execute("UPDATE projects SET name=?,status=?,priority=?,owner=?,due_date=?,description=?,updated_at=? WHERE slug=?",
                     (p["name"], p["status"], p["priority"], p["owner"], p["dueDate"], p["description"], p["updatedAt"], slug))
    sync_project_meta(p)
    return True, "ok"


def delete_project(slug: str) -> tuple[bool, str]:
    p = get_project(slug)
    if not p:
        return False, "Projeto não encontrado"
    with db() as conn:
        conn.execute("DELETE FROM projects WHERE slug=?", (slug,))
    return True, "ok"


def create_session(username: str, role: str) -> str:
    token = secrets.token_hex(24)
    SESSIONS[token] = {"username": username, "role": role, "exp": datetime.utcnow().timestamp() + SESSION_TTL_SECONDS}
    return token


def parse_cookie(raw: str | None) -> dict:
    if not raw:
        return {}
    jar = cookies.SimpleCookie(); jar.load(raw)
    return {k: v.value for k, v in jar.items()}


def current_user_from_cookie(raw_cookie: str | None) -> dict | None:
    tok = parse_cookie(raw_cookie).get(SESSION_COOKIE)
    if not tok or tok not in SESSIONS:
        return None
    s = SESSIONS[tok]
    if datetime.utcnow().timestamp() > s["exp"]:
        SESSIONS.pop(tok, None)
        return None
    return {"username": s["username"], "role": s["role"], "token": tok}


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict, set_cookie: str | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404); return
        b = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _read_json(self):
        l = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(l).decode("utf-8") if l else "{}"
        try:
            return True, json.loads(raw)
        except Exception:
            return False, {"error": "JSON inválido"}

    def _user(self):
        return current_user_from_cookie(self.headers.get("Cookie"))

    def _require_auth(self):
        u = self._user()
        if u: return u
        self._json(401, {"ok": False, "error": "unauthorized"}); return None

    def _require_admin(self):
        u = self._require_auth()
        if not u: return None
        if u["role"] != "admin":
            self._json(403, {"ok": False, "error": "forbidden"}); return None
        return u

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ["/", "/index.html"]: return self._serve(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if p == "/login.html": return self._serve(WEB_DIR / "login.html", "text/html; charset=utf-8")
        if p == "/signup.html": return self._serve(WEB_DIR / "signup.html", "text/html; charset=utf-8")
        if p == "/edit.html": return self._serve(WEB_DIR / "edit.html", "text/html; charset=utf-8")
        if p == "/admin-users.html": return self._serve(WEB_DIR / "admin-users.html", "text/html; charset=utf-8")
        if p in ["/app.js", "/edit.js", "/login.js", "/signup.js", "/admin-users.js", "/styles.css"]:
            ctype = "application/javascript; charset=utf-8" if p.endswith(".js") else "text/css; charset=utf-8"
            return self._serve(WEB_DIR / p.lstrip("/"), ctype)

        if p == "/api/me":
            u = self._user()
            return self._json(200 if u else 401, {"ok": bool(u), "user": {"username": u["username"], "role": u["role"]} if u else None})

        if p == "/api/projects":
            if not self._require_auth(): return
            return self._json(200, {"projects": list_projects(), "statuses": STATUSES, "priorities": PRIORITIES})

        if p.startswith("/api/projects/"):
            if not self._require_auth(): return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj: return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            return self._json(200, {"ok": True, "project": proj, "statuses": STATUSES, "priorities": PRIORITIES})

        if p == "/api/admin/users":
            if not self._require_admin(): return
            with db() as conn:
                user_rows = conn.execute("SELECT username, role, created_at FROM users ORDER BY username").fetchall()
                users = []
                for r in user_rows:
                    task_count = conn.execute(
                        "SELECT COUNT(*) AS c FROM projects WHERE owner = ?",
                        (r["username"],),
                    ).fetchone()["c"]
                    users.append({
                        "username": r["username"],
                        "role": r["role"],
                        "created_at": r["created_at"],
                        "associated_tasks": task_count,
                    })
            return self._json(200, {"ok": True, "users": users, "roles": ROLES})

        if p == "/api/admin/audit":
            if not self._require_admin(): return
            return self._json(200, {"ok": True, "logs": list_audit_logs(300)})

        self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path

        if p == "/api/login":
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            username = (body.get("username") or "").strip()
            password = body.get("password") or ""
            with db() as conn:
                row = conn.execute("SELECT username,password_hash,role FROM users WHERE username=?", (username,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return self._json(401, {"ok": False, "error": "Credenciais inválidas"})
            tok = create_session(row["username"], row["role"])
            cookie = f"{SESSION_COOKIE}={tok}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_TTL_SECONDS}"
            return self._json(200, {"ok": True, "user": {"username": row["username"], "role": row["role"]}}, set_cookie=cookie)

        if p == "/api/logout":
            u = self._user()
            if u: SESSIONS.pop(u["token"], None)
            return self._json(200, {"ok": True}, set_cookie=f"{SESSION_COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")

        if p == "/api/projects":
            user = self._require_auth()
            if not user: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = create_project(body)
            if done:
                audit(user["username"], "project.create", body.get("name", ""), f"status={body.get('status','Backlog')}")
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p == "/api/admin/users":
            admin = self._require_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            username = (body.get("username") or "").strip()
            password = body.get("password") or ""
            role = body.get("role") if body.get("role") in ROLES else "member"
            if not username or not password:
                return self._json(400, {"ok": False, "error": "username e password são obrigatórios"})
            try:
                with db() as conn:
                    conn.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
                                 (username, hash_password(password), role, now_iso()))
            except sqlite3.IntegrityError:
                return self._json(400, {"ok": False, "error": "usuário já existe"})
            audit(admin["username"], "user.create", username, f"role={role}")
            return self._json(200, {"ok": True})

        if p == "/api/admin/invites":
            admin = self._require_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            role = body.get("role") if body.get("role") in ROLES else "member"
            token = secrets.token_urlsafe(24)
            exp = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0).isoformat() + "Z"
            with db() as conn:
                conn.execute("INSERT INTO invites (token,role,created_by,expires_at,created_at) VALUES (?,?,?,?,?)",
                             (token, role, admin["username"], exp, now_iso()))
            audit(admin["username"], "invite.create", token, f"role={role} expires={exp}")
            return self._json(200, {"ok": True, "inviteUrl": f"/signup.html?token={token}", "token": token, "expiresAt": exp})

        if p == "/api/signup":
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            token = body.get("token") or ""
            username = (body.get("username") or "").strip()
            password = body.get("password") or ""
            if not token or not username or not password:
                return self._json(400, {"ok": False, "error": "dados incompletos"})
            with db() as conn:
                inv = conn.execute("SELECT token, role, used_by, expires_at FROM invites WHERE token=?", (token,)).fetchone()
                if not inv: return self._json(400, {"ok": False, "error": "convite inválido"})
                if inv["used_by"]: return self._json(400, {"ok": False, "error": "convite já usado"})
                if datetime.fromisoformat(inv["expires_at"].replace("Z", "")) < datetime.utcnow():
                    return self._json(400, {"ok": False, "error": "convite expirado"})
                try:
                    conn.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
                                 (username, hash_password(password), inv["role"], now_iso()))
                    conn.execute("UPDATE invites SET used_by=? WHERE token=?", (username, token))
                except sqlite3.IntegrityError:
                    return self._json(400, {"ok": False, "error": "usuário já existe"})
            audit(username, "user.signup", username, f"role={inv['role']}")
            return self._json(200, {"ok": True})

        self.send_error(404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        if p.startswith("/api/projects/"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = patch_project(slug, body)
            if done:
                audit(user["username"], "project.update", slug, json.dumps(body, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/users/"):
            admin = self._require_admin()
            if not admin: return
            username = p.split("/")[4]
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})

            updates = []
            params = []
            if "role" in body:
                role = body.get("role")
                if role not in ROLES:
                    return self._json(400, {"ok": False, "error": "role inválida"})
                updates.append("role=?")
                params.append(role)
            if "password" in body:
                pwd = body.get("password") or ""
                if len(pwd) < 4:
                    return self._json(400, {"ok": False, "error": "senha muito curta"})
                updates.append("password_hash=?")
                params.append(hash_password(pwd))

            if not updates:
                return self._json(400, {"ok": False, "error": "nada para atualizar"})

            params.append(username)
            with db() as conn:
                exists = conn.execute("SELECT username FROM users WHERE username=?", (username,)).fetchone()
                if not exists:
                    return self._json(404, {"ok": False, "error": "usuário não encontrado"})
                conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE username=?", tuple(params))

            safe_details = {}
            if "role" in body:
                safe_details["role"] = body.get("role")
            if "password" in body:
                safe_details["password"] = "***changed***"
            audit(admin["username"], "user.update", username, json.dumps(safe_details, ensure_ascii=False))
            return self._json(200, {"ok": True})

        self.send_error(404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        if p.startswith("/api/projects/"):
            admin = self._require_admin()
            if not admin: return
            slug = p.split("/")[3]
            done, msg = delete_project(slug)
            if done:
                audit(admin["username"], "project.delete", slug)
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/users/"):
            admin = self._require_admin()
            if not admin: return
            username = p.split("/")[4]
            if username == admin["username"]:
                return self._json(400, {"ok": False, "error": "não é permitido apagar seu próprio usuário"})
            with db() as conn:
                exists = conn.execute("SELECT username, role FROM users WHERE username=?", (username,)).fetchone()
                if not exists:
                    return self._json(404, {"ok": False, "error": "usuário não encontrado"})
                if exists["role"] == "admin":
                    return self._json(400, {"ok": False, "error": "não é permitido apagar usuários admin"})
                conn.execute("DELETE FROM users WHERE username=?", (username,))
            audit(admin["username"], "user.delete", username)
            return self._json(200, {"ok": True})

        self.send_error(404)


def main():
    init_db()
    migrate_existing_projects()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"ProjectDashboard online em http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
