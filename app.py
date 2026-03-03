#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import smtplib
import threading
import time
from email.message import EmailMessage
from datetime import datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path("/home/panosso/.openclaw/workspace/projects")
WEB_DIR = Path(__file__).parent / "web"
DATA_DIR = Path(__file__).parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DOCS_REPO_DIR = DATA_DIR / "docs_repo"
DB_PATH = DATA_DIR / "projectdashboard.db"
HOST = os.getenv("PDASH_HOST", "0.0.0.0")
PORT = int(os.getenv("PDASH_PORT", "8765"))
STATUSES = ["Backlog", "Em andamento", "Em revisão", "Concluído"]
PRIORITIES = ["Baixa", "Média", "Alta", "Urgente"]
ROLES = ["admin", "member", "desenhista", "revisor", "cliente"]
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


def can_create_project(role: str) -> bool:
    return role in {"admin", "member"}


def can_edit_project(role: str) -> bool:
    return role in {"admin", "member", "desenhista"}


def can_upload_document(role: str) -> bool:
    return role in {"admin", "member", "desenhista"}


def can_add_review_note(role: str) -> bool:
    return role in {"admin", "member", "desenhista", "revisor"}


def can_resolve_review_note(role: str) -> bool:
    return role in {"desenhista", "admin"}


def can_delete_project(role: str, user: str, project: dict) -> bool:
    if role == "admin":
        return True
    if role == "member":
        return (project.get("createdBy") or "").strip().lower() == user.strip().lower()
    return False


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_slug TEXT NOT NULL,
                version INTEGER NOT NULL,
                document_name TEXT NOT NULL,
                document_mime TEXT NOT NULL,
                document_status TEXT NOT NULL,
                file_rel_path TEXT NOT NULL,
                git_commit TEXT NOT NULL,
                checksum TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(project_slug, version)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_slug TEXT NOT NULL,
                note TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_by TEXT NOT NULL DEFAULT '',
                resolved_at TEXT NOT NULL DEFAULT '',
                is_resolved INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_by TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS periodic_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                statuses_json TEXT NOT NULL,
                priorities_json TEXT NOT NULL,
                roles_json TEXT NOT NULL,
                weekdays_json TEXT NOT NULL,
                run_time TEXT NOT NULL,
                message TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                last_run_key TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        ensure_column(conn, "users", "role", "role TEXT NOT NULL DEFAULT 'member'")
        ensure_column(conn, "projects", "document_status", "document_status TEXT NOT NULL DEFAULT 'aguardando edição'")
        ensure_column(conn, "projects", "document_name", "document_name TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "projects", "document_mime", "document_mime TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "projects", "document_path", "document_path TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "projects", "created_by", "created_by TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "review_notes", "resolved_by", "resolved_by TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "review_notes", "resolved_at", "resolved_at TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "review_notes", "is_resolved", "is_resolved INTEGER NOT NULL DEFAULT 0")

        ensure_column(conn, "users", "email", "email TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "users", "phone", "phone TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "users", "extension", "extension TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "users", "work_area", "work_area TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "users", "notes", "notes TEXT NOT NULL DEFAULT ''")

        if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0:
            pwd = os.getenv("PDASH_INITIAL_PASSWORD", "admin123")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                ("admin", hash_password(pwd), now_iso()),
            )
            print("[ProjectDashboard] Initial user: admin / password:", pwd)

        # Ensure admin user keeps admin role after upgrades/migrations
        conn.execute("UPDATE users SET role='admin' WHERE username='admin'")
        conn.execute("UPDATE projects SET status='Em revisão' WHERE status='Bloqueado'")
        conn.execute("UPDATE projects SET document_status=status")
        conn.execute("UPDATE projects SET created_by=owner WHERE created_by='' AND owner<>''")

        for k, v in [
            ("smtp.host", ""),
            ("smtp.port", "587"),
            ("smtp.user", ""),
            ("smtp.pass", ""),
            ("smtp.from", ""),
            ("smtp.tls", "true"),
            ("invite.default_message", "Olá!\n\nVocê foi convidado(a) para acessar o ProjectDashboard.\n\nUse este link para concluir seu cadastro:\n{invite_link}\n\nEste convite expira em: {expires_at}\n\nBem-vindo(a) ao sistema!"),
            ("workflow.default_due_days", "7"),
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value, updated_by, updated_at) VALUES (?, ?, '', '')",
                (k, v),
            )


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
                INSERT INTO projects (slug, name, status, priority, owner, due_date, description, path, updated_at, document_status, document_name, document_mime, document_path, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    data.get("name") or p.name,
                    ("Em revisão" if data.get("status") == "Bloqueado" else data.get("status")) if ("Em revisão" if data.get("status") == "Bloqueado" else data.get("status")) in STATUSES else "Backlog",
                    data.get("priority") if data.get("priority") in PRIORITIES else "Média",
                    data.get("owner") or "",
                    data.get("dueDate") or "",
                    data.get("description") or infer_description(p),
                    str(p),
                    data.get("updatedAt") or now_iso(),
                    ("Backlog" if data.get("documentStatus") == "aguardando edição" else "Em andamento" if data.get("documentStatus") == "editando" else "Em revisão" if data.get("documentStatus") == "em revisão" else "Concluído" if data.get("documentStatus") == "release" else (("Em revisão" if data.get("status") == "Bloqueado" else data.get("status")) if ("Em revisão" if data.get("status") == "Bloqueado" else data.get("status")) in STATUSES else "Backlog")),
                    data.get("documentName") or "",
                    data.get("documentMime") or "",
                    data.get("documentPath") or "",
                    data.get("createdBy") or data.get("owner") or "",
                ),
            )


def list_projects() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by FROM projects ORDER BY name").fetchall()
    return [{
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": r["due_date"], "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"],
        "documentStatus": ("aguardando edição" if r["status"] == "Backlog" else "em andamento" if r["status"] == "Em andamento" else "em revisão" if r["status"] == "Em revisão" else "release"), "documentName": r["document_name"],
        "documentMime": r["document_mime"], "hasDocument": bool(r["document_path"]),
        "createdBy": r["created_by"]
    } for r in rows]


def get_project(slug: str) -> dict | None:
    with db() as conn:
        r = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by FROM projects WHERE slug=?", (slug,)).fetchone()
    if not r:
        return None
    return {
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": r["due_date"], "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"],
        "documentStatus": ("aguardando edição" if r["status"] == "Backlog" else "em andamento" if r["status"] == "Em andamento" else "em revisão" if r["status"] == "Em revisão" else "release"), "documentName": r["document_name"],
        "documentMime": r["document_mime"], "documentPath": r["document_path"],
        "hasDocument": bool(r["document_path"]), "createdBy": r["created_by"]
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


def create_project(payload: dict, actor: str) -> tuple[bool, str]:
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
        "dueDate": (payload.get("dueDate") or "").strip() or default_due_date_iso(),
        "description": (payload.get("description") or "Sem descrição").strip(),
        "path": str(proj_dir),
        "updatedAt": now_iso(),
        "documentName": "",
        "documentMime": "",
        "documentPath": "",
        "createdBy": actor,
    }

    proj_dir.mkdir(parents=True, exist_ok=False)
    (proj_dir / "README.md").write_text(f"# Projeto: {project['name']}\n\n{project['description']}\n", encoding="utf-8")
    (proj_dir / "TASKS.md").write_text("# TASKS\n\n## Done\n\n- [ ] Inicializar projeto\n\n## Next\n\n- [ ] Definir roadmap\n", encoding="utf-8")

    with db() as conn:
        conn.execute(
            "INSERT INTO projects (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project["slug"], project["name"], project["status"], project["priority"], project["owner"], project["dueDate"], project["description"], project["path"], project["updatedAt"], project["status"], project["documentName"], project["documentMime"], project["documentPath"], project["createdBy"]),
        )
    sync_project_meta(project)
    return True, "ok"


def patch_project(slug: str, payload: dict) -> tuple[bool, str]:
    p = get_project(slug)
    if not p:
        return False, "Projeto não encontrado"
    old_status = p.get("status")
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

    if p.get("status") != old_status and "dueDate" not in payload:
        p["dueDate"] = default_due_date_iso()
    if "description" in payload:
        p["description"] = str(payload["description"]).strip() or "Sem descrição"
    p["updatedAt"] = now_iso()

    with db() as conn:
        conn.execute("UPDATE projects SET name=?,status=?,priority=?,owner=?,due_date=?,description=?,document_status=?,updated_at=? WHERE slug=?",
                     (p["name"], p["status"], p["priority"], p["owner"], p["dueDate"], p["description"], p["status"], p["updatedAt"], slug))
    sync_project_meta(p)
    return True, "ok"


def run_git(args: list[str]) -> tuple[bool, str]:
    try:
        res = subprocess.run(["git", *args], cwd=str(DOCS_REPO_DIR), capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return False, (res.stderr or res.stdout or "git error").strip()
        return True, (res.stdout or "").strip()
    except Exception as e:
        return False, str(e)


def ensure_docs_repo() -> tuple[bool, str]:
    DOCS_REPO_DIR.mkdir(parents=True, exist_ok=True)
    if not (DOCS_REPO_DIR / ".git").exists():
        ok, out = run_git(["init", "-b", "main"])
        if not ok:
            return False, out
    return True, "ok"


def get_admin_settings() -> dict:
    with db() as conn:
        rows = conn.execute("SELECT key, value, updated_by, updated_at FROM app_settings ORDER BY key").fetchall()
    return {r["key"]: {"value": r["value"], "updated_by": r["updated_by"], "updated_at": r["updated_at"]} for r in rows}


def update_admin_settings(payload: dict, actor: str) -> tuple[bool, str]:
    allowed = {
        "smtp.host", "smtp.port", "smtp.user", "smtp.pass", "smtp.from", "smtp.tls",
        "invite.default_message", "workflow.default_due_days"
    }
    incoming = {k: str(v) for k, v in (payload or {}).items() if k in allowed}
    if not incoming:
        return False, "Nenhuma configuração válida enviada"

    if "smtp.port" in incoming:
        try:
            p = int(incoming["smtp.port"])
            if p <= 0 or p > 65535:
                return False, "smtp.port inválida"
        except Exception:
            return False, "smtp.port inválida"

    if "smtp.tls" in incoming:
        incoming["smtp.tls"] = "true" if incoming["smtp.tls"].strip().lower() in {"1", "true", "yes", "on"} else "false"

    if "workflow.default_due_days" in incoming:
        try:
            days = int(incoming["workflow.default_due_days"])
            if days < 0 or days > 3650:
                return False, "workflow.default_due_days inválido"
        except Exception:
            return False, "workflow.default_due_days inválido"

    with db() as conn:
        for key, value in incoming.items():
            conn.execute(
                "INSERT INTO app_settings (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                (key, value, actor, now_iso()),
            )
    return True, "ok"


def _setting(settings: dict, key: str, env_name: str, default: str = "") -> str:
    row = settings.get(key) if isinstance(settings, dict) else None
    val = (row.get("value") if isinstance(row, dict) else "") if row else ""
    return (val or os.getenv(env_name, default) or default).strip()


def default_due_date_iso() -> str:
    settings = get_admin_settings()
    raw = _setting(settings, "workflow.default_due_days", "PDASH_DEFAULT_DUE_DAYS", "7")
    try:
        days = int(raw)
    except Exception:
        days = 7
    days = max(0, min(days, 3650))
    return (datetime.utcnow() + timedelta(days=days)).date().isoformat()


def send_invite_email(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    settings = get_admin_settings()
    host = _setting(settings, "smtp.host", "PDASH_SMTP_HOST", "")
    port = int(_setting(settings, "smtp.port", "PDASH_SMTP_PORT", "587") or "587")
    user = _setting(settings, "smtp.user", "PDASH_SMTP_USER", "")
    password = _setting(settings, "smtp.pass", "PDASH_SMTP_PASS", "")
    sender = _setting(settings, "smtp.from", "PDASH_SMTP_FROM", user or "")
    use_tls = _setting(settings, "smtp.tls", "PDASH_SMTP_TLS", "true").lower() not in {"0", "false", "no"}

    if not host or not sender:
        return False, "SMTP não configurado (defina host e remetente em Configurações)"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls()
            if user:
                server.login(user, password)
            server.send_message(msg)
        return True, "ok"
    except Exception as e:
        return False, f"Falha ao enviar email: {e}"


def list_periodic_reports() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM periodic_reports ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        item = dict(r)
        for k in ["statuses_json", "priorities_json", "roles_json", "weekdays_json"]:
            try:
                item[k.replace("_json", "")] = json.loads(item.get(k) or "[]")
            except Exception:
                item[k.replace("_json", "")] = []
            item.pop(k, None)
        out.append(item)
    return out


def create_periodic_report(payload: dict, actor: str) -> tuple[bool, str]:
    name = str(payload.get("name") or "").strip()
    statuses = payload.get("statuses") or []
    priorities = payload.get("priorities") or []
    roles = payload.get("roles") or []
    weekdays = payload.get("weekdays") or []
    run_time = str(payload.get("run_time") or "").strip()
    message = str(payload.get("message") or "").strip()
    active = 1 if bool(payload.get("active", True)) else 0

    if not name:
        return False, "Nome do relatório é obrigatório"
    if not statuses:
        return False, "Selecione ao menos uma lista/status"
    if not priorities:
        return False, "Selecione filtros de dados do relatório"
    if not roles:
        return False, "Selecione ao menos um perfil de destino"
    if not weekdays:
        return False, "Selecione ao menos um dia da semana"
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", run_time):
        return False, "Horário inválido (use HH:MM)"

    now = now_iso()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO periodic_reports (name, statuses_json, priorities_json, roles_json, weekdays_json, run_time, message, active, created_by, created_at, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, json.dumps(statuses, ensure_ascii=False), json.dumps(priorities, ensure_ascii=False), json.dumps(roles, ensure_ascii=False), json.dumps(weekdays, ensure_ascii=False), run_time, message, active, actor, now, actor, now),
        )
    return True, "ok"


def update_periodic_report(report_id: int, payload: dict, actor: str) -> tuple[bool, str]:
    fields = {}
    mapping = {
        "name": "name", "run_time": "run_time", "message": "message", "active": "active",
        "statuses": "statuses_json", "priorities": "priorities_json", "roles": "roles_json", "weekdays": "weekdays_json"
    }
    for k, dbk in mapping.items():
        if k in payload:
            v = payload[k]
            if k in {"statuses", "priorities", "roles", "weekdays"}:
                v = json.dumps(v or [], ensure_ascii=False)
            if k == "active":
                v = 1 if bool(v) else 0
            fields[dbk] = v
    if not fields:
        return False, "nada para atualizar"
    fields["updated_by"] = actor
    fields["updated_at"] = now_iso()

    set_clause = ", ".join([f"{k}=?" for k in fields.keys()])
    params = list(fields.values()) + [report_id]
    with db() as conn:
        exists = conn.execute("SELECT id FROM periodic_reports WHERE id=?", (report_id,)).fetchone()
        if not exists:
            return False, "Relatório não encontrado"
        conn.execute(f"UPDATE periodic_reports SET {set_clause} WHERE id=?", tuple(params))
    return True, "ok"


def delete_periodic_report(report_id: int) -> tuple[bool, str]:
    with db() as conn:
        exists = conn.execute("SELECT id FROM periodic_reports WHERE id=?", (report_id,)).fetchone()
        if not exists:
            return False, "Relatório não encontrado"
        conn.execute("DELETE FROM periodic_reports WHERE id=?", (report_id,))
    return True, "ok"


def _render_report_markdown(report: dict) -> str:
    statuses = report.get("statuses") or []
    priorities = report.get("priorities") or []
    with db() as conn:
        rows = conn.execute("SELECT slug, name, status, priority, owner, due_date, updated_at FROM projects ORDER BY priority DESC, name").fetchall()
    items = []
    for r in rows:
        if statuses and r["status"] not in statuses:
            continue
        if "TODOS" not in priorities and priorities and r["priority"] not in priorities:
            continue
        items.append(r)

    lines = []
    lines.append(f"## 📊 {report.get('name','Periodic Report')}")
    lines.append("")
    lines.append(f"- Generated at: **{now_iso()}**")
    lines.append(f"- Lists included: **{', '.join(statuses) if statuses else '-'}**")
    lines.append(f"- Priority filter: **{', '.join(priorities) if priorities else '-'}**")
    lines.append("")
    lines.append("### Summary")
    lines.append(f"- Total cards: **{len(items)}**")
    lines.append("")
    lines.append("### Cards")
    if not items:
        lines.append("_No cards matched the selected criteria._")
    else:
        for it in items:
            lines.append(f"- **[{it['slug']}] {it['name']}**  ")
            lines.append(f"  Status: `{it['status']}` | Priority: `{it['priority']}` | Owner: `{it['owner'] or '-'}` | Due: `{it['due_date'] or '-'}`")
    return "\n".join(lines)


def compose_periodic_report_email(report: dict) -> tuple[str, str, list[sqlite3.Row]]:
    roles = report.get("roles") or []
    users = []
    if roles:
        with db() as conn:
            users = conn.execute(
                "SELECT username, role, email FROM users WHERE role IN ({}) AND email<>''".format(",".join(["?"] * len(roles))),
                tuple(roles),
            ).fetchall()

    md = _render_report_markdown(report)
    msg = (report.get("message") or "").strip()
    email_body = f"{msg}\n\n---\n\n{md}" if msg else md
    subject = f"[ProjectDashboard] {report.get('name','Periodic Report')}"
    return subject, email_body, users


def run_periodic_report(report: dict, actor: str = "system") -> tuple[bool, str]:
    roles = report.get("roles") or []
    if not roles:
        return False, "sem perfis de destino"

    subject, email_body, users = compose_periodic_report_email(report)
    if not users:
        return False, "nenhum usuário com email encontrado para os perfis selecionados"

    sent = 0
    for u in users:
        ok, _ = send_invite_email(u["email"], subject, email_body)
        if ok:
            sent += 1

    if sent == 0:
        return False, "falha ao enviar para os destinatários"
    return True, f"sent={sent}"


def report_scheduler_loop():
    while True:
        try:
            now = datetime.now()
            key = now.strftime("%Y-%m-%d %H:%M")
            weekday = str(now.weekday())  # 0=Mon ... 6=Sun
            reports = [r for r in list_periodic_reports() if int(r.get("active") or 0) == 1]
            for r in reports:
                days = [str(x) for x in (r.get("weekdays") or [])]
                run_time = str(r.get("run_time") or "")
                if weekday in days and run_time == now.strftime("%H:%M") and (r.get("last_run_key") or "") != key:
                    ok, msg = run_periodic_report(r)
                    with db() as conn:
                        conn.execute("UPDATE periodic_reports SET last_run_key=?, updated_at=?, updated_by=? WHERE id=?", (key, now_iso(), "system", r["id"]))
                    audit("system", "report.periodic.run", str(r.get("id")), f"ok={ok} {msg}")
        except Exception as e:
            print("[ProjectDashboard] report scheduler error:", e)
        time.sleep(30)


def list_document_versions(slug: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT version, document_name, document_mime, document_status, git_commit, checksum, created_by, created_at
            FROM document_versions
            WHERE project_slug=?
            ORDER BY version DESC
            """,
            (slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_review_notes(slug: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, note, created_by, created_at, resolved_by, resolved_at, is_resolved
            FROM review_notes
            WHERE project_slug=?
            ORDER BY id DESC
            """,
            (slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_review_note(slug: str, note: str, actor: str) -> tuple[bool, str]:
    proj = get_project(slug)
    if not proj:
        return False, "Projeto não encontrado"
    if (proj.get("status") or "").strip().lower() != "em revisão":
        return False, "Notas de revisão só podem ser adicionadas quando o documento estiver em 'em revisão'"
    clean_note = (note or "").strip()
    if not clean_note:
        return False, "Nota não pode estar vazia"
    if len(clean_note) > 4000:
        return False, "Nota muito longa (máximo 4000 caracteres)"
    with db() as conn:
        conn.execute(
            "INSERT INTO review_notes (project_slug, note, created_by, created_at) VALUES (?, ?, ?, ?)",
            (slug, clean_note, actor, now_iso()),
        )
    return True, "ok"


def set_review_note_resolution(slug: str, note_id: int, actor: str, resolved: bool) -> tuple[bool, str]:
    proj = get_project(slug)
    if not proj:
        return False, "Projeto não encontrado"
    if (proj.get("status") or "").strip().lower() != "em revisão":
        return False, "Notas só podem ser alteradas quando o card estiver em 'em revisão'"

    with db() as conn:
        row = conn.execute(
            "SELECT id FROM review_notes WHERE id=? AND project_slug=?",
            (note_id, slug),
        ).fetchone()
        if not row:
            return False, "Nota não encontrada"

        if resolved:
            conn.execute(
                "UPDATE review_notes SET is_resolved=1, resolved_by=?, resolved_at=? WHERE id=? AND project_slug=?",
                (actor, now_iso(), note_id, slug),
            )
        else:
            conn.execute(
                "UPDATE review_notes SET is_resolved=0, resolved_by='', resolved_at='' WHERE id=? AND project_slug=?",
                (note_id, slug),
            )
    return True, "ok"


def get_document_version(slug: str, version: int | None = None) -> dict | None:
    with db() as conn:
        if version is None:
            row = conn.execute(
                "SELECT * FROM document_versions WHERE project_slug=? ORDER BY version DESC LIMIT 1",
                (slug,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM document_versions WHERE project_slug=? AND version=?",
                (slug, version),
            ).fetchone()
    return dict(row) if row else None


def save_project_document(slug: str, filename: str, mime_type: str, b64_content: str, actor: str) -> tuple[bool, str]:
    p = get_project(slug)
    if not p:
        return False, "Projeto não encontrado"

    ok_repo, repo_msg = ensure_docs_repo()
    if not ok_repo:
        return False, f"Falha ao preparar repositório Git: {repo_msg}"

    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", (filename or "documento.bin")).strip("._") or "documento.bin"
    try:
        raw = base64.b64decode(b64_content, validate=True)
    except Exception:
        return False, "Arquivo inválido (base64)"

    if len(raw) > 12 * 1024 * 1024:
        return False, "Arquivo excede 12MB"

    with db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS last FROM document_versions WHERE project_slug=?", (slug,)).fetchone()
        next_version = int(row["last"]) + 1

    rel_path = Path("cards") / slug / f"v{next_version:04d}_{safe_name}"
    abs_path = DOCS_REPO_DIR / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(raw)

    checksum = hashlib.sha256(raw).hexdigest()

    ok_add, msg_add = run_git(["add", str(rel_path)])
    if not ok_add:
        return False, f"Falha git add: {msg_add}"

    commit_msg = f"docs({slug}): v{next_version} - {p['status']} - {safe_name}"
    ok_commit, msg_commit = run_git([
        "-c", "user.name=ProjectDashboard",
        "-c", "user.email=projectdashboard@local",
        "commit", "-m", commit_msg,
    ])
    if not ok_commit:
        return False, f"Falha git commit: {msg_commit}"

    ok_hash, commit_hash = run_git(["rev-parse", "HEAD"])
    if not ok_hash:
        return False, f"Falha ao obter hash do commit: {commit_hash}"

    with db() as conn:
        conn.execute(
            """
            INSERT INTO document_versions (project_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (slug, next_version, safe_name, mime_type or "application/octet-stream", p["status"], str(rel_path), commit_hash, checksum, actor, now_iso()),
        )
        conn.execute(
            "UPDATE projects SET document_status=?, document_name=?, document_mime=?, document_path=?, updated_at=? WHERE slug=?",
            (p["status"], safe_name, mime_type or "application/octet-stream", str(abs_path), now_iso(), slug),
        )

    return True, "ok"


def delete_project(slug: str) -> tuple[bool, str]:
    p = get_project(slug)
    if not p:
        return False, "Projeto não encontrado"
    with db() as conn:
        conn.execute("DELETE FROM projects WHERE slug=?", (slug,))
    return True, "ok"


def get_user_profile(username: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT username, role, email, phone, extension, work_area, notes FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def update_user_profile(username: str, payload: dict) -> tuple[bool, str]:
    email = str(payload.get("email") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    extension = str(payload.get("extension") or "").strip()
    work_area = str(payload.get("work_area") or "").strip()
    notes = str(payload.get("notes") or "").strip()

    if len(email) > 200 or len(phone) > 80 or len(extension) > 40 or len(work_area) > 120 or len(notes) > 4000:
        return False, "Campos do perfil excedem o limite permitido"

    with db() as conn:
        row = conn.execute("SELECT username FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return False, "Usuário não encontrado"
        conn.execute(
            "UPDATE users SET email=?, phone=?, extension=?, work_area=?, notes=? WHERE username=?",
            (email, phone, extension, work_area, notes, username),
        )

    return True, "ok"


def change_own_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    current_password = current_password or ""
    new_password = new_password or ""
    if len(new_password) < 4:
        return False, "Nova senha muito curta"

    with db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return False, "Usuário não encontrado"
        if not verify_password(current_password, row["password_hash"]):
            return False, "Senha atual inválida"
        conn.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_password(new_password), username))

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
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)
        if p in ["/", "/index.html"]: return self._serve(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if p == "/login.html": return self._serve(WEB_DIR / "login.html", "text/html; charset=utf-8")
        if p == "/signup.html": return self._serve(WEB_DIR / "signup.html", "text/html; charset=utf-8")
        if p == "/edit.html": return self._serve(WEB_DIR / "edit.html", "text/html; charset=utf-8")
        if p == "/admin-users.html": return self._serve(WEB_DIR / "admin-users.html", "text/html; charset=utf-8")
        if p == "/profile.html": return self._serve(WEB_DIR / "profile.html", "text/html; charset=utf-8")
        if p == "/settings.html":
            u = self._user()
            if not u or u.get("role") != "admin":
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            return self._serve(WEB_DIR / "settings.html", "text/html; charset=utf-8")
        if p in ["/app.js", "/edit.js", "/login.js", "/signup.js", "/admin-users.js", "/profile.js", "/settings.js", "/styles.css"]:
            ctype = "application/javascript; charset=utf-8" if p.endswith(".js") else "text/css; charset=utf-8"
            return self._serve(WEB_DIR / p.lstrip("/"), ctype)

        if p == "/api/me":
            u = self._user()
            return self._json(200 if u else 401, {"ok": bool(u), "user": {"username": u["username"], "role": u["role"]} if u else None})

        if p == "/api/me/profile":
            u = self._require_auth()
            if not u: return
            profile = get_user_profile(u["username"])
            if not profile:
                return self._json(404, {"ok": False, "error": "Usuário não encontrado"})
            return self._json(200, {"ok": True, "profile": profile})

        if p == "/api/projects":
            if not self._require_auth(): return
            return self._json(200, {"projects": list_projects(), "statuses": STATUSES, "priorities": PRIORITIES})

        if p.startswith("/api/projects/") and p.endswith("/document/versions"):
            if not self._require_auth(): return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj: return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            return self._json(200, {"ok": True, "versions": list_document_versions(slug)})

        if p.startswith("/api/projects/") and p.endswith("/review-notes"):
            if not self._require_auth(): return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj: return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            return self._json(200, {"ok": True, "notes": list_review_notes(slug)})

        if p.startswith("/api/projects/") and p.endswith("/document"):
            if not self._require_auth(): return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj: return self._json(404, {"ok": False, "error": "Projeto não encontrado"})

            version = None
            if "version" in qs and qs["version"]:
                try:
                    version = int(qs["version"][0])
                except Exception:
                    return self._json(400, {"ok": False, "error": "Parâmetro version inválido"})

            ver = get_document_version(slug, version)
            if not ver:
                return self._json(404, {"ok": False, "error": "Versão de documento não encontrada"})

            if version is None:
                doc_path = Path(proj.get("documentPath") or "")
            else:
                doc_path = DOCS_REPO_DIR / ver["file_rel_path"]

            if not doc_path.exists():
                return self._json(404, {"ok": False, "error": "Arquivo da versão não encontrado"})
            content = doc_path.read_bytes()

            self.send_response(200)
            self.send_header("Content-Type", ver.get("document_mime") or "application/octet-stream")
            self.send_header("Content-Disposition", f"inline; filename=\"{ver.get('document_name') or 'documento.bin'}\"")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

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

        if p == "/api/admin/settings":
            if not self._require_admin(): return
            return self._json(200, {"ok": True, "settings": get_admin_settings()})

        if p == "/api/admin/reports":
            if not self._require_admin(): return
            return self._json(200, {"ok": True, "reports": list_periodic_reports(), "statuses": STATUSES, "roles": ROLES, "priorities": ["TODOS", *PRIORITIES]})

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

        if p == "/api/me/change-password":
            user = self._require_auth()
            if not user: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = change_own_password(user["username"], body.get("currentPassword") or "", body.get("newPassword") or "")
            if done:
                audit(user["username"], "user.password.change", user["username"])
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p == "/api/projects":
            user = self._require_auth()
            if not user: return
            if not can_create_project(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para criar card"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = create_project(body, user["username"])
            if done:
                audit(user["username"], "project.create", body.get("name", ""), f"status={body.get('status','Backlog')}")
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/projects/") and p.endswith("/document"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj:
                return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            if not can_upload_document(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para anexar documento"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = save_project_document(
                slug,
                body.get("fileName") or "documento.bin",
                body.get("mimeType") or "application/octet-stream",
                body.get("contentBase64") or "",
                user["username"],
            )
            if done:
                audit(user["username"], "project.document.upload", slug, json.dumps({"file": body.get("fileName", "")}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/projects/") and p.endswith("/review-notes"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj:
                return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            if not can_add_review_note(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para adicionar nota de revisão"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = add_review_note(slug, body.get("note") or "", user["username"])
            if done:
                audit(user["username"], "project.review_note.create", slug, "note_added")
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p == "/api/admin/settings/test-smtp":
            admin = self._require_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            to_email = str(body.get("to") or "").strip()
            if not to_email:
                return self._json(400, {"ok": False, "error": "E-mail de destino é obrigatório"})
            done, msg = send_invite_email(
                to_email,
                "ProjectDashboard SMTP test",
                "Olá!\n\nEste é um teste de SMTP enviado pela área de Configurações do ProjectDashboard.\n",
            )
            if done:
                audit(admin["username"], "admin.settings.smtp_test", to_email)
                return self._json(200, {"ok": True})
            return self._json(400, {"ok": False, "error": msg})

        if p == "/api/admin/reports":
            admin = self._require_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = create_periodic_report(body, admin["username"])
            if done:
                audit(admin["username"], "report.periodic.create", body.get("name", ""))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/reports/") and p.endswith("/run"):
            admin = self._require_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 5:
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                rid = int(parts[3])
            except Exception:
                return self._json(400, {"ok": False, "error": "id inválido"})
            reports = [r for r in list_periodic_reports() if int(r.get("id") or 0) == rid]
            if not reports:
                return self._json(404, {"ok": False, "error": "Relatório não encontrado"})
            report = reports[0]
            subject, preview_text, recipients = compose_periodic_report_email(report)
            done, msg = run_periodic_report(report, admin["username"])
            if done:
                audit(admin["username"], "report.periodic.run.manual", str(rid), msg)
                return self._json(200, {"ok": True, "subject": subject, "previewText": preview_text, "recipients": len(recipients), "message": msg})
            return self._json(400, {"ok": False, "error": msg, "subject": subject, "previewText": preview_text, "recipients": len(recipients)})

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
            invite_url = f"/signup.html?token={token}"
            host = self.headers.get("Host") or f"127.0.0.1:{PORT}"
            full_invite_url = f"http://{host}{invite_url}"
            with db() as conn:
                conn.execute("INSERT INTO invites (token,role,created_by,expires_at,created_at) VALUES (?,?,?,?,?)",
                             (token, role, admin["username"], exp, now_iso()))

            settings = get_admin_settings()
            email_to = str(body.get("email") or "").strip()
            send_email = bool(body.get("sendEmail"))
            default_message = _setting(settings, "invite.default_message", "PDASH_INVITE_DEFAULT_MESSAGE", "")
            message_text = str(body.get("message") or "").strip() or default_message
            email_status = "not_requested"

            if send_email:
                if not email_to:
                    return self._json(400, {"ok": False, "error": "E-mail do convidado é obrigatório para envio"})
                if not message_text:
                    message_text = (
                        "Olá!\n\n"
                        "Você foi convidado(a) para acessar o ProjectDashboard.\n"
                        "Use o link abaixo para concluir seu cadastro:\n\n"
                        f"{full_invite_url}\n\n"
                        f"Este convite expira em: {exp}\n\n"
                        "Se você não esperava este convite, pode ignorar esta mensagem."
                    )
                else:
                    message_text = message_text.replace("{invite_link}", full_invite_url).replace("{expires_at}", exp)

                ok_email, msg_email = send_invite_email(email_to, "Convite para ProjectDashboard", message_text)
                if not ok_email:
                    return self._json(400, {"ok": False, "error": msg_email})
                email_status = "sent"

            audit(admin["username"], "invite.create", token, f"role={role} expires={exp} email={email_to or '-'} status={email_status}")
            return self._json(200, {
                "ok": True,
                "inviteUrl": invite_url,
                "fullInviteUrl": full_invite_url,
                "token": token,
                "expiresAt": exp,
                "emailStatus": email_status,
            })

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

        if p == "/api/me/profile":
            user = self._require_auth()
            if not user: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = update_user_profile(user["username"], body)
            if done:
                audit(user["username"], "user.profile.update", user["username"])
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p == "/api/admin/settings":
            admin = self._require_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = update_admin_settings(body, admin["username"])
            if done:
                audit(admin["username"], "admin.settings.update", "app_settings", json.dumps({k: ("***" if "pass" in k else v) for k, v in body.items()}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/projects/") and "/review-notes/" in p:
            user = self._require_auth()
            if not user: return
            parts = p.strip("/").split("/")
            # /api/projects/{slug}/review-notes/{id}
            if len(parts) != 5 or parts[0] != "api" or parts[1] != "projects" or parts[3] != "review-notes":
                return self._json(404, {"ok": False, "error": "not found"})
            slug = parts[2]
            try:
                note_id = int(parts[4])
            except Exception:
                return self._json(400, {"ok": False, "error": "invalid note id"})

            if not can_resolve_review_note(user["role"]):
                return self._json(403, {"ok": False, "error": "Apenas desenhista ou admin pode alterar status da revisão"})

            ok, body = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": body["error"]})
            if "resolved" not in body or not isinstance(body.get("resolved"), bool):
                return self._json(400, {"ok": False, "error": "resolved (boolean) is required"})

            done, msg = set_review_note_resolution(slug, note_id, user["username"], bool(body.get("resolved")))
            if done:
                audit(user["username"], "project.review_note.status", slug, json.dumps({"note_id": note_id, "resolved": bool(body.get("resolved"))}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/projects/"):
            user = self._require_auth()
            if not user: return
            if not can_edit_project(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para editar card"})
            slug = p.split("/")[3]
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})

            done, msg = patch_project(slug, body)
            if done:
                audit(user["username"], "project.update", slug, json.dumps(body, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/reports/"):
            admin = self._require_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 4:
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                rid = int(parts[3])
            except Exception:
                return self._json(400, {"ok": False, "error": "id inválido"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = update_periodic_report(rid, body, admin["username"])
            if done:
                audit(admin["username"], "report.periodic.update", str(rid))
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
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = get_project(slug)
            if not proj:
                return self._json(404, {"ok": False, "error": "Projeto não encontrado"})
            if not can_delete_project(user["role"], user["username"], proj):
                return self._json(403, {"ok": False, "error": "Sem permissão para apagar card"})
            done, msg = delete_project(slug)
            if done:
                audit(user["username"], "project.delete", slug)
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/reports/"):
            admin = self._require_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 4:
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                rid = int(parts[3])
            except Exception:
                return self._json(400, {"ok": False, "error": "id inválido"})
            done, msg = delete_periodic_report(rid)
            if done:
                audit(admin["username"], "report.periodic.delete", str(rid))
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
    ok_repo, repo_msg = ensure_docs_repo()
    if not ok_repo:
        print("[ProjectDashboard] Aviso: falha ao inicializar docs_repo:", repo_msg)
    server = HTTPServer((HOST, PORT), Handler)
    t = threading.Thread(target=report_scheduler_loop, daemon=True)
    t.start()
    print(f"ProjectDashboard online em http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
