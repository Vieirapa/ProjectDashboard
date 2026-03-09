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
import shutil
import threading
import time
from email.message import EmailMessage
from datetime import datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).parent
BASE_DIR = Path(os.getenv("PDASH_DOCUMENTS_DIR", str(APP_DIR / "documents")))
WEB_DIR = APP_DIR / "web"
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


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    v = str(value).strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", ""))
    except Exception:
        return None


def _project_age_fields(opened_at: str, status: str, released_at: str) -> tuple[str, int]:
    opened = _parse_iso_date(opened_at) or datetime.utcnow()
    if status == "Concluído" and released_at:
        released = _parse_iso_date(released_at) or datetime.utcnow()
        days = max(0, (released.date() - opened.date()).days)
        return "Dia até solução", days
    days = max(0, (datetime.utcnow().date() - opened.date()).days)
    return "Dias desde abertura", days


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower() or "documento"


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

# --- Legacy migrations: projects -> documents ---

def _table_exists(conn, name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def _column_exists(conn, table: str, col: str) -> bool:
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return False
    return col in cols


def migrate_projects_to_documents(conn: sqlite3.Connection) -> None:
    # Migrate legacy projects table into documents table (only if legacy schema exists)
    if _table_exists(conn, 'projects') and _column_exists(conn, 'projects', 'slug'):
        total_docs = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()[0]
        total_projects = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()[0]
        if total_projects and total_docs == 0:
            conn.execute(
                "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at) "
                "SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at FROM projects"
            )

    # Migrate deleted table (project_json -> document_json)
    if _table_exists(conn, 'deleted_projects') or _table_exists(conn, 'deleted_documents'):
        # create new table with correct column name
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deleted_documents_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL,
                name TEXT NOT NULL,
                deleted_at TEXT NOT NULL,
                deleted_by TEXT NOT NULL,
                trash_path TEXT NOT NULL,
                document_json TEXT NOT NULL,
                review_notes_json TEXT NOT NULL DEFAULT '[]',
                document_versions_json TEXT NOT NULL DEFAULT '[]'
            )
        """)

        # from deleted_projects
        if _table_exists(conn, 'deleted_projects'):
            conn.execute(
                "INSERT INTO deleted_documents_new (id, slug, name, deleted_at, deleted_by, trash_path, document_json, review_notes_json, document_versions_json) "
                "SELECT id, slug, name, deleted_at, deleted_by, trash_path, project_json, review_notes_json, document_versions_json FROM deleted_projects"
            )
        # from old deleted_documents (if it had project_json)
        if _table_exists(conn, 'deleted_documents'):
            cols = [r[1] for r in conn.execute("PRAGMA table_info(deleted_documents)").fetchall()]
            if 'project_json' in cols:
                conn.execute(
                    "INSERT INTO deleted_documents_new (id, slug, name, deleted_at, deleted_by, trash_path, document_json, review_notes_json, document_versions_json) "
                    "SELECT id, slug, name, deleted_at, deleted_by, trash_path, project_json, review_notes_json, document_versions_json FROM deleted_documents"
                )
            else:
                conn.execute(
                    "INSERT INTO deleted_documents_new (id, slug, name, deleted_at, deleted_by, trash_path, document_json, review_notes_json, document_versions_json) "
                    "SELECT id, slug, name, deleted_at, deleted_by, trash_path, document_json, review_notes_json, document_versions_json FROM deleted_documents"
                )

        # swap tables
        if _table_exists(conn, 'deleted_documents'):
            conn.execute("DROP TABLE deleted_documents")
        conn.execute("ALTER TABLE deleted_documents_new RENAME TO deleted_documents")

    # Migrate review_notes.project_slug -> document_slug
    if _table_exists(conn, 'review_notes') and _column_exists(conn, 'review_notes', 'project_slug') and not _column_exists(conn, 'review_notes', 'document_slug'):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_notes_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_slug TEXT NOT NULL,
                note TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_by TEXT NOT NULL DEFAULT '',
                resolved_at TEXT NOT NULL DEFAULT '',
                is_resolved INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT INTO review_notes_new (id, document_slug, note, created_by, created_at, resolved_by, resolved_at, is_resolved) "
            "SELECT id, project_slug, note, created_by, created_at, resolved_by, resolved_at, is_resolved FROM review_notes"
        )
        conn.execute("DROP TABLE review_notes")
        conn.execute("ALTER TABLE review_notes_new RENAME TO review_notes")

    # Migrate document_versions.project_slug -> document_slug
    if _table_exists(conn, 'document_versions') and _column_exists(conn, 'document_versions', 'project_slug') and not _column_exists(conn, 'document_versions', 'document_slug'):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_versions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_slug TEXT NOT NULL,
                version INTEGER NOT NULL,
                document_name TEXT NOT NULL,
                document_mime TEXT NOT NULL,
                document_status TEXT NOT NULL,
                file_rel_path TEXT NOT NULL,
                git_commit TEXT NOT NULL,
                checksum TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(document_slug, version)
            )
        """)
        conn.execute(
            "INSERT INTO document_versions_new (id, document_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at) "
            "SELECT id, project_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at FROM document_versions"
        )
        conn.execute("DROP TABLE document_versions")
        conn.execute("ALTER TABLE document_versions_new RENAME TO document_versions")




def can_create_document(role: str) -> bool:
    return role in {"admin", "member"}


def can_edit_document(role: str) -> bool:
    return role in {"admin", "member", "desenhista"}


def can_upload_document(role: str) -> bool:
    return role in {"admin", "member", "desenhista"}


def can_add_review_note(role: str) -> bool:
    return role in {"admin", "member", "desenhista", "revisor"}


def can_resolve_review_note(role: str) -> bool:
    return role in {"desenhista", "admin"}


def can_delete_document(role: str, user: str, document: dict) -> bool:
    if role == "admin":
        return True
    if role == "member":
        return (document.get("createdBy") or "").strip().lower() == user.strip().lower()
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
            CREATE TABLE IF NOT EXISTS documents (
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
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                start_date TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                allowed_roles TEXT NOT NULL DEFAULT 'member,desenhista,revisor,cliente',
                is_template INTEGER NOT NULL DEFAULT 0,
                template_source_project_id INTEGER
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
                document_slug TEXT NOT NULL,
                version INTEGER NOT NULL,
                document_name TEXT NOT NULL,
                document_mime TEXT NOT NULL,
                document_status TEXT NOT NULL,
                file_rel_path TEXT NOT NULL,
                git_commit TEXT NOT NULL,
                checksum TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(document_slug, version)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_slug TEXT NOT NULL,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deleted_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL,
                name TEXT NOT NULL,
                deleted_at TEXT NOT NULL,
                deleted_by TEXT NOT NULL,
                trash_path TEXT NOT NULL,
                document_json TEXT NOT NULL,
                review_notes_json TEXT NOT NULL DEFAULT '[]',
                document_versions_json TEXT NOT NULL DEFAULT '[]'
            )
        """)
        ensure_column(conn, "users", "role", "role TEXT NOT NULL DEFAULT 'member'")
        ensure_column(conn, "documents", "document_status", "document_status TEXT NOT NULL DEFAULT 'aguardando edição'")
        ensure_column(conn, "documents", "document_name", "document_name TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "documents", "document_mime", "document_mime TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "documents", "document_path", "document_path TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "documents", "created_by", "created_by TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "documents", "opened_at", "opened_at TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "documents", "released_at", "released_at TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "documents", "project_id", "project_id INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "projects", "allowed_roles", "allowed_roles TEXT NOT NULL DEFAULT 'member,desenhista,revisor,cliente'")
        ensure_column(conn, "projects", "is_template", "is_template INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "projects", "template_source_project_id", "template_source_project_id INTEGER")
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

        if conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO projects (project_name, start_date, notes) VALUES (?, ?, ?)",
                ("Projeto padrão", now_iso(), "Projeto inicial automático"),
            )

        migrate_projects_to_documents(conn)

        # Ensure admin user keeps admin role after upgrades/migrations
        conn.execute("UPDATE users SET role='admin' WHERE username='admin'")
        conn.execute("UPDATE documents SET status='Em revisão' WHERE status='Bloqueado'")
        conn.execute("UPDATE projects SET allowed_roles='member,desenhista,revisor,cliente' WHERE allowed_roles IS NULL OR TRIM(allowed_roles)=''")
        conn.execute("UPDATE projects SET is_template=0 WHERE is_template IS NULL")
        conn.execute("UPDATE documents SET project_id=1 WHERE project_id IS NULL OR project_id<=0")
        conn.execute("UPDATE documents SET document_status=status")
        conn.execute("UPDATE documents SET created_by=owner WHERE created_by='' AND owner<>''")
        conn.execute("UPDATE documents SET opened_at=updated_at WHERE opened_at='' AND updated_at<>''")
        conn.execute("UPDATE documents SET opened_at=? WHERE opened_at=''",(now_iso(),))
        conn.execute("UPDATE documents SET due_date='-' WHERE status='Concluído'")
        conn.execute("UPDATE documents SET released_at=updated_at WHERE status='Concluído' AND released_at='' AND updated_at<>''")

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


def migrate_existing_documents():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        for p in sorted(BASE_DIR.iterdir()):
            if not p.is_dir() or p.name in SKIP_DIRS:
                continue
            slug = p.name.lower()
            if conn.execute("SELECT id FROM documents WHERE slug=?", (slug,)).fetchone():
                continue

            data = {}
            meta = p / "document.json"
            if meta.exists():
                try:
                    data = json.loads(meta.read_text(encoding="utf-8"))
                except Exception:
                    data = {}

            migrated_status = ("Em revisão" if data.get("status") == "Bloqueado" else data.get("status"))
            migrated_status = migrated_status if migrated_status in STATUSES else "Backlog"
            migrated_updated = data.get("updatedAt") or now_iso()
            migrated_due = "-" if migrated_status == "Concluído" else (data.get("dueDate") or "")
            migrated_doc_status = (
                "Backlog" if data.get("documentStatus") == "aguardando edição"
                else "Em andamento" if data.get("documentStatus") == "editando"
                else "Em revisão" if data.get("documentStatus") == "em revisão"
                else "Concluído" if data.get("documentStatus") == "release"
                else migrated_status
            )

            conn.execute(
                """
                INSERT INTO documents (slug, name, status, priority, owner, due_date, description, path, updated_at, document_status, document_name, document_mime, document_path, created_by, opened_at, released_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    data.get("name") or p.name,
                    migrated_status,
                    data.get("priority") if data.get("priority") in PRIORITIES else "Média",
                    data.get("owner") or "",
                    migrated_due,
                    data.get("description") or infer_description(p),
                    str(p),
                    migrated_updated,
                    migrated_doc_status,
                    data.get("documentName") or "",
                    data.get("documentMime") or "",
                    data.get("documentPath") or "",
                    data.get("createdBy") or data.get("owner") or "",
                    data.get("openedAt") or migrated_updated,
                    data.get("releasedAt") or (migrated_updated if migrated_status == "Concluído" else ""),
                ),
            )


def list_documents(project_id: int | None = None) -> list[dict]:
    with db() as conn:
        if project_id is None:
            rows = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents ORDER BY name").fetchall()
        else:
            rows = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents WHERE project_id=? ORDER BY name", (project_id,)).fetchall()
    return [{
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": ("-" if r["status"] == "Concluído" else r["due_date"]), "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"],
        "documentStatus": ("aguardando edição" if r["status"] == "Backlog" else "em andamento" if r["status"] == "Em andamento" else "em revisão" if r["status"] == "Em revisão" else "release"), "documentName": r["document_name"],
        "documentMime": r["document_mime"], "hasDocument": bool(r["document_path"]),
        "createdBy": r["created_by"], "projectId": int(r["project_id"] or 1),
        "openedAt": r["opened_at"], "releasedAt": r["released_at"],
        "ageLabel": _project_age_fields(r["opened_at"], r["status"], r["released_at"])[0],
        "ageDays": _project_age_fields(r["opened_at"], r["status"], r["released_at"])[1],
    } for r in rows]


def get_document(slug: str, project_id: int | None = None) -> dict | None:
    with db() as conn:
        if project_id is None:
            r = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents WHERE slug=?", (slug,)).fetchone()
        else:
            r = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents WHERE slug=? AND project_id=?", (slug, project_id)).fetchone()
    if not r:
        return None
    age_label, age_days = _project_age_fields(r["opened_at"], r["status"], r["released_at"])
    return {
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": ("-" if r["status"] == "Concluído" else r["due_date"]), "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"],
        "documentStatus": ("aguardando edição" if r["status"] == "Backlog" else "em andamento" if r["status"] == "Em andamento" else "em revisão" if r["status"] == "Em revisão" else "release"), "documentName": r["document_name"],
        "documentMime": r["document_mime"], "documentPath": r["document_path"],
        "hasDocument": bool(r["document_path"]), "createdBy": r["created_by"], "projectId": int(r["project_id"] or 1),
        "openedAt": r["opened_at"], "releasedAt": r["released_at"],
        "ageLabel": age_label, "ageDays": age_days,
    }


def list_audit_logs(limit: int = 200) -> list[dict]:
    limit = max(1, min(limit, 1000))
    with db() as conn:
        rows = conn.execute(
            "SELECT actor, action, target, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_usernames() -> list[str]:
    with db() as conn:
        rows = conn.execute("SELECT username FROM users ORDER BY username").fetchall()
    return [r["username"] for r in rows]


def _normalize_allowed_roles(raw: str | list | None) -> str:
    if isinstance(raw, list):
        vals = [str(x or '').strip().lower() for x in raw]
    else:
        vals = [x.strip().lower() for x in str(raw or '').split(',')]
    allowed = [r for r in vals if r in ROLES and r != 'admin']
    # remove duplicados preservando ordem
    out: list[str] = []
    for r in allowed:
        if r not in out:
            out.append(r)
    return ','.join(out) if out else 'member,desenhista,revisor,cliente'


def parse_allowed_roles(raw: str | None) -> list[str]:
    return [r for r in _normalize_allowed_roles(raw).split(',') if r]


def project_role_allowed(project_row: dict | None, role: str) -> bool:
    normalized_role = (role or '').strip().lower()
    if normalized_role == 'admin':
        return True
    if not project_row:
        return False
    # Template projects are restricted to admin only.
    if bool(project_row.get('is_template')):
        return False
    allowed = parse_allowed_roles(project_row.get('allowed_roles'))
    return normalized_role in allowed


def _to_bool_int(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) != 0 else 0
    s = str(value or '').strip().lower()
    return 1 if s in {'1', 'true', 'yes', 'on'} else 0


def list_projects_registry() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT project_id, project_name, start_date, notes, allowed_roles, is_template, template_source_project_id FROM projects ORDER BY project_id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['allowed_roles'] = _normalize_allowed_roles(d.get('allowed_roles'))
        d['is_template'] = bool(int(d.get('is_template') or 0))
        out.append(d)
    return out


def create_project_registry(payload: dict) -> tuple[bool, str, int | None]:
    name = str(payload.get("project_name") or "").strip()
    start_date = str(payload.get("start_date") or "").strip()
    notes = str(payload.get("notes") or "").strip()
    allowed_roles = _normalize_allowed_roles(payload.get("allowed_roles") or payload.get("allowedRoles"))
    is_template = _to_bool_int(payload.get("is_template") if "is_template" in payload else payload.get("isTemplate"))
    if not name:
        return False, "Nome do projeto é obrigatório", None
    if not start_date:
        start_date = now_iso()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (project_name, start_date, notes, allowed_roles, is_template) VALUES (?, ?, ?, ?, ?)",
            (name, start_date, notes, allowed_roles, is_template),
        )
        new_id = int(cur.lastrowid or 0) or None
    return True, "ok", new_id


def update_project_registry(project_id: int, payload: dict) -> tuple[bool, str]:
    fields = []
    vals: list = []
    if "project_name" in payload:
        name = str(payload.get("project_name") or "").strip()
        if not name:
            return False, "Nome do projeto é obrigatório"
        fields.append("project_name=?")
        vals.append(name)
    if "start_date" in payload:
        fields.append("start_date=?")
        vals.append(str(payload.get("start_date") or "").strip())
    if "notes" in payload:
        fields.append("notes=?")
        vals.append(str(payload.get("notes") or "").strip())
    if "allowed_roles" in payload or "allowedRoles" in payload:
        fields.append("allowed_roles=?")
        vals.append(_normalize_allowed_roles(payload.get("allowed_roles") or payload.get("allowedRoles")))
    if "is_template" in payload or "isTemplate" in payload:
        fields.append("is_template=?")
        vals.append(_to_bool_int(payload.get("is_template") if "is_template" in payload else payload.get("isTemplate")))
    if not fields:
        return False, "Nada para atualizar"
    vals.append(project_id)
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if not exists:
            return False, "Projeto não encontrado"
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE project_id=?", tuple(vals))
    return True, "ok"


def delete_project_registry(project_id: int) -> tuple[bool, str, int]:
    deleted_cards = 0
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if not exists:
            return False, "Projeto não encontrado", 0

        linked_docs = conn.execute(
            "SELECT slug, path, document_path FROM documents WHERE project_id=?",
            (project_id,),
        ).fetchall()

        # Hard-delete all project cards (and related metadata) before deleting project.
        for row in linked_docs:
            d = dict(row)
            slug = str(d.get("slug") or "").strip()
            if not slug:
                continue
            conn.execute("DELETE FROM review_notes WHERE document_slug=?", (slug,))
            conn.execute("DELETE FROM document_versions WHERE document_slug=?", (slug,))

            for candidate in [d.get("path"), d.get("document_path")]:
                p = str(candidate or "").strip()
                if not p:
                    continue
                try:
                    rp = Path(p)
                    if rp.exists():
                        if rp.is_file():
                            rp.unlink(missing_ok=True)
                        elif rp.is_dir():
                            shutil.rmtree(rp, ignore_errors=True)
                except Exception:
                    pass

            conn.execute("DELETE FROM documents WHERE slug=?", (slug,))
            deleted_cards += 1

        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))

    return True, "ok", deleted_cards


def _unique_slug(conn: sqlite3.Connection, base_name: str) -> str:
    base = slugify(base_name)
    candidate = base
    i = 2
    while conn.execute("SELECT 1 FROM documents WHERE slug=?", (candidate,)).fetchone():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


def clone_project_from_template(template_project_id: int, payload: dict, actor: str) -> tuple[bool, str, int | None]:
    new_name = str(payload.get("project_name") or payload.get("projectName") or "").strip()
    if not new_name:
        return False, "Nome do novo projeto é obrigatório", None

    requested_start = str(payload.get("start_date") or payload.get("startDate") or "").strip()
    new_start_date = requested_start or now_iso()

    with db() as conn:
        template = conn.execute(
            "SELECT project_id, project_name, notes, allowed_roles, is_template FROM projects WHERE project_id=?",
            (template_project_id,),
        ).fetchone()
        if not template:
            return False, "Template não encontrado", None
        if int(template["is_template"] or 0) != 1:
            return False, "Projeto selecionado não é template", None

        template_d = dict(template)
        default_notes = f"Criado a partir do template #{template_d['project_id']} · {template_d['project_name']}"
        new_notes = str(payload.get("notes") or "").strip() or default_notes
        allowed_roles = _normalize_allowed_roles(template_d.get("allowed_roles"))

        cur = conn.execute(
            "INSERT INTO projects (project_name, start_date, notes, allowed_roles, is_template, template_source_project_id) VALUES (?, ?, ?, ?, 0, ?)",
            (new_name, new_start_date, new_notes, allowed_roles, int(template_d["project_id"])),
        )
        new_project_id = int(cur.lastrowid or 0)
        if not new_project_id:
            return False, "Falha ao criar projeto a partir do template", None

        template_docs = conn.execute(
            "SELECT name, status, priority, description FROM documents WHERE project_id=? ORDER BY id",
            (template_project_id,),
        ).fetchall()

        now = now_iso()
        for row in template_docs:
            d = dict(row)
            name = str(d.get("name") or "").strip() or "Documento"
            doc_slug = _unique_slug(conn, name)
            doc_path = str(BASE_DIR / doc_slug)
            (BASE_DIR / doc_slug).mkdir(parents=True, exist_ok=True)
            conn.execute(
                "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    doc_slug,
                    name,
                    str(d.get("status") or "Backlog"),
                    str(d.get("priority") or "Média"),
                    "",
                    "",
                    str(d.get("description") or "").strip(),
                    doc_path,
                    now,
                    "aguardando edição",
                    "",
                    "",
                    "",
                    actor,
                    now,
                    "",
                    new_project_id,
                ),
            )

    return True, "ok", new_project_id


def is_valid_owner(owner: str) -> bool:
    owner = (owner or "").strip()
    if not owner:
        return True
    with db() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE username=?", (owner,)).fetchone()
    return bool(row)


def sync_document_meta(document: dict):
    p = Path(document.get("path") or "")
    if not p.exists():
        p = BASE_DIR / (document.get("slug") or "documento")
        p.mkdir(parents=True, exist_ok=True)
        document["path"] = str(p)
        with db() as conn:
            conn.execute("UPDATE documents SET path=? WHERE slug=?", (document["path"], document.get("slug", "")))
    (p / "document.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_document(payload: dict, actor: str) -> tuple[bool, str, str | None]:
    name = (payload.get("name") or "").strip()
    if not name:
        return False, "Nome é obrigatório", None
    try:
        project_id = int(payload.get("project_id") or payload.get("projectId") or 1)
    except Exception:
        project_id = 1
    with db() as conn:
        exists_project = conn.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone()
    if not exists_project:
        return False, "Projeto inválido", None

    slug = slugify(name)
    proj_dir = BASE_DIR / slug
    if proj_dir.exists():
        return False, "Documento já existe", None

    status = payload.get("status") if payload.get("status") in STATUSES else "Backlog"
    opened_at = now_iso()
    owner = (payload.get("owner") or "").strip()
    if not is_valid_owner(owner):
        return False, "Responsável inválido (usuário não encontrado)", None

    document = {
        "slug": slug,
        "name": name,
        "status": status,
        "priority": payload.get("priority") if payload.get("priority") in PRIORITIES else "Média",
        "owner": owner,
        "dueDate": ("-" if status == "Concluído" else ((payload.get("dueDate") or "").strip() or default_due_date_iso())),
        "description": (payload.get("description") or "Sem descrição").strip(),
        "path": str(proj_dir),
        "updatedAt": now_iso(),
        "documentName": "",
        "documentMime": "",
        "documentPath": "",
        "createdBy": actor,
        "openedAt": opened_at,
        "releasedAt": opened_at if status == "Concluído" else "",
        "projectId": project_id,
    }

    proj_dir.mkdir(parents=True, exist_ok=False)
    (proj_dir / "README.md").write_text(f"# Documento: {document['name']}\n\n{document['description']}\n", encoding="utf-8")
    (proj_dir / "TASKS.md").write_text("# TASKS\n\n## Done\n\n- [ ] Inicializar documento\n\n## Next\n\n- [ ] Definir roadmap\n", encoding="utf-8")

    with db() as conn:
        conn.execute(
            "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (document["slug"], document["name"], document["status"], document["priority"], document["owner"], document["dueDate"], document["description"], document["path"], document["updatedAt"], document["status"], document["documentName"], document["documentMime"], document["documentPath"], document["createdBy"], document["openedAt"], document["releasedAt"], int(document.get("projectId") or 1)),
        )
    sync_document_meta(document)
    return True, "ok", slug


def patch_document(slug: str, payload: dict, project_id: int | None = None) -> tuple[bool, str]:
    p = get_document(slug, project_id)
    if not p:
        return False, "Documento não encontrado"
    old_status = p.get("status")
    if "name" in payload and str(payload["name"]).strip():
        p["name"] = str(payload["name"]).strip()
    if "status" in payload and payload["status"] in STATUSES:
        p["status"] = payload["status"]
    if "priority" in payload and payload["priority"] in PRIORITIES:
        p["priority"] = payload["priority"]
    if "owner" in payload:
        next_owner = str(payload["owner"]).strip()
        if not is_valid_owner(next_owner):
            return False, "Responsável inválido (usuário não encontrado)"
        p["owner"] = next_owner

    status_changed = p.get("status") != old_status
    if "dueDate" in payload:
        p["dueDate"] = str(payload["dueDate"]).strip()

    if p.get("status") == "Concluído":
        p["dueDate"] = "-"
        if status_changed:
            p["releasedAt"] = now_iso()
    else:
        if status_changed and "dueDate" not in payload:
            p["dueDate"] = default_due_date_iso()

    if "description" in payload:
        p["description"] = str(payload["description"]).strip() or "Sem descrição"
    p["updatedAt"] = now_iso()

    with db() as conn:
        conn.execute("UPDATE documents SET name=?,status=?,priority=?,owner=?,due_date=?,description=?,document_status=?,updated_at=?,released_at=? WHERE slug=?",
                     (p["name"], p["status"], p["priority"], p["owner"], p["dueDate"], p["description"], p["status"], p["updatedAt"], p.get("releasedAt") or "", slug))
    sync_document_meta(p)
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
        "invite.default_message", "workflow.default_due_days",
        "backup.enabled", "backup.path", "backup.weekdays", "backup.run_time",
        "system.git_repo", "system.git_branch",
        "deleted.retention_days",
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

    if "backup.enabled" in incoming:
        incoming["backup.enabled"] = "true" if incoming["backup.enabled"].strip().lower() in {"1", "true", "yes", "on"} else "false"

    if "backup.path" in incoming:
        p = Path(incoming["backup.path"]).expanduser()
        if not p.is_absolute():
            return False, "backup.path deve ser caminho absoluto"
        incoming["backup.path"] = str(p)

    if "backup.weekdays" in incoming:
        try:
            raw = json.loads(incoming["backup.weekdays"])
            if not isinstance(raw, list):
                return False, "backup.weekdays inválido"
            clean_days = sorted({str(int(x)) for x in raw if str(x).strip() != ""})
            for d in clean_days:
                if d not in {"0", "1", "2", "3", "4", "5", "6"}:
                    return False, "backup.weekdays inválido"
            incoming["backup.weekdays"] = json.dumps(clean_days, ensure_ascii=False)
        except Exception:
            return False, "backup.weekdays inválido"

    if "backup.run_time" in incoming:
        rt = incoming["backup.run_time"].strip()
        if not re.match(r"^\d{2}:\d{2}$", rt):
            return False, "backup.run_time inválido"
        hh, mm = rt.split(":")
        if int(hh) > 23 or int(mm) > 59:
            return False, "backup.run_time inválido"
        incoming["backup.run_time"] = rt

    if "system.git_repo" in incoming and incoming["system.git_repo"]:
        repo = incoming["system.git_repo"].strip()
        if not (repo.startswith("https://") or repo.startswith("git@") or repo.startswith("ssh://")):
            return False, "system.git_repo inválido"
        incoming["system.git_repo"] = repo

    if "system.git_branch" in incoming and incoming["system.git_branch"]:
        branch = incoming["system.git_branch"].strip()
        if not re.match(r"^[A-Za-z0-9._/-]+$", branch):
            return False, "system.git_branch inválido"
        incoming["system.git_branch"] = branch

    if "deleted.retention_days" in incoming:
        try:
            days = int(incoming["deleted.retention_days"])
            if days < 1 or days > 3650:
                return False, "deleted.retention_days inválido"
            incoming["deleted.retention_days"] = str(days)
        except Exception:
            return False, "deleted.retention_days inválido"

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
        rows = conn.execute("SELECT slug, name, status, priority, owner, due_date, updated_at FROM documents ORDER BY priority DESC, name").fetchall()
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
    lines.append(f"- Total documentos: **{len(items)}**")
    lines.append("")
    lines.append("### Documentos")
    if not items:
        lines.append("_Nenhum documento atendeu aos critérios selecionados._")
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


def _backup_config(settings: dict) -> dict:
    raw_days = _setting(settings, "backup.weekdays", "PDASH_BACKUP_WEEKDAYS", "[]")
    try:
        days = json.loads(raw_days)
        if not isinstance(days, list):
            days = []
    except Exception:
        days = []
    clean_days = [str(d) for d in days if str(d) in {"0", "1", "2", "3", "4", "5", "6"}]
    return {
        "enabled": _setting(settings, "backup.enabled", "PDASH_BACKUP_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        "path": _setting(settings, "backup.path", "PDASH_BACKUP_PATH", str(DATA_DIR / "backups")),
        "weekdays": clean_days,
        "run_time": _setting(settings, "backup.run_time", "PDASH_BACKUP_RUN_TIME", "03:00"),
    }


def _backup_permission_hint(path: Path) -> str:
    p = str(path)
    return (
        f"Permissão negada em '{p}'. "
        "Sugestões: (1) use um caminho gravável pelo serviço (ex.: ./data/backups), "
        f"ou (2) ajuste permissões no Ubuntu: sudo mkdir -p {p} && sudo chown -R <usuario_servico>:<grupo_servico> {p}"
    )


def run_system_backup(actor: str = "system") -> tuple[bool, str]:
    settings = get_admin_settings()
    cfg = _backup_config(settings)
    primary_out_dir = Path(cfg["path"]).expanduser()
    fallback_out_dir = DATA_DIR / "backups"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    db_src = DATA_DIR / "projectdashboard.db"
    docs_src = DATA_DIR / "docs_repo"

    def _write_backup(target_dir: Path) -> list[str]:
        target_dir.mkdir(parents=True, exist_ok=True)
        copied_local: list[str] = []
        if db_src.exists():
            db_out = target_dir / f"projectdashboard-db-{stamp}.sqlite3"
            db_out.write_bytes(db_src.read_bytes())
            copied_local.append(db_out.name)
        if docs_src.exists() and docs_src.is_dir():
            archive = target_dir / f"projectdashboard-docs-{stamp}.tar.gz"
            subprocess.run(["tar", "-czf", str(archive), "-C", str(DATA_DIR), "docs_repo"], check=True)
            copied_local.append(archive.name)
        return copied_local

    used_dir = primary_out_dir
    try:
        copied = _write_backup(primary_out_dir)
    except PermissionError:
        try:
            copied = _write_backup(fallback_out_dir)
            used_dir = fallback_out_dir
            hint = _backup_permission_hint(primary_out_dir)
            msg = (
                f"backup salvo em {used_dir} ({', '.join(copied)}) | "
                f"Obs: caminho configurado sem permissão. {hint}"
            )
            audit(actor, "system.backup.run", str(used_dir), msg)
            return True, msg
        except Exception as e2:
            return False, f"falha no backup. {_backup_permission_hint(primary_out_dir)} | detalhe: {e2}"
    except Exception as e:
        return False, f"falha no backup: {e}"

    if not copied:
        return False, "nenhum artefato encontrado para backup"

    audit(actor, "system.backup.run", str(used_dir), ", ".join(copied))
    return True, f"backup salvo em {used_dir} ({', '.join(copied)})"

def run_system_diagnostics() -> dict:
    settings = get_admin_settings()
    repo_url = _setting(settings, "system.git_repo", "PDASH_GIT_REPO", "https://github.com/Vieirapa/ProjectDashboard.git")
    repo_branch = _setting(settings, "system.git_branch", "PDASH_GIT_BRANCH", "main")

    diagnostics = {
        "timestamp": now_iso(),
        "checks": [],
        "version": {
            "local": "unknown",
            "remote": "unknown",
            "repo": repo_url,
            "branch": repo_branch,
            "updateAvailable": False,
        }
    }

    def add_check(name: str, ok: bool, detail: str):
        diagnostics["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    add_check("Banco de dados", DB_PATH.exists(), str(DB_PATH))
    add_check("Pasta de dados", DATA_DIR.exists(), str(DATA_DIR))
    add_check("Pasta de documentos", BASE_DIR.exists(), str(BASE_DIR))

    if (APP_DIR / ".git").exists():
        try:
            local = subprocess.check_output(["git", "-C", str(APP_DIR), "rev-parse", "HEAD"], text=True, timeout=6).strip()
            diagnostics["version"]["local"] = local
            add_check("Git local", True, local[:12])
        except Exception as e:
            add_check("Git local", False, str(e))
    else:
        add_check("Git local", False, "instalação sem .git (normal em deploy via rsync)")

    try:
        remote_line = subprocess.check_output(["git", "ls-remote", repo_url, f"refs/heads/{repo_branch}"], text=True, timeout=10).strip()
        remote = remote_line.split()[0] if remote_line else ""
        if remote:
            diagnostics["version"]["remote"] = remote
            add_check("GitHub remoto", True, remote[:12])
        else:
            add_check("GitHub remoto", False, "branch não encontrada")
    except Exception as e:
        add_check("GitHub remoto", False, str(e))

    local = diagnostics["version"]["local"]
    remote = diagnostics["version"]["remote"]
    diagnostics["version"]["updateAvailable"] = bool(local and remote and local != "unknown" and remote != "unknown" and local != remote)

    return diagnostics


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

            backup_cfg = _backup_config(get_admin_settings())
            if backup_cfg["enabled"] and weekday in backup_cfg["weekdays"] and backup_cfg["run_time"] == now.strftime("%H:%M"):
                backup_key = f"backup:{key}"
                with db() as conn:
                    lock = conn.execute("SELECT value FROM app_settings WHERE key='backup.last_run_key'").fetchone()
                    last_key = (lock["value"] if lock else "")
                    if last_key != backup_key:
                        ok, msg = run_system_backup("system")
                        conn.execute(
                            "INSERT INTO app_settings (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                            ("backup.last_run_key", backup_key, "system", now_iso()),
                        )
                        audit("system", "system.backup.schedule", backup_cfg["path"], f"ok={ok} {msg}")

            purge_key = f"purge:{now.strftime('%Y-%m-%d %H')}"
            with db() as conn:
                lock = conn.execute("SELECT value FROM app_settings WHERE key='deleted.last_purge_key'").fetchone()
                last_purge = (lock["value"] if lock else "")
                if last_purge != purge_key:
                    purged, retention = purge_expired_deleted_documents("system")
                    conn.execute(
                        "INSERT INTO app_settings (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                        ("deleted.last_purge_key", purge_key, "system", now_iso()),
                    )
                    if purged:
                        audit("system", "document.deleted.purge.hourly", str(purged), f"retention_days={retention}")
        except Exception as e:
            print("[ProjectDashboard] report/backup scheduler error:", e)
        time.sleep(30)


def list_document_versions(slug: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT version, document_name, document_mime, document_status, git_commit, checksum, created_by, created_at
            FROM document_versions
            WHERE document_slug=?
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
            WHERE document_slug=?
            ORDER BY id DESC
            """,
            (slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_review_note(slug: str, note: str, actor: str) -> tuple[bool, str]:
    proj = get_document(slug)
    if not proj:
        return False, "Documento não encontrado"
    if (proj.get("status") or "").strip().lower() != "em revisão":
        return False, "Notas de revisão só podem ser adicionadas quando o documento estiver em 'em revisão'"
    clean_note = (note or "").strip()
    if not clean_note:
        return False, "Nota não pode estar vazia"
    if len(clean_note) > 4000:
        return False, "Nota muito longa (máximo 4000 caracteres)"
    with db() as conn:
        conn.execute(
            "INSERT INTO review_notes (document_slug, note, created_by, created_at) VALUES (?, ?, ?, ?)",
            (slug, clean_note, actor, now_iso()),
        )
    return True, "ok"


def set_review_note_resolution(slug: str, note_id: int, actor: str, resolved: bool) -> tuple[bool, str]:
    proj = get_document(slug)
    if not proj:
        return False, "Documento não encontrado"
    if (proj.get("status") or "").strip().lower() != "em revisão":
        return False, "Notas só podem ser alteradas quando o documento estiver em 'em revisão'"

    with db() as conn:
        row = conn.execute(
            "SELECT id FROM review_notes WHERE id=? AND document_slug=?",
            (note_id, slug),
        ).fetchone()
        if not row:
            return False, "Nota não encontrada"

        if resolved:
            conn.execute(
                "UPDATE review_notes SET is_resolved=1, resolved_by=?, resolved_at=? WHERE id=? AND document_slug=?",
                (actor, now_iso(), note_id, slug),
            )
        else:
            conn.execute(
                "UPDATE review_notes SET is_resolved=0, resolved_by='', resolved_at='' WHERE id=? AND document_slug=?",
                (note_id, slug),
            )
    return True, "ok"


def get_document_version(slug: str, version: int | None = None) -> dict | None:
    with db() as conn:
        if version is None:
            row = conn.execute(
                "SELECT * FROM document_versions WHERE document_slug=? ORDER BY version DESC LIMIT 1",
                (slug,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM document_versions WHERE document_slug=? AND version=?",
                (slug, version),
            ).fetchone()
    return dict(row) if row else None


def save_document_file(slug: str, filename: str, mime_type: str, b64_content: str, actor: str) -> tuple[bool, str]:
    p = get_document(slug)
    if not p:
        return False, "Documento não encontrado"

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
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS last FROM document_versions WHERE document_slug=?", (slug,)).fetchone()
        next_version = int(row["last"]) + 1

    rel_path = Path("documents") / slug / f"v{next_version:04d}_{safe_name}"
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
            INSERT INTO document_versions (document_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (slug, next_version, safe_name, mime_type or "application/octet-stream", p["status"], str(rel_path), commit_hash, checksum, actor, now_iso()),
        )
        conn.execute(
            "UPDATE documents SET document_status=?, document_name=?, document_mime=?, document_path=?, updated_at=? WHERE slug=?",
            (p["status"], safe_name, mime_type or "application/octet-stream", str(abs_path), now_iso(), slug),
        )

    return True, "ok"


def list_deleted_documents() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, slug, name, deleted_at, deleted_by, trash_path FROM deleted_documents ORDER BY deleted_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def _purge_deleted_document_record(record: sqlite3.Row | dict) -> tuple[bool, str]:
    rec = dict(record)
    trash_path = Path(rec.get("trash_path") or "")
    if trash_path.exists() and trash_path.is_dir():
        shutil.rmtree(trash_path, ignore_errors=True)

    try:
        versions = json.loads(rec.get("document_versions_json") or "[]")
    except Exception:
        versions = []
    for v in versions:
        rel = str(v.get("file_rel_path") or "").strip()
        if rel:
            try:
                p = DOCS_REPO_DIR / rel
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    with db() as conn:
        conn.execute("DELETE FROM deleted_documents WHERE id=?", (int(rec["id"]),))
    return True, "ok"


def purge_expired_deleted_documents(actor: str = "system") -> tuple[int, int]:
    settings = get_admin_settings()
    try:
        retention_days = int(_setting(settings, "deleted.retention_days", "PDASH_DELETED_RETENTION_DAYS", "30"))
    except Exception:
        retention_days = 30
    retention_days = max(1, min(retention_days, 3650))
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    purged = 0
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM deleted_documents WHERE deleted_at < ? ORDER BY deleted_at ASC",
            (cutoff.replace(microsecond=0).isoformat() + "Z",),
        ).fetchall()
    for r in rows:
        ok, _ = _purge_deleted_document_record(r)
        if ok:
            purged += 1
    if purged:
        audit(actor, "document.deleted.purge", "deleted_documents", f"purged={purged} retention_days={retention_days}")
    return purged, retention_days


def restore_deleted_document(deleted_id: int, actor: str) -> tuple[bool, str]:
    with db() as conn:
        row = conn.execute("SELECT * FROM deleted_documents WHERE id=?", (deleted_id,)).fetchone()
    if not row:
        return False, "Registro de documento apagado não encontrado"

    rec = dict(row)
    try:
        document = json.loads(rec.get("document_json") or "{}")
        notes = json.loads(rec.get("review_notes_json") or "[]")
        versions = json.loads(rec.get("document_versions_json") or "[]")
    except Exception:
        return False, "Dados de restauração inválidos"

    slug = str(document.get("slug") or rec.get("slug") or "").strip()
    if not slug:
        return False, "Slug inválido para restauração"

    with db() as conn:
        exists = conn.execute("SELECT 1 FROM documents WHERE slug=?", (slug,)).fetchone()
        if exists:
            return False, "Já existe um documento ativo com este slug"

    trash_path = Path(rec.get("trash_path") or "")
    target_path = BASE_DIR / slug
    if target_path.exists():
        return False, "Já existe pasta de documento com este slug"

    if trash_path.exists() and trash_path.is_dir():
        try:
            shutil.move(str(trash_path), str(target_path))
        except Exception as e:
            return False, f"Falha ao restaurar pasta do documento: {e}"

    document["path"] = str(target_path)

    with db() as conn:
        conn.execute(
            "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                document.get("slug", slug), document.get("name", rec.get("name", slug)), document.get("status", "Backlog"),
                document.get("priority", "Média"), document.get("owner", ""), document.get("dueDate", ""),
                document.get("description", "Sem descrição"), document.get("path", str(target_path)), document.get("updatedAt", now_iso()),
                document.get("documentStatus", "aguardando edição"), document.get("documentName", ""), document.get("documentMime", ""),
                document.get("documentPath", ""), document.get("createdBy", actor), document.get("openedAt", now_iso()), document.get("releasedAt", ""),
            ),
        )
        for n in notes:
            conn.execute(
                "INSERT INTO review_notes (document_slug, note, created_by, created_at, resolved_by, resolved_at, is_resolved) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (slug, n.get("note", ""), n.get("created_by", ""), n.get("created_at", now_iso()), n.get("resolved_by", ""), n.get("resolved_at", ""), int(n.get("is_resolved") or 0)),
            )
        for v in versions:
            conn.execute(
                "INSERT OR IGNORE INTO document_versions (document_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (slug, int(v.get("version") or 1), v.get("document_name", ""), v.get("document_mime", "application/octet-stream"), v.get("document_status", ""), v.get("file_rel_path", ""), v.get("git_commit", ""), v.get("checksum", ""), v.get("created_by", ""), v.get("created_at", now_iso())),
            )
        conn.execute("DELETE FROM deleted_documents WHERE id=?", (deleted_id,))

    audit(actor, "document.restore", slug, f"deleted_id={deleted_id}")
    return True, "ok"


def delete_deleted_document_permanently(deleted_id: int, actor: str) -> tuple[bool, str]:
    with db() as conn:
        row = conn.execute("SELECT * FROM deleted_documents WHERE id=?", (deleted_id,)).fetchone()
    if not row:
        return False, "Registro de documento apagado não encontrado"
    ok, msg = _purge_deleted_document_record(row)
    if ok:
        audit(actor, "document.deleted.purge.manual", str(deleted_id))
    return ok, msg


def delete_document(slug: str, actor: str) -> tuple[bool, str]:
    p = get_document(slug)
    if not p:
        return False, "Documento não encontrado"

    proj_path = Path(p.get("path") or "")
    trash_root = DATA_DIR / "deleted_documents"
    trash_root.mkdir(parents=True, exist_ok=True)
    target = trash_root / f"{slug}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    if proj_path.exists():
        try:
            resolved_proj = proj_path.resolve()
            resolved_base = BASE_DIR.resolve()
            if str(resolved_proj).startswith(str(resolved_base) + os.sep):
                shutil.move(str(resolved_proj), str(target))
        except Exception as e:
            return False, f"Falha ao remover pasta do documento: {e}"

    with db() as conn:
        notes = conn.execute("SELECT * FROM review_notes WHERE document_slug=?", (slug,)).fetchall()
        versions = conn.execute("SELECT * FROM document_versions WHERE document_slug=?", (slug,)).fetchall()

        conn.execute(
            "INSERT INTO deleted_documents (slug, name, deleted_at, deleted_by, trash_path, document_json, review_notes_json, document_versions_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                p.get("slug", slug), p.get("name", slug), now_iso(), actor, str(target),
                json.dumps(p, ensure_ascii=False),
                json.dumps([dict(x) for x in notes], ensure_ascii=False),
                json.dumps([dict(x) for x in versions], ensure_ascii=False),
            ),
        )

        conn.execute("DELETE FROM review_notes WHERE document_slug=?", (slug,))
        conn.execute("DELETE FROM document_versions WHERE document_slug=?", (slug,))
        conn.execute("DELETE FROM documents WHERE slug=?", (slug,))
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

    def _projects_for_user(self, user: dict | None) -> list[dict]:
        all_projects = list_projects_registry()
        if not user:
            return all_projects
        role = (user.get("role") or "").strip().lower()
        if role == "admin":
            return all_projects
        return [p for p in all_projects if project_role_allowed(p, role)]

    def _project_by_id(self, project_id: int) -> dict | None:
        return next((p for p in list_projects_registry() if int(p.get("project_id") or 0) == int(project_id)), None)

    def _project_access_error(self, project_id: int, user: dict | None) -> str:
        if not user:
            return "Autenticação necessária."
        if (user.get("role") or "").strip().lower() == "admin":
            return ""
        proj = self._project_by_id(project_id)
        if not proj:
            return "Projeto não encontrado."
        if bool(proj.get("is_template")):
            return "Projeto template disponível apenas para administradores."
        return "Sem acesso ao projeto selecionado para seu role."

    def _can_access_project(self, project_id: int, user: dict | None) -> bool:
        if not user:
            return False
        if (user.get("role") or "").strip().lower() == "admin":
            return True
        proj = self._project_by_id(project_id)
        return project_role_allowed(proj, user.get("role") or "")

    def _selected_project_id(self, qs: dict | None = None, user: dict | None = None) -> int:
        try:
            if qs is not None and qs.get("project_id"):
                raw = qs.get("project_id")[0]
                pid = int(raw)
                if pid > 0:
                    return pid
            elif qs is None:
                parsed = urlparse(self.path)
                parsed_qs = parse_qs(parsed.query)
                if parsed_qs.get("project_id"):
                    pid = int(parsed_qs.get("project_id")[0])
                    if pid > 0:
                        return pid
        except Exception:
            pass

        first = self._projects_for_user(user)
        return int(first[0]["project_id"]) if first else 1

    def _get_document_in_scope(self, slug: str, qs: dict | None = None, user: dict | None = None) -> dict | None:
        project_id = self._selected_project_id(qs, user)
        if user and not self._can_access_project(project_id, user):
            return None
        scoped = get_document(slug, project_id)
        if scoped:
            return scoped
        any_scope = get_document(slug)
        if any_scope:
            print(f"[scope] blocked slug={slug} requested_project_id={project_id} real_project_id={any_scope.get('projectId')}")
        return None

    def _reply_document_scope_error(self, slug: str, qs: dict | None = None, user: dict | None = None):
        project_id = self._selected_project_id(qs, user)
        if user and not self._can_access_project(project_id, user):
            return self._json(403, {"ok": False, "error": self._project_access_error(project_id, user)})
        any_scope = get_document(slug)
        if any_scope:
            return self._json(409, {"ok": False, "error": f"Escopo inválido: documento pertence ao projeto {any_scope.get('projectId')}, mas o contexto atual é {project_id}."})
        return self._json(404, {"ok": False, "error": "Documento não encontrado"})

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)
        if p in ["/", "/index.html"]: return self._serve(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if p == "/login.html": return self._serve(WEB_DIR / "login.html", "text/html; charset=utf-8")
        if p == "/signup.html": return self._serve(WEB_DIR / "signup.html", "text/html; charset=utf-8")
        if p == "/kanban.html": return self._serve(WEB_DIR / "kanban.html", "text/html; charset=utf-8")
        if p == "/edit.html": return self._serve(WEB_DIR / "edit.html", "text/html; charset=utf-8")
        if p == "/projects.html": return self._serve(WEB_DIR / "projects.html", "text/html; charset=utf-8")
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
        if p in ["/app.js", "/dashboard.js", "/edit.js", "/projects.js", "/sidebar.js", "/sidebar-project-select.js", "/login.js", "/signup.js", "/admin-users.js", "/profile.js", "/settings.js", "/styles.css"]:
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

        if p == "/api/documents":
            user = self._require_auth()
            if not user: return
            selected_project_id = self._selected_project_id(qs, user)
            if not self._can_access_project(selected_project_id, user):
                return self._json(403, {"ok": False, "error": self._project_access_error(selected_project_id, user)})
            return self._json(200, {
                "documents": list_documents(selected_project_id),
                "statuses": STATUSES,
                "priorities": PRIORITIES,
                "users": list_usernames(),
                "projects": self._projects_for_user(user),
                "selectedProjectId": selected_project_id,
            })

        if p.startswith("/api/documents/") and p.endswith("/document/versions"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = self._get_document_in_scope(slug, qs, user)
            if not proj: return self._reply_document_scope_error(slug, qs, user)
            return self._json(200, {"ok": True, "versions": list_document_versions(slug)})

        if p.startswith("/api/documents/") and p.endswith("/review-notes"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = self._get_document_in_scope(slug, qs, user)
            if not proj: return self._reply_document_scope_error(slug, qs, user)
            return self._json(200, {"ok": True, "notes": list_review_notes(slug)})

        if p.startswith("/api/documents/") and p.endswith("/document"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = self._get_document_in_scope(slug, qs, user)
            if not proj: return self._reply_document_scope_error(slug, qs, user)

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

        if p.startswith("/api/documents/"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            doc = self._get_document_in_scope(slug, qs, user)
            if not doc: return self._reply_document_scope_error(slug, qs, user)
            return self._json(200, {"ok": True, "document": doc, "statuses": STATUSES, "priorities": PRIORITIES, "users": list_usernames()})

        if p == "/api/projects-registry":
            user = self._require_auth()
            if not user: return
            return self._json(200, {"ok": True, "projects": self._projects_for_user(user)})

        if p == "/api/admin/projects":
            if not self._require_admin(): return
            return self._json(200, {"ok": True, "projects": list_projects_registry()})

        if p == "/api/admin/users":
            if not self._require_admin(): return
            with db() as conn:
                user_rows = conn.execute("SELECT username, role, created_at FROM users ORDER BY username").fetchall()
                users = []
                for r in user_rows:
                    task_count = conn.execute(
                        "SELECT COUNT(*) AS c FROM documents WHERE owner = ?",
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

        if p == "/api/admin/deleted-documents":
            if not self._require_admin(): return
            settings = get_admin_settings()
            retention_days = _setting(settings, "deleted.retention_days", "PDASH_DELETED_RETENTION_DAYS", "30")
            return self._json(200, {"ok": True, "retention_days": retention_days, "deleted_documents": list_deleted_documents()})

        if p == "/api/admin/system/diagnostics":
            if not self._require_admin(): return
            return self._json(200, {"ok": True, "diagnostics": run_system_diagnostics()})

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)

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

        if p == "/api/documents":
            user = self._require_auth()
            if not user: return
            if not can_create_document(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para criar documento"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            try:
                pid = int(body.get("project_id") or body.get("projectId") or self._selected_project_id(qs, user))
            except Exception:
                pid = self._selected_project_id(qs, user)
            if not self._can_access_project(pid, user):
                return self._json(403, {"ok": False, "error": self._project_access_error(pid, user)})
            done, msg, slug = create_document(body, user["username"])
            if done:
                audit(user["username"], "document.create", body.get("name", ""), f"status={body.get('status','Backlog')}")
            return self._json(200 if done else 400, {"ok": done, "slug": slug if done else None, "error": None if done else msg})

        if p.startswith("/api/documents/") and p.endswith("/document"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = self._get_document_in_scope(slug, qs, user)
            if not proj:
                return self._reply_document_scope_error(slug, qs, user)
            if not can_upload_document(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para anexar documento"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = save_document_file(
                slug,
                body.get("fileName") or "documento.bin",
                body.get("mimeType") or "application/octet-stream",
                body.get("contentBase64") or "",
                user["username"],
            )
            if done:
                audit(user["username"], "document.file.upload", slug, json.dumps({"file": body.get("fileName", "")}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/documents/") and p.endswith("/review-notes"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = self._get_document_in_scope(slug, qs, user)
            if not proj:
                return self._reply_document_scope_error(slug, qs, user)
            if not can_add_review_note(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para adicionar nota de revisão"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = add_review_note(slug, body.get("note") or "", user["username"])
            if done:
                audit(user["username"], "document.review_note.create", slug, "note_added")
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

        if p == "/api/admin/system/backup/run":
            admin = self._require_admin()
            if not admin: return
            done, msg = run_system_backup(admin["username"])
            return self._json(200 if done else 400, {"ok": done, "message": msg if done else None, "error": None if done else msg})

        if p.startswith("/api/admin/deleted-documents/") and p.endswith("/restore"):
            admin = self._require_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 5:
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                deleted_id = int(parts[3])
            except Exception:
                return self._json(400, {"ok": False, "error": "id inválido"})
            done, msg = restore_deleted_document(deleted_id, admin["username"])
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

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

        if p == "/api/admin/projects":
            admin = self._require_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg, new_project_id = create_project_registry(body)
            if done:
                audit(admin["username"], "project.registry.create", body.get("project_name", ""))
            return self._json(200 if done else 400, {"ok": done, "project_id": new_project_id if done else None, "error": None if done else msg})

        if p.startswith("/api/admin/projects/") and p.endswith("/clone"):
            admin = self._require_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 5:
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                template_project_id = int(parts[3])
            except Exception:
                return self._json(400, {"ok": False, "error": "ID inválido"})
            ok, body = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": body["error"]})
            done, msg, new_project_id = clone_project_from_template(template_project_id, body, admin["username"])
            if done:
                audit(admin["username"], "project.registry.clone_from_template", str(template_project_id), f"new_project_id={new_project_id}")
            return self._json(200 if done else 400, {"ok": done, "project_id": new_project_id if done else None, "error": None if done else msg})

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
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)

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

        if p.startswith("/api/documents/") and "/review-notes/" in p:
            user = self._require_auth()
            if not user: return
            parts = p.strip("/").split("/")
            # /api/documents/{slug}/review-notes/{id}
            if len(parts) != 5 or parts[0] != "api" or parts[1] != "documents" or parts[3] != "review-notes":
                return self._json(404, {"ok": False, "error": "not found"})
            slug = parts[2]
            try:
                note_id = int(parts[4])
            except Exception:
                return self._json(400, {"ok": False, "error": "invalid note id"})

            if not self._get_document_in_scope(slug, qs, user):
                return self._reply_document_scope_error(slug, qs, user)

            if not can_resolve_review_note(user["role"]):
                return self._json(403, {"ok": False, "error": "Apenas desenhista ou admin pode alterar status da revisão"})

            ok, body = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": body["error"]})
            if "resolved" not in body or not isinstance(body.get("resolved"), bool):
                return self._json(400, {"ok": False, "error": "resolved (boolean) is required"})

            done, msg = set_review_note_resolution(slug, note_id, user["username"], bool(body.get("resolved")))
            if done:
                audit(user["username"], "document.review_note.status", slug, json.dumps({"note_id": note_id, "resolved": bool(body.get("resolved"))}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/documents/"):
            user = self._require_auth()
            if not user: return
            if not can_edit_document(user["role"]):
                return self._json(403, {"ok": False, "error": "Sem permissão para editar documento"})
            slug = p.split("/")[3]
            if not self._get_document_in_scope(slug, qs, user):
                return self._reply_document_scope_error(slug, qs, user)
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})

            done, msg = patch_document(slug, body, self._selected_project_id(qs, user))
            if done:
                audit(user["username"], "document.update", slug, json.dumps(body, ensure_ascii=False))
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

        if p.startswith("/api/admin/projects/"):
            admin = self._require_admin()
            if not admin: return
            pid = p.split("/")[4]
            try:
                project_id = int(pid)
            except Exception:
                return self._json(400, {"ok": False, "error": "ID inválido"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = update_project_registry(project_id, body)
            if done:
                audit(admin["username"], "project.registry.update", str(project_id))
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
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)
        if p.startswith("/api/documents/"):
            user = self._require_auth()
            if not user: return
            slug = p.split("/")[3]
            proj = self._get_document_in_scope(slug, qs, user)
            if not proj:
                return self._reply_document_scope_error(slug, qs, user)
            if not can_delete_document(user["role"], user["username"], proj):
                return self._json(403, {"ok": False, "error": "Sem permissão para apagar documento"})
            done, msg = delete_document(slug, user["username"])
            if done:
                audit(user["username"], "document.delete", slug)
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/deleted-documents/"):
            admin = self._require_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 4:
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                deleted_id = int(parts[3])
            except Exception:
                return self._json(400, {"ok": False, "error": "id inválido"})
            done, msg = delete_deleted_document_permanently(deleted_id, admin["username"])
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

        if p.startswith("/api/admin/projects/"):
            admin = self._require_admin()
            if not admin: return
            try:
                project_id = int(p.split("/")[4])
            except Exception:
                return self._json(400, {"ok": False, "error": "ID inválido"})
            done, msg, deleted_cards = delete_project_registry(project_id)
            if done:
                audit(admin["username"], "project.registry.delete", str(project_id), f"deleted_cards={deleted_cards}")
            return self._json(200 if done else 400, {"ok": done, "deleted_cards": deleted_cards if done else 0, "error": None if done else msg})

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
    migrate_existing_documents()
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
