#!/usr/bin/env python3
"""
ProjectDashboard — backend principal
===================================

Este arquivo ainda funciona como o ponto central de composição da aplicação.
Mesmo com a modularização já iniciada, ele continua reunindo:

- bootstrap do sistema
- utilitários gerais
- partes relevantes da lógica de domínio
- rotas/dispatch HTTP
- integração entre módulos extraídos e código legado

Objetivo de documentação
------------------------
À medida que o projeto evolui para uma arquitetura mais modular, este arquivo
precisa ser legível o suficiente para que futuras extrações sejam seguras.
Por isso, esta documentação descreve:

- o papel de blocos importantes
- o contrato esperado das funções utilitárias
- como cada função deve ser chamada e tratada no restante do sistema

Observação importante
---------------------
Nem toda função aqui representa um destino final de arquitetura. Muitas ainda
existem em `app.py` por razões de evolução incremental. A documentação ajuda a
reduzir risco enquanto a base é reorganizada.
"""

import base64
import json
import os
import re
import sqlite3
import subprocess
import smtplib
import shutil
import threading
import time
from email.message import EmailMessage
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend.auth.session import (
    create_session as create_auth_session,
    current_user_from_cookie as current_user_from_session_cookie,
    hash_password,
    parse_cookie,
    verify_password,
)
from backend.admin.settings import (
    get_admin_settings as load_admin_settings,
    update_admin_settings as persist_admin_settings,
)
from backend.admin.settings import (
    get_admin_settings as load_admin_settings,
    update_admin_settings as persist_admin_settings,
)
from backend.core.db import column_exists, connect_db, ensure_column, table_exists
from backend.rbac.roles import (
    list_role_catalog as list_rbac_role_catalog,
    resolve_fallback_role as resolve_rbac_fallback_role,
    role_exists as rbac_role_exists,
    role_is_active as rbac_role_is_active,
)

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
ROLES = ["admin", "lider_projeto", "member", "desenhista", "colaborador", "revisor", "cliente"]
ADMIN_EQUIV_ROLES = {"admin", "lider_projeto"}
SETTING_KEY_TO_MODULE = {
    "smtp.host": "settings.smtp",
    "smtp.port": "settings.smtp",
    "smtp.user": "settings.smtp",
    "smtp.pass": "settings.smtp",
    "smtp.from": "settings.smtp",
    "smtp.tls": "settings.smtp",
    "invite.default_message": "settings.smtp",
    "workflow.default_due_days": "settings.system_behavior",
    "workflow.dependency_max_status": "settings.system_behavior",
    # Defensive alias for possible old/typo payloads from cached frontends.
    "workflow.dependency.max.status": "settings.system_behavior",
    "backup.enabled": "settings.backup",
    "backup.path": "settings.backup",
    "backup.weekdays": "settings.backup",
    "backup.run_time": "settings.backup",
    "system.git_repo": "settings.system_diagnostics",
    "system.git_branch": "settings.system_diagnostics",
    "deleted.retention_days": "settings.recoverable_documents",
}

MODULE_CATALOG_V1 = [
    {"module_id": "projects.create_edit", "page_key": "projects.html", "label": "Create/Edit Project", "active": 1},
    {"module_id": "projects.list", "page_key": "projects.html", "label": "Registered Projects", "active": 1},
    {"module_id": "projects.cards_list", "page_key": "projects.html", "label": "Cards List", "active": 1},
    {"module_id": "admin_users.create", "page_key": "admin-users.html", "label": "Create User", "active": 1},
    {"module_id": "admin_users.invite", "page_key": "admin-users.html", "label": "Invite New User", "active": 1},
    {"module_id": "admin_users.list", "page_key": "admin-users.html", "label": "Registered Users", "active": 1},
    {"module_id": "admin_users.audit_log", "page_key": "admin-users.html", "label": "Audit Log", "active": 1},
    {"module_id": "settings.smtp", "page_key": "settings.html", "label": "Email Sending (SMTP)", "active": 1},
    {"module_id": "settings.system_behavior", "page_key": "settings.html", "label": "System Behavior", "active": 1},
    {"module_id": "settings.backup", "page_key": "settings.html", "label": "System Backup", "active": 1},
    {"module_id": "settings.backup_restore", "page_key": "settings.html", "label": "System Backup Recovery", "active": 1},
    {"module_id": "settings.system_diagnostics", "page_key": "settings.html", "label": "System Diagnostics", "active": 1},
    {"module_id": "settings.recoverable_documents", "page_key": "settings.html", "label": "Recoverable Documents", "active": 1},
    {"module_id": "settings.periodic_reports", "page_key": "settings.html", "label": "Periodic Reports", "active": 1},
    {"module_id": "settings.roles_control", "page_key": "settings.html", "label": "Roles Control", "active": 1},
]
SKIP_DIRS = {"ProjectDashboard", "__pycache__"}
SESSION_COOKIE = "pdash_session"
SESSION_TTL_SECONDS = 60 * 60 * 24

SESSIONS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Utilitários base de data, texto e conexão
# ---------------------------------------------------------------------------
def now_iso() -> str:
    """
    Devolve o timestamp atual em UTC no formato ISO-8601 com sufixo `Z`.

    Retorno
    -------
    str
        Exemplo: `2026-03-29T00:00:00Z`

    Como deve ser usada
    -------------------
    Deve ser usada sempre que a aplicação precisar gerar timestamps para
    persistência, auditoria ou respostas coerentes em UTC.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Parsing defensivo de data ISO
# ---------------------------------------------------------------------------
def _parse_iso_date(value: str | None) -> datetime | None:
    """
    Converte uma string ISO em `datetime`, quando possível.

    Parâmetros
    ----------
    value:
        Data em string, normalmente vinda do banco ou de payloads internos.

    Retorno
    -------
    datetime | None
        Retorna `datetime` quando o valor é válido; `None` quando ausente ou
        inválido.

    Observação
    ----------
    O comportamento defensivo desta função evita quebrar a aplicação em fluxos
    que lidam com dados legados ou parciais.
    """
    if not value:
        return None
    v = str(value).strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", ""))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cálculo de idade/tempo de resolução de documento
# ---------------------------------------------------------------------------
def _project_age_fields(opened_at: str, status: str, released_at: str) -> tuple[str, int]:
    """
    Calcula o rótulo e o número de dias relevantes para um documento.

    Estratégia
    ----------
    - Se o documento já foi concluído e possui `released_at`, calcula dias até
      solução.
    - Caso contrário, calcula dias desde a abertura.

    Parâmetros
    ----------
    opened_at:
        Data de abertura do documento.
    status:
        Status atual do documento.
    released_at:
        Data de liberação/conclusão, quando existir.

    Retorno
    -------
    tuple[str, int]
        `(label, days)` para uso em UI e relatórios.
    """
    opened = _parse_iso_date(opened_at) or datetime.now(UTC)
    if status == "Concluído" and released_at:
        released = _parse_iso_date(released_at) or datetime.now(UTC)
        days = max(0, (released.date() - opened.date()).days)
        return "Dia até solução", days
    days = max(0, (datetime.now(UTC).date() - opened.date()).days)
    return "Dias desde abertura", days


# ---------------------------------------------------------------------------
# Geração de slug estável
# ---------------------------------------------------------------------------
def slugify(name: str) -> str:
    """
    Converte um nome livre em slug seguro para uso interno.

    Parâmetros
    ----------
    name:
        Texto-base que será normalizado.

    Retorno
    -------
    str
        Slug minúsculo, sem caracteres inválidos. Se nada sobrar após a
        normalização, devolve `documento`.
    """
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower() or "documento"


# ---------------------------------------------------------------------------
# Leitura defensiva de arquivo texto
# ---------------------------------------------------------------------------
def read_text_if_exists(path: Path) -> str:
    """
    Lê um arquivo texto apenas se ele existir e for arquivo regular.

    Parâmetros
    ----------
    path:
        Caminho do arquivo desejado.

    Retorno
    -------
    str
        Conteúdo do arquivo quando existir; string vazia caso contrário.
    """
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


# ---------------------------------------------------------------------------
# Inferência de descrição a partir do README do projeto
# ---------------------------------------------------------------------------
def infer_description(project_dir: Path) -> str:
    """
    Tenta inferir uma descrição curta de projeto a partir do README local.

    Estratégia
    ----------
    Procura a primeira linha não vazia que não seja cabeçalho Markdown e usa
    esse conteúdo como resumo curto.

    Parâmetros
    ----------
    project_dir:
        Diretório-base do projeto a ser inspecionado.

    Retorno
    -------
    str
        Descrição resumida ou `Sem descrição` quando não for possível inferir.
    """
    for line in read_text_if_exists(project_dir / "README.md").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:180]
    return "Sem descrição"


# ---------------------------------------------------------------------------
# Factory principal de conexão com banco
# ---------------------------------------------------------------------------
def db() -> sqlite3.Connection:
    """
    Devolve uma conexão SQLite pronta para uso pelo restante do backend.

    Retorno
    -------
    sqlite3.Connection
        Conexão com `row_factory` configurado.

    Como deve ser usada
    -------------------
    Esta é a factory padrão de banco no `app.py`. Funções de domínio e rotas
    devem preferir `with db() as conn:` em vez de abrir conexões diretamente.
    """
    return connect_db(DATA_DIR, DB_PATH)


# ---------------------------------------------------------------------------
# Migrações legadas: projects -> documents
# ---------------------------------------------------------------------------


def migrate_projects_to_documents(conn: sqlite3.Connection) -> None:
    """
    Migra estruturas legadas do antigo modelo `projects` para o modelo atual de
    `documents`, incluindo tabelas auxiliares relacionadas.

    Parâmetros
    ----------
    conn:
        Conexão ativa com o banco durante bootstrap/migração.

    Retorno
    -------
    None

    Como deve ser usada
    -------------------
    Deve ser chamada apenas em rotinas de inicialização/migração do banco.
    Não é uma função de uso operacional normal das rotas.

    Observação
    ----------
    Trata compatibilidade com instalações antigas. Conforme o projeto evoluir
    para migrations versionadas formais, esta lógica deve migrar para camadas
    mais explícitas de evolução de schema.
    """
    # Migrate legacy projects table into documents table (only if legacy schema exists)
    if table_exists(conn, 'projects') and column_exists(conn, 'projects', 'slug'):
        total_docs = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()[0]
        total_projects = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()[0]
        if total_projects and total_docs == 0:
            conn.execute(
                "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at) "
                "SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at FROM projects"
            )

    # Migrate deleted table (project_json -> document_json)
    if table_exists(conn, 'deleted_projects') or table_exists(conn, 'deleted_documents'):
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
        if table_exists(conn, 'deleted_projects'):
            conn.execute(
                "INSERT INTO deleted_documents_new (id, slug, name, deleted_at, deleted_by, trash_path, document_json, review_notes_json, document_versions_json) "
                "SELECT id, slug, name, deleted_at, deleted_by, trash_path, project_json, review_notes_json, document_versions_json FROM deleted_projects"
            )
        # from old deleted_documents (if it had project_json)
        if table_exists(conn, 'deleted_documents'):
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
        if table_exists(conn, 'deleted_documents'):
            conn.execute("DROP TABLE deleted_documents")
        conn.execute("ALTER TABLE deleted_documents_new RENAME TO deleted_documents")

    # Migrate review_notes.project_slug -> document_slug
    if table_exists(conn, 'review_notes') and column_exists(conn, 'review_notes', 'project_slug') and not column_exists(conn, 'review_notes', 'document_slug'):
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
    if table_exists(conn, 'document_versions') and column_exists(conn, 'document_versions', 'project_slug') and not column_exists(conn, 'document_versions', 'document_slug'):
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
    return role in {"admin", "lider_projeto", "member", "desenhista", "colaborador"}


def can_upload_document(role: str) -> bool:
    return role in {"admin", "lider_projeto", "member", "desenhista", "colaborador"}


def can_add_review_note(role: str) -> bool:
    return role in {"admin", "lider_projeto", "member", "desenhista", "colaborador", "revisor"}


def can_resolve_review_note(role: str) -> bool:
    return role in {"desenhista", "colaborador", "admin", "lider_projeto"}


def can_delete_document(role: str, user: str, document: dict) -> bool:
    if role in ADMIN_EQUIV_ROLES:
        return True
    if role == "member":
        return (document.get("createdBy") or "").strip().lower() == user.strip().lower()
    return False


# ---------------------------------------------------------------------------
# Fundação de roles e catálogo de módulos
# ---------------------------------------------------------------------------
def ensure_roles_foundation(conn: sqlite3.Connection) -> None:
    """
    Garante a base estrutural mínima de roles e módulos no banco.

    Parâmetros
    ----------
    conn:
        Conexão ativa do banco durante bootstrap.

    Retorno
    -------
    None

    Como deve ser usada
    -------------------
    Deve ser executada no processo de inicialização do schema, antes de fluxos
    administrativos que dependam de catálogo de roles/módulos.
    """
    # Fase 1: base de roles no banco (compatível com modelo atual)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_key TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            is_system INTEGER NOT NULL DEFAULT 0,
            is_superadmin INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_roles_active ON roles(active)")

    # Tombstones: bloqueia ressurreição automática de roles removidas manualmente
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deleted_roles (
            role_key TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL DEFAULT '',
            deleted_by TEXT NOT NULL DEFAULT ''
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS role_module_permissions (
            role_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            can_access INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (role_id, module_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_role_module_permissions_module ON role_module_permissions(module_id)")

    now = now_iso()
    deleted_roles = {
        str(r[0] or "").strip().lower()
        for r in conn.execute("SELECT role_key FROM deleted_roles WHERE role_key IS NOT NULL AND TRIM(role_key)<>''").fetchall()
    }

    existing_roles_count = int(conn.execute("SELECT COUNT(*) AS c FROM roles").fetchone()["c"] or 0)

    # Seed oficial apenas no bootstrap inicial (evita ressuscitar roles apagadas manualmente)
    if existing_roles_count == 0:
        for role_key in ROLES:
            if role_key != "admin" and role_key in deleted_roles:
                continue
            is_super = 1 if role_key == "admin" else 0
            is_system = 1 if role_key == "admin" else 0
            conn.execute(
                """
                INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, 1, ?, ?, 'system', 'system')
                """,
                (role_key, role_key, is_system, is_super, now, now),
            )
    else:
        # Garantia mínima: admin sempre existe/protegido
        conn.execute(
            """
            INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
            VALUES ('admin', 'admin', 1, 1, 1, ?, ?, 'system', 'system')
            ON CONFLICT(role_key) DO UPDATE SET
                is_system=1,
                is_superadmin=1,
                active=1,
                updated_at=excluded.updated_at,
                updated_by='system'
            """,
            (now, now),
        )

    # Garante que roles já existentes em dados legados também existam no catálogo
    legacy_roles = set()
    for row in conn.execute("SELECT DISTINCT role FROM users WHERE role IS NOT NULL AND TRIM(role)<>''").fetchall():
        legacy_roles.add(str(row[0]).strip().lower())
    for row in conn.execute("SELECT DISTINCT role_name FROM role_modules WHERE role_name IS NOT NULL AND TRIM(role_name)<>''").fetchall():
        legacy_roles.add(str(row[0]).strip().lower())
    for row in conn.execute("SELECT DISTINCT allowed_roles FROM projects WHERE allowed_roles IS NOT NULL AND TRIM(allowed_roles)<>''").fetchall():
        for role_name in str(row[0] or "").split(','):
            role_name = role_name.strip().lower()
            if role_name:
                legacy_roles.add(role_name)

    for role_key in sorted(legacy_roles):
        if role_key != "admin" and role_key in deleted_roles:
            continue
        conn.execute(
            """
            INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, 0, 0, 1, ?, ?, 'migration', 'migration')
            ON CONFLICT(role_key) DO NOTHING
            """,
            (role_key, role_key, now, now),
        )

    # Sincroniza permissões legadas para a nova tabela
    role_map = {
        str(r["role_key"]): int(r["id"])
        for r in conn.execute("SELECT id, role_key FROM roles").fetchall()
    }

    legacy_permissions = conn.execute(
        "SELECT role_name, module_id, can_access, updated_at, updated_by FROM role_modules"
    ).fetchall()

    for p in legacy_permissions:
        role_key = str(p["role_name"] or "").strip().lower()
        module_id = str(p["module_id"] or "").strip()
        if not role_key or not module_id:
            continue
        role_id = role_map.get(role_key)
        if not role_id:
            continue
        conn.execute(
            """
            INSERT INTO role_module_permissions (role_id, module_id, can_access, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(role_id, module_id) DO UPDATE SET
                can_access=excluded.can_access,
                updated_at=excluded.updated_at,
                updated_by=excluded.updated_by
            """,
            (
                role_id,
                module_id,
                int(p["can_access"] or 0),
                str(p["updated_at"] or now),
                str(p["updated_by"] or "migration"),
            ),
        )

    # Regra de negócio: admin sempre com acesso total nos módulos ativos
    admin_id = role_map.get("admin")
    if admin_id:
        modules = conn.execute("SELECT module_id FROM app_modules").fetchall()
        for m in modules:
            module_id = str(m["module_id"])
            conn.execute(
                """
                INSERT INTO role_module_permissions (role_id, module_id, can_access, updated_at, updated_by)
                VALUES (?, ?, 1, ?, 'system')
                ON CONFLICT(role_id, module_id) DO UPDATE SET
                    can_access=1,
                    updated_at=excluded.updated_at,
                    updated_by='system'
                """,
                (admin_id, module_id, now),
            )


# ---------------------------------------------------------------------------
# Inicialização principal do banco e bootstrap do sistema
# ---------------------------------------------------------------------------
def init_db():
    """
    Inicializa o banco principal da aplicação, garantindo tabelas, colunas,
    seeds e migrações defensivas necessárias para o estado atual do sistema.

    Retorno
    -------
    None

    Como deve ser usada
    -------------------
    Esta função deve ser chamada em bootstrap de instalação e em inicialização
    do backend quando for necessário garantir integridade mínima do schema.

    Observação
    ----------
    Esta função ainda concentra responsabilidades históricas e é candidata a
    futura decomposição em uma camada mais formal de migrations/bootstrap.
    """
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL,
                applied_by TEXT NOT NULL DEFAULT 'system'
            )
        """)
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
                allowed_roles TEXT NOT NULL DEFAULT 'member,desenhista,colaborador,revisor,cliente',
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
            CREATE TABLE IF NOT EXISTS document_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                document_slug TEXT NOT NULL,
                depends_on_slug TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(document_slug, depends_on_slug)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_deps_document ON document_dependencies(document_slug)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_deps_depends_on ON document_dependencies(depends_on_slug)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_by TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_modules (
                module_id TEXT PRIMARY KEY,
                page_key TEXT NOT NULL,
                label TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS role_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL,
                module_id TEXT NOT NULL,
                can_access INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL DEFAULT '',
                UNIQUE(role_name, module_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_role_modules_role ON role_modules(role_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_role_modules_module ON role_modules(module_id)")
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
        ensure_column(conn, "projects", "allowed_roles", "allowed_roles TEXT NOT NULL DEFAULT 'member,desenhista,colaborador,revisor,cliente'")
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
        ensure_column(conn, "users", "priority_color_enabled", "priority_color_enabled INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "priority_colors_json", "priority_colors_json TEXT NOT NULL DEFAULT ''")

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
        conn.execute("UPDATE projects SET allowed_roles='member,desenhista,colaborador,revisor,cliente' WHERE allowed_roles IS NULL OR TRIM(allowed_roles)=''")
        conn.execute("UPDATE projects SET is_template=0 WHERE is_template IS NULL")
        conn.execute("UPDATE documents SET project_id=1 WHERE project_id IS NULL OR project_id<=0")
        conn.execute("UPDATE documents SET document_status=status")
        conn.execute("UPDATE documents SET created_by=owner WHERE created_by='' AND owner<>''")
        conn.execute("UPDATE documents SET opened_at=updated_at WHERE opened_at='' AND updated_at<>''")
        conn.execute("UPDATE documents SET opened_at=? WHERE opened_at=''",(now_iso(),))
        conn.execute("UPDATE documents SET due_date='-' WHERE status='Concluído'")
        conn.execute("UPDATE documents SET released_at=updated_at WHERE status='Concluído' AND released_at='' AND updated_at<>''")

        for mod in MODULE_CATALOG_V1:
            conn.execute(
                """
                INSERT INTO app_modules (module_id, page_key, label, active, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(module_id) DO UPDATE SET
                    page_key=excluded.page_key,
                    label=excluded.label,
                    active=excluded.active
                """,
                (mod["module_id"], mod["page_key"], mod["label"], int(mod.get("active", 1)), now_iso()),
            )

        ensure_roles_foundation(conn)

        for k, v in [
            ("smtp.host", ""),
            ("smtp.port", "587"),
            ("smtp.user", ""),
            ("smtp.pass", ""),
            ("smtp.from", ""),
            ("smtp.tls", "true"),
            ("invite.default_message", "Olá!\n\nVocê foi convidado(a) para acessar o ProjectDashboard.\n\nUse este link para concluir seu cadastro:\n{invite_link}\n\nEste convite expira em: {expires_at}\n\nBem-vindo(a) ao sistema!"),
            ("workflow.default_due_days", "7"),
            ("workflow.dependency_max_status", "Backlog"),
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


# ---------------------------------------------------------------------------
# Consulta e leitura de documentos
# ---------------------------------------------------------------------------
def list_documents(project_id: int | None = None) -> list[dict]:
    """
    Lista documentos do sistema, opcionalmente filtrando por projeto.

    Parâmetros
    ----------
    project_id:
        Identificador do projeto. Quando omitido, a função retorna documentos
        de todos os projetos visíveis no banco.

    Retorno
    -------
    list[dict]
        Lista de documentos já normalizados para uso por rotas e UI.

    Como deve ser usada
    -------------------
    Deve ser chamada por endpoints de listagem, dashboards e telas operacionais.
    É uma função de leitura; não deve aplicar efeitos colaterais.
    """
    with db() as conn:
        if project_id is None:
            rows = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents ORDER BY name").fetchall()
        else:
            rows = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents WHERE project_id=? ORDER BY name", (project_id,)).fetchall()

        dep_rows = conn.execute(
            """
            SELECT dd.project_id, dd.document_slug, dd.depends_on_slug, d.name, d.status
            FROM document_dependencies dd
            JOIN documents d ON d.slug = dd.depends_on_slug
            """
        ).fetchall()

    deps_by_doc: dict[tuple[int, str], list[dict]] = {}
    for dr in dep_rows:
        key = (int(dr["project_id"] or 1), str(dr["document_slug"] or ""))
        deps_by_doc.setdefault(key, []).append({
            "slug": dr["depends_on_slug"],
            "name": dr["name"],
            "status": dr["status"],
        })

    out = []
    for r in rows:
        pid = int(r["project_id"] or 1)
        deps = deps_by_doc.get((pid, str(r["slug"])), [])
        out.append({
            "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
            "owner": r["owner"], "dueDate": ("-" if r["status"] == "Concluído" else r["due_date"]), "description": r["description"],
            "path": r["path"], "updatedAt": r["updated_at"],
            "documentStatus": ("aguardando edição" if r["status"] == "Backlog" else "em andamento" if r["status"] == "Em andamento" else "em revisão" if r["status"] == "Em revisão" else "release"), "documentName": r["document_name"],
            "documentMime": r["document_mime"], "hasDocument": bool(r["document_path"]),
            "createdBy": r["created_by"], "projectId": pid,
            "openedAt": r["opened_at"], "releasedAt": r["released_at"],
            "ageLabel": _project_age_fields(r["opened_at"], r["status"], r["released_at"])[0],
            "ageDays": _project_age_fields(r["opened_at"], r["status"], r["released_at"])[1],
            "dependsOn": [d["slug"] for d in deps],
            "dependencies": deps,
            "isBlockedByDependencies": any(str(d.get("status") or "") != "Concluído" for d in deps),
        })
    return out


# ---------------------------------------------------------------------------
# Leitura de documento individual
# ---------------------------------------------------------------------------
def get_document(slug: str, project_id: int | None = None) -> dict | None:
    """
    Resolve um documento individual a partir do slug, opcionalmente limitado a um projeto.

    Parâmetros
    ----------
    slug:
        Identificador lógico do documento.
    project_id:
        Projeto esperado para escopo defensivo, quando aplicável.

    Retorno
    -------
    dict | None
        Documento encontrado em formato de dicionário ou `None` quando não existe.

    Como deve ser usada
    -------------------
    Base para rotas de detalhe, edição, revisão, anexo e validação de escopo.
    """
    with db() as conn:
        if project_id is None:
            r = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents WHERE slug=?", (slug,)).fetchone()
        else:
            r = conn.execute("SELECT slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id FROM documents WHERE slug=? AND project_id=?", (slug, project_id)).fetchone()
    if not r:
        return None
    age_label, age_days = _project_age_fields(r["opened_at"], r["status"], r["released_at"])
    project_id_val = int(r["project_id"] or 1)
    deps = list_document_dependencies(r["slug"], project_id_val)
    return {
        "slug": r["slug"], "name": r["name"], "status": r["status"], "priority": r["priority"],
        "owner": r["owner"], "dueDate": ("-" if r["status"] == "Concluído" else r["due_date"]), "description": r["description"],
        "path": r["path"], "updatedAt": r["updated_at"],
        "documentStatus": ("aguardando edição" if r["status"] == "Backlog" else "em andamento" if r["status"] == "Em andamento" else "em revisão" if r["status"] == "Em revisão" else "release"), "documentName": r["document_name"],
        "documentMime": r["document_mime"], "documentPath": r["document_path"],
        "hasDocument": bool(r["document_path"]), "createdBy": r["created_by"], "projectId": project_id_val,
        "openedAt": r["opened_at"], "releasedAt": r["released_at"],
        "ageLabel": age_label, "ageDays": age_days,
        "dependsOn": [d["slug"] for d in deps],
        "dependencies": deps,
        "isBlockedByDependencies": any(str(d.get("status") or "") != "Concluído" for d in deps),
    }


# ---------------------------------------------------------------------------
# Normalização de payload de dependências
# ---------------------------------------------------------------------------
def _dependency_slugs_from_payload(payload: dict | None) -> list[str] | None:
    """
    Extrai e normaliza a lista de slugs de dependência a partir de um payload.

    Parâmetros
    ----------
    payload:
        Payload bruto recebido pela aplicação, normalmente vindo de PATCH/POST.

    Retorno
    -------
    list[str] | None
        Lista normalizada de slugs quando o payload traz dependências; `None`
        quando o chamador não informou o campo.

    Como deve ser usada
    -------------------
    Helper interno para criação/edição de documentos. Ela separa a semântica de
    “campo ausente” da semântica de “lista vazia”.
    """
    if not isinstance(payload, dict):
        return None
    raw = payload.get("depends_on") if "depends_on" in payload else payload.get("dependsOn")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("depends_on deve ser uma lista de slugs")
    out: list[str] = []
    for item in raw:
        slug = str(item or "").strip()
        if not slug:
            continue
        if slug not in out:
            out.append(slug)
    return out


# ---------------------------------------------------------------------------
# Leitura de dependências explícitas de documento
# ---------------------------------------------------------------------------
def list_document_dependencies(slug: str, project_id: int) -> list[dict]:
    """
    Lista as dependências explícitas de um documento dentro de um projeto.

    Parâmetros
    ----------
    slug:
        Documento de origem.
    project_id:
        Projeto ao qual a relação pertence.

    Retorno
    -------
    list[dict]
        Lista de documentos dos quais o documento atual depende.
    """
    with db() as conn:
        rows = conn.execute(
            """
            SELECT dd.depends_on_slug, d.name, d.status
            FROM document_dependencies dd
            JOIN documents d ON d.slug = dd.depends_on_slug
            WHERE dd.document_slug=? AND dd.project_id=?
            ORDER BY d.name
            """,
            (slug, project_id),
        ).fetchall()
    return [{"slug": r["depends_on_slug"], "name": r["name"], "status": r["status"]} for r in rows]


# ---------------------------------------------------------------------------
# Dependências pendentes
# ---------------------------------------------------------------------------
def unresolved_dependencies(slug: str, project_id: int) -> list[dict]:
    """
    Lista apenas as dependências ainda não concluídas de um documento.

    Parâmetros
    ----------
    slug:
        Documento de origem.
    project_id:
        Projeto ao qual o documento pertence.

    Retorno
    -------
    list[dict]
        Dependências cujo status ainda não está concluído.
    """
    deps = list_document_dependencies(slug, project_id)
    return [d for d in deps if str(d.get("status") or "") != "Concluído"]


# ---------------------------------------------------------------------------
# Detecção defensiva de ciclo em grafo de dependências
# ---------------------------------------------------------------------------
def _would_create_cycle(conn: sqlite3.Connection, source_slug: str, candidate_dep_slug: str, project_id: int) -> bool:
    """
    Informa se adicionar uma dependência criaria ciclo entre documentos.

    Parâmetros
    ----------
    conn:
        Conexão ativa do banco.
    source_slug:
        Documento que receberia a dependência.
    candidate_dep_slug:
        Documento candidato a virar dependência.
    project_id:
        Projeto no qual o relacionamento deve ser validado.

    Retorno
    -------
    bool
        `True` quando a nova dependência criaria ciclo.

    Como deve ser usada
    -------------------
    Deve ser chamada antes de persistir dependências para preservar integridade
    do fluxo de trabalho.
    """
    stack = [candidate_dep_slug]
    seen: set[str] = set()
    while stack:
        cur = stack.pop()
        if cur == source_slug:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        children = conn.execute(
            "SELECT depends_on_slug FROM document_dependencies WHERE document_slug=? AND project_id=?",
            (cur, project_id),
        ).fetchall()
        for row in children:
            nxt = str(row["depends_on_slug"] or "").strip()
            if nxt:
                stack.append(nxt)
    return False


# ---------------------------------------------------------------------------
# Persistência de dependências de documento
# ---------------------------------------------------------------------------
def set_document_dependencies(slug: str, project_id: int, depends_on_slugs: list[str], actor: str) -> tuple[bool, str]:
    """
    Atualiza a lista de dependências de um documento.

    Parâmetros
    ----------
    slug:
        Documento de origem.
    project_id:
        Projeto no qual a relação será salva.
    depends_on_slugs:
        Lista final de slugs dos pré-requisitos.
    actor:
        Usuário responsável pela alteração, para auditoria.

    Retorno
    -------
    tuple[bool, str]
        `(ok, message)` indicando sucesso ou motivo de falha.

    Como deve ser usada
    -------------------
    Chamada por fluxos de criação/edição quando o campo de dependência é
    alterado. Também aplica verificações de integridade, como prevenção de ciclo.
    """
    with db() as conn:
        doc = conn.execute("SELECT slug FROM documents WHERE slug=? AND project_id=?", (slug, project_id)).fetchone()
        if not doc:
            return False, "Documento não encontrado"

        for dep_slug in depends_on_slugs:
            if dep_slug == slug:
                return False, "Um documento não pode depender de si mesmo"
            dep_doc = conn.execute("SELECT slug FROM documents WHERE slug=? AND project_id=?", (dep_slug, project_id)).fetchone()
            if not dep_doc:
                return False, f"Dependência inválida (fora do projeto ou inexistente): {dep_slug}"
            if _would_create_cycle(conn, slug, dep_slug, project_id):
                return False, f"Dependência cíclica detectada com {dep_slug}"

        conn.execute("DELETE FROM document_dependencies WHERE document_slug=? AND project_id=?", (slug, project_id))
        now = now_iso()
        for dep_slug in depends_on_slugs:
            conn.execute(
                "INSERT OR IGNORE INTO document_dependencies (project_id, document_slug, depends_on_slug, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, slug, dep_slug, actor, now),
            )

    return True, "ok"


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


def list_role_catalog(include_admin: bool = True) -> list[str]:
    return list_rbac_role_catalog(db, ROLES, include_admin=include_admin)


def role_exists(role_key: str, active_only: bool = True) -> bool:
    return rbac_role_exists(db, role_key, active_only=active_only)


def role_is_active(role_key: str) -> bool:
    return rbac_role_is_active(db, role_key, ROLES)


def resolve_fallback_role(preferred: str = "member") -> str:
    return resolve_rbac_fallback_role(db, preferred=preferred)


def list_roles_admin_view() -> list[dict]:
    with db() as conn:
        role_rows = conn.execute(
            """
            SELECT id, role_key, display_name, is_system, is_superadmin, active, created_at, updated_at
            FROM roles
            ORDER BY id
            """
        ).fetchall()

        user_counts = {
            str(r["role"] or "").strip().lower(): int(r["c"] or 0)
            for r in conn.execute(
                "SELECT role, COUNT(*) AS c FROM users GROUP BY role"
            ).fetchall()
        }

        module_counts = {
            int(r["role_id"]): int(r["c"] or 0)
            for r in conn.execute(
                "SELECT role_id, COUNT(*) AS c FROM role_module_permissions WHERE can_access=1 GROUP BY role_id"
            ).fetchall()
        }

    out = []
    for r in role_rows:
        role_key = str(r["role_key"])
        out.append({
            "id": int(r["id"]),
            "role_key": role_key,
            "display_name": str(r["display_name"] or role_key),
            "is_system": bool(int(r["is_system"] or 0)),
            "is_superadmin": bool(int(r["is_superadmin"] or 0)),
            "active": bool(int(r["active"] or 0)),
            "created_at": str(r["created_at"] or ""),
            "updated_at": str(r["updated_at"] or ""),
            "usage": {
                "users": int(user_counts.get(role_key, 0)),
                "enabled_modules": int(module_counts.get(int(r["id"]), 0)),
            },
        })
    return out


def create_role_admin(payload: dict, actor: str) -> tuple[bool, str, dict | None]:
    role_key = str(payload.get("role_key") or payload.get("roleKey") or "").strip().lower()
    display_name = str(payload.get("display_name") or payload.get("displayName") or role_key).strip()
    if not role_key:
        return False, "role_key é obrigatório", None
    if not re.fullmatch(r"[a-z0-9_\-]{2,64}", role_key):
        return False, "role_key inválido", None
    if role_key == "admin":
        return False, "role admin é reservada", None
    if not display_name:
        return False, "display_name é obrigatório", None

    now = now_iso()
    with db() as conn:
        exists = conn.execute("SELECT id FROM roles WHERE role_key=?", (role_key,)).fetchone()
        if exists:
            return False, "role já existe", None

        # criação explícita remove tombstone (permite recriar role intencionalmente)
        conn.execute("DELETE FROM deleted_roles WHERE role_key=?", (role_key,))

        conn.execute(
            """
            INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, 0, 0, 1, ?, ?, ?, ?)
            """,
            (role_key, display_name, now, now, actor, actor),
        )
        role_row = conn.execute("SELECT id FROM roles WHERE role_key=?", (role_key,)).fetchone()
        role_id = int(role_row["id"])

        # defaults: novos módulos inicialmente false
        modules = conn.execute("SELECT module_id FROM app_modules").fetchall()
        for m in modules:
            conn.execute(
                """
                INSERT OR IGNORE INTO role_module_permissions (role_id, module_id, can_access, updated_at, updated_by)
                VALUES (?, ?, 0, ?, ?)
                """,
                (role_id, str(m["module_id"]), now, actor),
            )

    return True, "ok", {"id": role_id, "role_key": role_key, "display_name": display_name}


def update_role_admin(selector: str, payload: dict, actor: str) -> tuple[bool, str, dict | None]:
    sel = str(selector or "").strip()
    if not sel:
        return False, "role inválida", None

    with db() as conn:
        if sel.isdigit():
            role_row = conn.execute("SELECT * FROM roles WHERE id=?", (int(sel),)).fetchone()
        else:
            role_row = conn.execute("SELECT * FROM roles WHERE role_key=?", (sel.lower(),)).fetchone()

        if role_row is None:
            return False, "role não encontrada", None

        role_key = str(role_row["role_key"])
        if role_key == "admin" or bool(int(role_row["is_superadmin"] or 0)):
            # apenas allow active toggle=true (no-op) and display_name same; prática: imutável
            return False, "role admin é imutável", None

        updates = []
        vals = []

        if "display_name" in payload or "displayName" in payload:
            display_name = str(payload.get("display_name") or payload.get("displayName") or "").strip()
            if not display_name:
                return False, "display_name inválido", None
            updates.append("display_name=?")
            vals.append(display_name)

        if "active" in payload:
            active = 1 if bool(payload.get("active")) else 0
            updates.append("active=?")
            vals.append(active)

        if not updates:
            return False, "nenhuma alteração informada", None

        updates.append("updated_at=?")
        vals.append(now_iso())
        updates.append("updated_by=?")
        vals.append(actor)
        vals.append(int(role_row["id"]))

        conn.execute(f"UPDATE roles SET {', '.join(updates)} WHERE id=?", tuple(vals))

        out = conn.execute("SELECT id, role_key, display_name, active FROM roles WHERE id=?", (int(role_row["id"]),)).fetchone()
    return True, "ok", dict(out) if out else None


def delete_role_admin(selector: str, actor: str, reassign_to: str | None = None) -> tuple[bool, str]:
    sel = str(selector or "").strip()
    if not sel:
        return False, "role inválida"
    reass = str(reassign_to or "").strip().lower()

    with db() as conn:
        if sel.isdigit():
            role_row = conn.execute("SELECT * FROM roles WHERE id=?", (int(sel),)).fetchone()
        else:
            role_row = conn.execute("SELECT * FROM roles WHERE role_key=?", (sel.lower(),)).fetchone()

        if role_row is None:
            return False, "role não encontrada"

        role_key = str(role_row["role_key"])
        if role_key == "admin" or bool(int(role_row["is_superadmin"] or 0)) or bool(int(role_row["is_system"] or 0)):
            return False, "role protegida não pode ser removida"

        users_count = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE LOWER(TRIM(role))=?",
                (role_key,),
            ).fetchone()["c"]
        )
        if users_count > 0:
            if not reass:
                return False, f"role em uso por {users_count} usuário(s); informe reassign_to"
            target = conn.execute("SELECT role_key FROM roles WHERE role_key=? AND active=1", (reass,)).fetchone()
            if target is None:
                return False, "reassign_to inválida"
            if reass == role_key:
                return False, "reassign_to deve ser diferente da role removida"
            conn.execute(
                "UPDATE users SET role=? WHERE LOWER(TRIM(role))=?",
                (reass, role_key),
            )

        # Limpa vínculos de permissões e legado
        conn.execute("DELETE FROM role_module_permissions WHERE role_id=?", (int(role_row["id"]),))
        conn.execute("DELETE FROM role_modules WHERE LOWER(TRIM(role_name))=?", (role_key,))

        # Remove role de projetos legados (CSV)
        project_rows = conn.execute("SELECT project_id, allowed_roles FROM projects").fetchall()
        for pr in project_rows:
            vals = [x.strip().lower() for x in str(pr["allowed_roles"] or "").split(',') if x.strip()]
            new_vals = [x for x in vals if x != role_key]
            if new_vals != vals:
                conn.execute("UPDATE projects SET allowed_roles=? WHERE project_id=?", (','.join(new_vals), int(pr["project_id"])))

        now = now_iso()
        conn.execute(
            """
            INSERT INTO deleted_roles (role_key, deleted_at, deleted_by)
            VALUES (?, ?, ?)
            ON CONFLICT(role_key) DO UPDATE SET
                deleted_at=excluded.deleted_at,
                deleted_by=excluded.deleted_by
            """,
            (role_key, now, actor),
        )

        conn.execute("DELETE FROM roles WHERE id=?", (int(role_row["id"]),))

    audit(actor, "roles.delete", role_key, json.dumps({"reassign_to": reass or None}, ensure_ascii=False))
    return True, "ok"


def list_app_modules(active_only: bool = False) -> list[dict]:
    with db() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT module_id, page_key, label, active FROM app_modules WHERE active=1 ORDER BY page_key, module_id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT module_id, page_key, label, active FROM app_modules ORDER BY page_key, module_id"
            ).fetchall()
    return [
        {
            "module_id": r["module_id"],
            "page_key": r["page_key"],
            "label": r["label"],
            "active": bool(int(r["active"] or 0)),
        }
        for r in rows
    ]


def list_role_module_matrix() -> list[dict]:
    modules = list_app_modules(active_only=False)
    module_ids = [m["module_id"] for m in modules]

    access_map: dict[tuple[str, str], bool] = {}
    with db() as conn:
        try:
            rows = conn.execute(
                """
                SELECT r.role_key AS role_name, p.module_id, p.can_access
                FROM role_module_permissions p
                JOIN roles r ON r.id = p.role_id
                """
            ).fetchall()
            for r in rows:
                access_map[(str(r["role_name"]), str(r["module_id"]))] = bool(int(r["can_access"] or 0))
        except sqlite3.OperationalError:
            # fallback legado
            rows = conn.execute(
                "SELECT role_name, module_id, can_access FROM role_modules"
            ).fetchall()
            for r in rows:
                access_map[(str(r["role_name"]), str(r["module_id"]))] = bool(int(r["can_access"] or 0))

    matrix: list[dict] = []
    for role in list_role_catalog(include_admin=True):
        role_row = {
            "role": role,
            "immutable": role == "admin",
            "permissions": {},
        }
        for module_id in module_ids:
            role_row["permissions"][module_id] = True if role == "admin" else bool(access_map.get((role, module_id), False))
        matrix.append(role_row)
    return matrix


def sync_module_catalog() -> None:
    with db() as conn:
        now = now_iso()
        for mod in MODULE_CATALOG_V1:
            conn.execute(
                """
                INSERT INTO app_modules (module_id, page_key, label, active, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(module_id) DO UPDATE SET
                    page_key=excluded.page_key,
                    label=excluded.label,
                    active=excluded.active
                """,
                (mod["module_id"], mod["page_key"], mod["label"], int(mod.get("active", 1)), now),
            )

        # Fase 1: manter role foundation e default de permissões para módulos novos
        ensure_roles_foundation(conn)

        role_rows = conn.execute("SELECT id, role_key FROM roles WHERE active=1").fetchall()
        module_rows = conn.execute("SELECT module_id FROM app_modules").fetchall()
        for rr in role_rows:
            role_id = int(rr["id"])
            role_key = str(rr["role_key"])
            for mm in module_rows:
                module_id = str(mm["module_id"])
                can_access = 1 if role_key == "admin" else 0
                conn.execute(
                    """
                    INSERT OR IGNORE INTO role_module_permissions (role_id, module_id, can_access, updated_at, updated_by)
                    VALUES (?, ?, ?, ?, 'system')
                    """,
                    (role_id, module_id, can_access, now),
                )


def get_role_module_permissions(role_name: str) -> dict[str, bool]:
    role = str(role_name or "").strip().lower()
    modules = list_app_modules(active_only=False)
    out = {m["module_id"]: False for m in modules}
    if role == "admin":
        return {k: True for k in out.keys()}

    with db() as conn:
        try:
            rows = conn.execute(
                """
                SELECT p.module_id, p.can_access
                FROM role_module_permissions p
                JOIN roles r ON r.id = p.role_id
                WHERE r.role_key=?
                """,
                (role,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT module_id, can_access FROM role_modules WHERE role_name=?",
                (role,),
            ).fetchall()

    for r in rows:
        module_id = str(r["module_id"])
        if module_id in out:
            out[module_id] = bool(int(r["can_access"] or 0))
    return out


def get_effective_permissions(user: dict | None) -> dict:
    if not user:
        return {"role": "", "roleActive": False, "allowedModules": [], "allowedPages": []}
    role = str(user.get("role") or "").strip().lower()
    if not role_is_active(role):
        return {
            "role": role,
            "roleActive": False,
            "allowedModules": [],
            "allowedPages": [],
        }

    modules = list_app_modules(active_only=True)
    mod_by_id = {m["module_id"]: m for m in modules}
    role_perms = get_role_module_permissions(role)
    allowed_modules = [mid for mid, ok in role_perms.items() if ok and mid in mod_by_id]
    allowed_pages = sorted({mod_by_id[mid]["page_key"] for mid in allowed_modules if mid in mod_by_id})
    return {
        "role": role,
        "roleActive": True,
        "allowedModules": allowed_modules,
        "allowedPages": allowed_pages,
    }


def update_role_modules(role_name: str, payload: dict, actor: str) -> tuple[bool, str]:
    role = str(role_name or "").strip().lower()
    if not role:
        return False, "role inválida"
    if not re.fullmatch(r"[a-z0-9_\-]{2,64}", role):
        return False, "role inválida"
    if role == "admin":
        return False, "role admin é imutável"

    permissions_payload = payload.get("permissions")
    normalized: dict[str, int] = {}

    if isinstance(permissions_payload, dict):
        for module_id, can_access in permissions_payload.items():
            normalized[str(module_id)] = 1 if bool(can_access) else 0
    elif isinstance(payload.get("modules"), list):
        for item in payload.get("modules"):
            if not isinstance(item, dict):
                continue
            module_id = str(item.get("module_id") or item.get("moduleId") or "").strip()
            if not module_id:
                continue
            normalized[module_id] = 1 if bool(item.get("can_access") or item.get("canAccess")) else 0
    else:
        return False, "permissions inválidas"

    if not normalized:
        return False, "nenhuma permissão informada"

    with db() as conn:
        valid_modules = {
            r["module_id"]
            for r in conn.execute("SELECT module_id FROM app_modules").fetchall()
        }
        invalid = [mid for mid in normalized.keys() if mid not in valid_modules]
        if invalid:
            return False, f"módulos inválidos: {', '.join(invalid)}"

        now = now_iso()
        role_row = conn.execute("SELECT id FROM roles WHERE role_key=?", (role,)).fetchone()
        if role_row is None:
            deleted = conn.execute("SELECT 1 FROM deleted_roles WHERE role_key=?", (role,)).fetchone()
            if deleted is not None:
                return False, "role foi removida e não pode ser recriada por atualização de permissões"
            conn.execute(
                """
                INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, 0, 0, 1, ?, ?, ?, ?)
                """,
                (role, role, now, now, actor, actor),
            )
            role_row = conn.execute("SELECT id FROM roles WHERE role_key=?", (role,)).fetchone()

        role_id = int(role_row["id"])

        for module_id, can_access in normalized.items():
            # Legado (compatibilidade)
            conn.execute(
                """
                INSERT INTO role_modules (role_name, module_id, can_access, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(role_name, module_id) DO UPDATE SET
                    can_access=excluded.can_access,
                    updated_at=excluded.updated_at,
                    updated_by=excluded.updated_by
                """,
                (role, module_id, int(can_access), now, actor),
            )

            # Novo modelo (fase 1+)
            conn.execute(
                """
                INSERT INTO role_module_permissions (role_id, module_id, can_access, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(role_id, module_id) DO UPDATE SET
                    can_access=excluded.can_access,
                    updated_at=excluded.updated_at,
                    updated_by=excluded.updated_by
                """,
                (role_id, module_id, int(can_access), now, actor),
            )

    return True, "ok"


def _normalize_allowed_roles(raw: str | list | None) -> str:
    if isinstance(raw, list):
        vals = [str(x or '').strip().lower() for x in raw]
    else:
        vals = [x.strip().lower() for x in str(raw or '').split(',')]
    known_roles = set(list_role_catalog(include_admin=True))
    allowed = [r for r in vals if r in known_roles and r != 'admin']
    # remove duplicados preservando ordem
    out: list[str] = []
    for r in allowed:
        if r not in out:
            out.append(r)
    return ','.join(out)


def parse_allowed_roles(raw: str | None) -> list[str]:
    return [r for r in _normalize_allowed_roles(raw).split(',') if r]


def project_role_allowed(project_row: dict | None, role: str) -> bool:
    normalized_role = (role or '').strip().lower()
    if normalized_role in ADMIN_EQUIV_ROLES:
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


# ---------------------------------------------------------------------------
# Registro/catálogo de projetos
# ---------------------------------------------------------------------------
def list_projects_registry() -> list[dict]:
    """
    Lista os projetos registrados no sistema.

    Retorno
    -------
    list[dict]
        Projetos normalizados para uso em catálogo, selects e páginas de gestão.

    Como deve ser usada
    -------------------
    Função de leitura para tela de projetos, navegação, Kanban e fluxos que
    precisem conhecer o catálogo atual de projetos.
    """
    with db() as conn:
        rows = conn.execute("SELECT project_id, project_name, start_date, notes, allowed_roles, is_template, template_source_project_id FROM projects ORDER BY project_id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['allowed_roles'] = _normalize_allowed_roles(d.get('allowed_roles'))
        d['is_template'] = bool(int(d.get('is_template') or 0))
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Criação de projeto no registro principal
# ---------------------------------------------------------------------------
def create_project_registry(payload: dict) -> tuple[bool, str, int | None]:
    """
    Cria um novo projeto no catálogo principal da aplicação.

    Parâmetros
    ----------
    payload:
        Dados de criação do projeto recebidos da UI/API.

    Retorno
    -------
    tuple[bool, str, int | None]
        `(ok, message, project_id)` com identificador do novo projeto em caso de sucesso.
    """
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


# ---------------------------------------------------------------------------
# Atualização de projeto existente
# ---------------------------------------------------------------------------
def update_project_registry(project_id: int, payload: dict) -> tuple[bool, str]:
    """
    Atualiza os dados de um projeto já registrado.

    Parâmetros
    ----------
    project_id:
        Projeto alvo.
    payload:
        Alterações solicitadas.

    Retorno
    -------
    tuple[bool, str]
        `(ok, message)` com resultado da operação.
    """
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


# ---------------------------------------------------------------------------
# Remoção de projeto e limpeza associada
# ---------------------------------------------------------------------------
def delete_project_registry(project_id: int) -> tuple[bool, str, int]:
    """
    Remove um projeto do registro e apaga seus artefatos associados quando aplicável.

    Parâmetros
    ----------
    project_id:
        Projeto alvo da remoção.

    Retorno
    -------
    tuple[bool, str, int]
        `(ok, message, deleted_cards)` com total de cards apagados no processo.
    """
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
            conn.execute("DELETE FROM document_dependencies WHERE document_slug=? OR depends_on_slug=?", (slug, slug))

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

    def _safe_filename(name: str, fallback: str = "documento.bin") -> str:
        clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(name or "")).strip("._")
        return clean or fallback

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
            "SELECT id, slug, name, status, priority, description, document_name, document_mime, document_path, document_status FROM documents WHERE project_id=? ORDER BY id",
            (template_project_id,),
        ).fetchall()

        now = now_iso()
        cloned_slug_map: dict[str, str] = {}
        for row in template_docs:
            d = dict(row)
            source_slug = str(d.get("slug") or "").strip()
            name = str(d.get("name") or "").strip() or "Documento"
            doc_slug = _unique_slug(conn, name)
            if source_slug:
                cloned_slug_map[source_slug] = doc_slug
            card_path = str(BASE_DIR / doc_slug)
            (BASE_DIR / doc_slug).mkdir(parents=True, exist_ok=True)

            latest_name = ""
            latest_mime = ""
            latest_abs_path = ""
            latest_status = str(d.get("document_status") or "").strip() or "aguardando edição"

            if source_slug:
                versions = conn.execute(
                    "SELECT version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum FROM document_versions WHERE document_slug=? ORDER BY version",
                    (source_slug,),
                ).fetchall()
            else:
                versions = []

            for vrow in versions:
                v = dict(vrow)
                version_num = int(v.get("version") or 0)
                if version_num <= 0:
                    continue
                src_rel = str(v.get("file_rel_path") or "").strip()
                if not src_rel:
                    continue
                src_abs = DOCS_REPO_DIR / src_rel
                if not src_abs.exists() or not src_abs.is_file():
                    continue

                version_name = _safe_filename(v.get("document_name") or src_abs.name)
                rel_path = Path("documents") / doc_slug / f"v{version_num:04d}_{version_name}"
                dst_abs = DOCS_REPO_DIR / rel_path
                dst_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_abs, dst_abs)

                checksum = str(v.get("checksum") or "").strip() or hashlib.sha256(dst_abs.read_bytes()).hexdigest()
                mime = str(v.get("document_mime") or "application/octet-stream").strip() or "application/octet-stream"
                status_for_version = str(v.get("document_status") or latest_status).strip() or latest_status

                conn.execute(
                    "INSERT INTO document_versions (document_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        doc_slug,
                        version_num,
                        version_name,
                        mime,
                        status_for_version,
                        str(rel_path),
                        "",
                        checksum,
                        actor,
                        now,
                    ),
                )

                latest_name = version_name
                latest_mime = mime
                latest_status = status_for_version
                latest_abs_path = str(dst_abs)

            if not latest_abs_path:
                source_doc_path = Path(str(d.get("document_path") or "").strip())
                if source_doc_path.exists() and source_doc_path.is_file():
                    fallback_name = _safe_filename(d.get("document_name") or source_doc_path.name)
                    rel_path = Path("documents") / doc_slug / f"v0001_{fallback_name}"
                    dst_abs = DOCS_REPO_DIR / rel_path
                    dst_abs.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_doc_path, dst_abs)

                    latest_name = fallback_name
                    latest_mime = str(d.get("document_mime") or "application/octet-stream").strip() or "application/octet-stream"
                    latest_abs_path = str(dst_abs)

                    conn.execute(
                        "INSERT INTO document_versions (document_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            doc_slug,
                            1,
                            latest_name,
                            latest_mime,
                            latest_status,
                            str(rel_path),
                            "",
                            hashlib.sha256(dst_abs.read_bytes()).hexdigest(),
                            actor,
                            now,
                        ),
                    )

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
                    card_path,
                    now,
                    latest_status,
                    latest_name,
                    latest_mime,
                    latest_abs_path,
                    actor,
                    now,
                    "",
                    new_project_id,
                ),
            )

        if cloned_slug_map:
            template_deps = conn.execute(
                "SELECT document_slug, depends_on_slug FROM document_dependencies WHERE project_id=?",
                (template_project_id,),
            ).fetchall()
            for drow in template_deps:
                src_from = str(drow["document_slug"] or "").strip()
                src_to = str(drow["depends_on_slug"] or "").strip()
                dst_from = cloned_slug_map.get(src_from)
                dst_to = cloned_slug_map.get(src_to)
                if not dst_from or not dst_to:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO document_dependencies (project_id, document_slug, depends_on_slug, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                    (new_project_id, dst_from, dst_to, actor, now),
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


# ---------------------------------------------------------------------------
# Criação de documento
# ---------------------------------------------------------------------------
def create_document(payload: dict, actor: str) -> tuple[bool, str, str | None]:
    """
    Cria um novo documento/card no sistema.

    Parâmetros
    ----------
    payload:
        Dados informados pela UI/API para criação do documento.
    actor:
        Usuário responsável pela criação.

    Retorno
    -------
    tuple[bool, str, str | None]
        `(ok, message, slug)` com o slug criado quando houver sucesso.

    Como deve ser usada
    -------------------
    Deve ser chamada por rotas de criação e por fluxos que materializam um novo
    card no Kanban. A função também integra dependências, prazos e auditoria.
    """
    name = (payload.get("name") or "").strip()
    if not name:
        return False, "Nome é obrigatório", None
    try:
        depends_on_slugs = _dependency_slugs_from_payload(payload)
    except ValueError as e:
        return False, str(e), None
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

    if depends_on_slugs is not None:
        done_deps, msg_deps = set_document_dependencies(slug, project_id, depends_on_slugs, actor)
        if not done_deps:
            with db() as conn:
                conn.execute("DELETE FROM documents WHERE slug=?", (slug,))
            try:
                shutil.rmtree(proj_dir, ignore_errors=True)
            except Exception:
                pass
            return False, msg_deps, None

    unresolved = unresolved_dependencies(slug, project_id)
    if unresolved:
        allowed, max_status = status_allowed_with_pending_dependencies(status)
        if not allowed:
            pend = ", ".join([f"{d['name']}" for d in unresolved][:5])
            with db() as conn:
                conn.execute("DELETE FROM documents WHERE slug=?", (slug,))
                conn.execute("DELETE FROM document_dependencies WHERE document_slug=?", (slug,))
            try:
                shutil.rmtree(proj_dir, ignore_errors=True)
            except Exception:
                pass
            return False, f"Não é possível criar com dependências pendentes além de '{max_status}' ({pend})", None

    sync_document_meta(document)
    return True, "ok", slug


# ---------------------------------------------------------------------------
# Atualização parcial de documento
# ---------------------------------------------------------------------------
def patch_document(slug: str, payload: dict, project_id: int | None = None, actor: str = "system") -> tuple[bool, str]:
    """
    Atualiza parcialmente um documento existente.

    Parâmetros
    ----------
    slug:
        Documento alvo.
    payload:
        Campos parciais a alterar.
    project_id:
        Escopo opcional de projeto para validação defensiva.
    actor:
        Usuário responsável pela alteração.

    Retorno
    -------
    tuple[bool, str]
        `(ok, message)` com sucesso ou motivo da rejeição.

    Como deve ser usada
    -------------------
    Principal função de edição do card. Ela deve ser chamada por rotas de edição
    e precisa manter integridade de status, dependências, prazo e auditoria.
    """
    p = get_document(slug, project_id)
    if not p:
        return False, "Documento não encontrado"

    effective_project_id = int(project_id or p.get("projectId") or 1)
    try:
        depends_on_slugs = _dependency_slugs_from_payload(payload)
    except ValueError as e:
        return False, str(e)

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

    if depends_on_slugs is not None:
        done_deps, msg_deps = set_document_dependencies(slug, effective_project_id, depends_on_slugs, actor)
        if not done_deps:
            return False, msg_deps

    pend = unresolved_dependencies(slug, effective_project_id)
    if pend:
        allowed, max_status = status_allowed_with_pending_dependencies(str(p.get("status") or "Backlog"))
        if not allowed:
            blocked = ", ".join([f"{d['name']} ({d['status']})" for d in pend][:5])
            return False, f"Card bloqueado por dependências não concluídas: máximo permitido = '{max_status}'. Pendentes: {blocked}"

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


# ---------------------------------------------------------------------------
# Leitura consolidada de configurações administrativas
# ---------------------------------------------------------------------------
def get_admin_settings() -> dict:
    """
    Lê as configurações administrativas persistidas em `app_settings`.

    Retorno
    -------
    dict
        Mapa `key -> {value, updated_by, updated_at}`.

    Como deve ser usada
    -------------------
    Base para SMTP, backup, workflow, diagnóstico, relatórios e demais áreas de
    configuração operacional.
    """
    return load_admin_settings(db)


# ---------------------------------------------------------------------------
# Atualização validada de configurações administrativas
# ---------------------------------------------------------------------------
def update_admin_settings(payload: dict, actor: str) -> tuple[bool, str]:
    """
    Atualiza configurações administrativas com validação de consistência.

    Parâmetros
    ----------
    payload:
        Conjunto de chaves/valores enviados pela UI/API.
    actor:
        Usuário responsável pela alteração.

    Retorno
    -------
    tuple[bool, str]
        `(ok, message)` indicando sucesso ou falha de validação.

    Como deve ser usada
    -------------------
    Deve ser usada por rotas administrativas; centraliza validação de payload,
    normalização e persistência.
    """
    return persist_admin_settings(db, now_iso, payload, actor)



# ---------------------------------------------------------------------------
# Catálogo de relatórios periódicos
# ---------------------------------------------------------------------------
def list_periodic_reports() -> list[dict]:
    """
    Lista os relatórios periódicos cadastrados no sistema.

    Retorno
    -------
    list[dict]
        Relatórios normalizados para uso administrativo e operacional.
    """
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


# ---------------------------------------------------------------------------
# Criação de relatório periódico
# ---------------------------------------------------------------------------
def create_periodic_report(payload: dict, actor: str) -> tuple[bool, str]:
    """
    Cria uma nova regra de relatório periódico.

    Parâmetros
    ----------
    payload:
        Configuração do relatório enviada pela UI.
    actor:
        Usuário responsável pela criação.

    Retorno
    -------
    tuple[bool, str]
        Resultado da operação.
    """
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


# ---------------------------------------------------------------------------
# Atualização de relatório periódico
# ---------------------------------------------------------------------------
def update_periodic_report(report_id: int, payload: dict, actor: str) -> tuple[bool, str]:
    """
    Atualiza uma regra já cadastrada de relatório periódico.

    Parâmetros
    ----------
    report_id:
        Relatório alvo.
    payload:
        Alterações solicitadas.
    actor:
        Usuário responsável.

    Retorno
    -------
    tuple[bool, str]
        Resultado da operação.
    """
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


# ---------------------------------------------------------------------------
# Exclusão de relatório periódico
# ---------------------------------------------------------------------------
def delete_periodic_report(report_id: int) -> tuple[bool, str]:
    """
    Remove uma regra de relatório periódico.

    Parâmetros
    ----------
    report_id:
        Identificador do relatório.

    Retorno
    -------
    tuple[bool, str]
        Resultado da operação.
    """
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


# ---------------------------------------------------------------------------
# Composição de conteúdo de relatório periódico
# ---------------------------------------------------------------------------
def compose_periodic_report_email(report: dict) -> tuple[str, str, list[sqlite3.Row]]:
    """
    Monta assunto, corpo e conjunto de linhas usadas em um relatório periódico.

    Parâmetros
    ----------
    report:
        Configuração do relatório a ser executado.

    Retorno
    -------
    tuple[str, str, list[sqlite3.Row]]
        `(subject, body, rows)` para envio e/ou pré-visualização.
    """
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


# ---------------------------------------------------------------------------
# Execução operacional de relatório periódico
# ---------------------------------------------------------------------------
def run_periodic_report(report: dict, actor: str = "system") -> tuple[bool, str]:
    """
    Executa um relatório periódico e dispara seu envio quando aplicável.

    Parâmetros
    ----------
    report:
        Configuração do relatório.
    actor:
        Usuário/ator lógico da execução.

    Retorno
    -------
    tuple[bool, str]
        Resultado da execução.
    """
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


def _backup_state(settings: dict | None = None) -> dict:
    settings = settings or get_admin_settings()
    cfg = _backup_config(settings)
    keys = ["backup.enabled", "backup.path", "backup.weekdays", "backup.run_time"]
    rows = [settings.get(k, {}) for k in keys]
    updated_at = max([str((r or {}).get("updated_at") or "") for r in rows] + [""])
    return {
        "enabled": bool(cfg.get("enabled")),
        "path": str(cfg.get("path") or ""),
        "weekdays": [str(x) for x in (cfg.get("weekdays") or [])],
        "run_time": str(cfg.get("run_time") or ""),
        "config_updated_at": updated_at,
    }


def _normalize_setting_value_for_compare(key: str, value: str) -> str:
    v = str(value or "")
    if key == "backup.enabled":
        return "true" if v.strip().lower() in {"1", "true", "yes", "on"} else "false"
    if key == "backup.path":
        return str(_resolve_backup_path(v))
    if key == "backup.weekdays":
        try:
            arr = json.loads(v)
            if not isinstance(arr, list):
                arr = []
        except Exception:
            arr = []
        clean = sorted({str(x) for x in arr if str(x) in {"0", "1", "2", "3", "4", "5", "6"}})
        return json.dumps(clean, ensure_ascii=False)
    if key == "backup.run_time":
        return v.strip()
    return v.strip()


def _backup_permission_hint(path: Path) -> str:
    p = str(path)
    return (
        f"Permissão negada em '{p}'. "
        "Sugestões: (1) use um caminho gravável pelo serviço (ex.: ./data/backups), "
        f"ou (2) ajuste permissões no Ubuntu: sudo mkdir -p {p} && sudo chown -R <usuario_servico>:<grupo_servico> {p}"
    )


def _resolve_backup_path(path_value: str | None) -> Path:
    raw = str(path_value or "").strip()
    if not raw:
        return (DATA_DIR / "backups").resolve()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (APP_DIR / p).resolve()
    return p


# ---------------------------------------------------------------------------
# Validação de permissões do caminho de backup
# ---------------------------------------------------------------------------
def test_backup_path_permissions(path_raw: str | None = None) -> tuple[bool, str, dict]:
    """
    Testa se o caminho configurado para backup existe e aceita escrita.

    Parâmetros
    ----------
    path_raw:
        Caminho opcional informado manualmente para teste.

    Retorno
    -------
    tuple[bool, str, dict]
        `(ok, message, detail)` com detalhes de existência e gravabilidade.
    """
    settings = get_admin_settings()
    cfg = _backup_config(settings)
    target = _resolve_backup_path(path_raw or cfg["path"])
    detail = {"path": str(target), "exists": False, "writable": False}

    try:
        detail["exists"] = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f".pdash-permcheck-{int(time.time())}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        detail["writable"] = True
        return True, f"Caminho de backup OK para escrita: {target}", detail
    except PermissionError:
        return False, _backup_permission_hint(target), detail
    except Exception as e:
        return False, f"Falha ao validar caminho de backup '{target}': {e}", detail


# ---------------------------------------------------------------------------
# Execução de backup do sistema
# ---------------------------------------------------------------------------
def run_system_backup(actor: str = "system", path_override: str | None = None) -> tuple[bool, str]:
    """
    Executa backup do banco e dos artefatos documentais do sistema.

    Parâmetros
    ----------
    actor:
        Usuário/ator lógico da operação.
    path_override:
        Caminho opcional para sobrescrever o destino configurado.

    Retorno
    -------
    tuple[bool, str]
        Resultado textual da operação.
    """
    settings = get_admin_settings()
    cfg = _backup_config(settings)
    primary_out_dir = _resolve_backup_path(path_override or cfg["path"])
    fallback_out_dir = (DATA_DIR / "backups").resolve()
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

# ---------------------------------------------------------------------------
# Catálogo de backups disponíveis
# ---------------------------------------------------------------------------
def list_available_backups(path_raw: str | None = None) -> tuple[bool, str, dict]:
    """
    Lista os backups disponíveis em um diretório configurado.

    Parâmetros
    ----------
    path_raw:
        Caminho opcional a ser inspecionado.

    Retorno
    -------
    tuple[bool, str, dict]
        `(ok, message, payload)` com itens agrupados por snapshot.
    """
    settings = get_admin_settings()
    cfg = _backup_config(settings)
    backup_dir = _resolve_backup_path(path_raw or cfg["path"])

    if not backup_dir.exists() or not backup_dir.is_dir():
        return True, "ok", {"path": str(backup_dir), "items": [], "total": 0}

    db_re = re.compile(r"^projectdashboard-db-(\d{8}-\d{6})\.sqlite3$")
    docs_re = re.compile(r"^projectdashboard-docs-(\d{8}-\d{6})\.tar\.gz$")

    grouped: dict[str, dict] = {}
    for p in backup_dir.iterdir():
        if not p.is_file():
            continue
        mdb = db_re.match(p.name)
        if mdb:
            stamp = mdb.group(1)
            item = grouped.setdefault(stamp, {"stamp": stamp, "db_backup": None, "docs_backup": None})
            item["db_backup"] = str(p)
            continue
        mdocs = docs_re.match(p.name)
        if mdocs:
            stamp = mdocs.group(1)
            item = grouped.setdefault(stamp, {"stamp": stamp, "db_backup": None, "docs_backup": None})
            item["docs_backup"] = str(p)

    items = [v for v in grouped.values() if v.get("db_backup")]
    items.sort(key=lambda x: x.get("stamp") or "", reverse=True)

    for it in items:
        st = str(it.get("stamp") or "")
        try:
            dt = datetime.strptime(st, "%Y%m%d-%H%M%S")
            it["when"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            it["when"] = st

    return True, "ok", {"path": str(backup_dir), "items": items, "total": len(items)}


# ---------------------------------------------------------------------------
# Cálculo do próximo backup agendado
# ---------------------------------------------------------------------------
def next_backup_run() -> dict:
    """
    Calcula a próxima janela prevista de execução automática de backup.

    Retorno
    -------
    dict
        Estrutura com estado, dias configurados, horário e próximo horário
        resolvido quando houver.
    """
    settings = get_admin_settings()
    cfg = _backup_config(settings)
    result = {
        "enabled": bool(cfg.get("enabled")),
        "weekdays": [str(x) for x in (cfg.get("weekdays") or [])],
        "run_time": str(cfg.get("run_time") or "03:00"),
        "next_run_iso": None,
        "next_run_human": None,
    }
    if not result["enabled"] or not result["weekdays"]:
        return result

    try:
        hh, mm = result["run_time"].split(":")
        hour = int(hh); minute = int(mm)
    except Exception:
        hour, minute = 3, 0

    allowed = {int(x) for x in result["weekdays"] if str(x).isdigit()}
    now = datetime.now()
    for i in range(0, 15):
        d = now + timedelta(days=i)
        if d.weekday() not in allowed:
            continue
        candidate = d.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            continue
        result["next_run_iso"] = candidate.isoformat()
        result["next_run_human"] = candidate.strftime("%Y-%m-%d %H:%M")
        break
    return result


# ---------------------------------------------------------------------------
# Restauração de backup por snapshot
# ---------------------------------------------------------------------------
def restore_backup_from_stamp(stamp: str, path_raw: str | None, actor: str) -> tuple[bool, str]:
    """
    Restaura um snapshot de backup específico.

    Parâmetros
    ----------
    stamp:
        Identificador temporal do snapshot.
    path_raw:
        Caminho opcional da origem dos backups.
    actor:
        Usuário responsável pela operação.

    Retorno
    -------
    tuple[bool, str]
        Resultado textual da restauração.
    """
    ok, msg, payload = list_available_backups(path_raw)
    if not ok:
        return False, msg

    target = None
    for it in payload.get("items", []):
        if str(it.get("stamp") or "") == str(stamp or ""):
            target = it
            break
    if not target:
        return False, "Backup selecionado não encontrado"

    db_backup = str(target.get("db_backup") or "").strip()
    docs_backup = str(target.get("docs_backup") or "").strip()
    if not db_backup:
        return False, "Backup de banco não encontrado para o snapshot selecionado"

    script = APP_DIR / "scripts" / "restore_backup.sh"
    if not script.exists():
        return False, f"Script de restore não encontrado: {script}"

    cmd = [
        str(script),
        "--db-backup", db_backup,
        "--install-dir", str(APP_DIR),
        "--allow-non-root",
    ]
    if docs_backup:
        cmd.extend(["--docs-backup", docs_backup])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as e:
        return False, f"Falha ao executar restore: {e}"

    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    detail = (out + ("\n" + err if err else "")).strip()

    if r.returncode != 0:
        return False, f"Restore falhou (code={r.returncode}). {detail[:1200]}"

    audit(actor, "system.backup.restore", str(stamp), f"path={payload.get('path')} docs={bool(docs_backup)}")
    return True, f"Restore concluído para {stamp}. {detail[:800]}"


# ---------------------------------------------------------------------------
# Diagnóstico geral do sistema
# ---------------------------------------------------------------------------
def run_system_diagnostics() -> dict:
    """
    Executa uma bateria de checks operacionais e de versão da aplicação.

    Retorno
    -------
    dict
        Estrutura com timestamp, checks e estado comparativo de versão local/remota.

    Como deve ser usada
    -------------------
    Base para a tela de diagnóstico, badge de saúde e troubleshooting operacional.
    """
    settings = get_admin_settings()
    repo_url = _setting(settings, "system.git_repo", "PDASH_GIT_REPO", "https://github.com/Vieirapa/ProjectDashboard.git")
    repo_branch = _setting(settings, "system.git_branch", "PDASH_GIT_BRANCH", "develop")

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


# ---------------------------------------------------------------------------
# Histórico de notas de revisão
# ---------------------------------------------------------------------------
def list_review_notes(slug: str) -> list[dict]:
    """
    Lista o histórico de notas de revisão de um documento.

    Parâmetros
    ----------
    slug:
        Documento alvo.

    Retorno
    -------
    list[dict]
        Notas ordenadas para exibição em histórico e tratamento operacional.
    """
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


# ---------------------------------------------------------------------------
# Inclusão de nova nota de revisão
# ---------------------------------------------------------------------------
def add_review_note(slug: str, note: str, actor: str) -> tuple[bool, str]:
    """
    Registra uma nova nota de revisão para um documento.

    Parâmetros
    ----------
    slug:
        Documento alvo.
    note:
        Texto livre da pendência/solicitação de revisão.
    actor:
        Usuário que registrou a nota.

    Retorno
    -------
    tuple[bool, str]
        `(ok, message)` para feedback operacional.

    Como deve ser usada
    -------------------
    Chamada por fluxos de revisão quando o documento está em contexto compatível
    com pendências de revisão.
    """
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


# ---------------------------------------------------------------------------
# Resolução/reabertura de nota de revisão
# ---------------------------------------------------------------------------
def set_review_note_resolution(slug: str, note_id: int, actor: str, resolved: bool) -> tuple[bool, str]:
    """
    Marca uma nota de revisão como resolvida ou volta seu estado para pendente.

    Parâmetros
    ----------
    slug:
        Documento alvo.
    note_id:
        Identificador da nota.
    actor:
        Usuário que executa a alteração.
    resolved:
        Estado final desejado (`True` para resolvido).

    Retorno
    -------
    tuple[bool, str]
        `(ok, message)` para feedback de operação.

    Como deve ser usada
    -------------------
    Deve ser chamada por fluxos de acompanhamento de revisão e precisa preservar
    rastreabilidade de quem resolveu e quando resolveu.
    """
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


# ---------------------------------------------------------------------------
# Catálogo de documentos apagados recuperáveis
# ---------------------------------------------------------------------------
def list_deleted_documents(
    q: str | None = None,
    deleted_by: str | None = None,
    deleted_from: str | None = None,
    deleted_to: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """
    Lista documentos apagados ainda elegíveis para recuperação, com filtros e paginação.

    Parâmetros
    ----------
    q:
        Busca textual por nome/slug.
    deleted_by:
        Filtro por usuário que executou a exclusão.
    deleted_from:
        Data inicial da janela de exclusão.
    deleted_to:
        Data final da janela de exclusão.
    page:
        Página atual.
    page_size:
        Quantidade de itens por página.

    Retorno
    -------
    dict
        Payload paginado para a UI administrativa de recuperação.
    """
    base_query = "FROM deleted_documents"
    where: list[str] = []
    params: list[object] = []

    qv = (q or "").strip()
    if qv:
        where.append("(name LIKE ? OR slug LIKE ?)")
        like = f"%{qv}%"
        params.extend([like, like])

    byv = (deleted_by or "").strip()
    if byv:
        where.append("LOWER(TRIM(COALESCE(deleted_by, ''))) LIKE ?")
        params.append(f"%{byv.lower()}%")

    def _normalize_date_start(raw: str | None) -> str | None:
        v = (raw or "").strip()
        if not v:
            return None
        if len(v) == 10:
            return f"{v}T00:00:00Z"
        return v

    def _normalize_date_end(raw: str | None) -> str | None:
        v = (raw or "").strip()
        if not v:
            return None
        if len(v) == 10:
            return f"{v}T23:59:59Z"
        return v

    from_v = _normalize_date_start(deleted_from)
    to_v = _normalize_date_end(deleted_to)
    if from_v:
        where.append("deleted_at >= ?")
        params.append(from_v)
    if to_v:
        where.append("deleted_at <= ?")
        params.append(to_v)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 10), 100))

    with db() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) AS c {base_query}{where_sql}", tuple(params)).fetchone()["c"])
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        safe_page = min(safe_page, total_pages)
        offset = (safe_page - 1) * safe_page_size

        rows = conn.execute(
            f"SELECT id, slug, name, deleted_at, deleted_by, trash_path {base_query}{where_sql} ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
            tuple(params) + (safe_page_size, offset),
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
    }


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


# ---------------------------------------------------------------------------
# Expurgo automático de documentos apagados vencidos
# ---------------------------------------------------------------------------
def purge_expired_deleted_documents(actor: str = "system") -> tuple[int, int]:
    """
    Remove definitivamente documentos apagados cujo período de retenção expirou.

    Parâmetros
    ----------
    actor:
        Usuário/ator lógico da operação.

    Retorno
    -------
    tuple[int, int]
        `(purged, failed)` com totais do processo.
    """
    settings = get_admin_settings()
    try:
        retention_days = int(_setting(settings, "deleted.retention_days", "PDASH_DELETED_RETENTION_DAYS", "30"))
    except Exception:
        retention_days = 30
    retention_days = max(1, min(retention_days, 3650))
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

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


# ---------------------------------------------------------------------------
# Restauração de documento apagado
# ---------------------------------------------------------------------------
def restore_deleted_document(deleted_id: int, actor: str) -> tuple[bool, str]:
    """
    Restaura um documento previamente enviado para a área recuperável.

    Parâmetros
    ----------
    deleted_id:
        Registro apagado alvo.
    actor:
        Usuário responsável pela restauração.

    Retorno
    -------
    tuple[bool, str]
        Resultado da operação.
    """
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


# ---------------------------------------------------------------------------
# Exclusão definitiva de documento já apagado
# ---------------------------------------------------------------------------
def delete_deleted_document_permanently(deleted_id: int, actor: str) -> tuple[bool, str]:
    """
    Apaga definitivamente um documento da área recuperável.

    Parâmetros
    ----------
    deleted_id:
        Registro alvo.
    actor:
        Usuário responsável.

    Retorno
    -------
    tuple[bool, str]
        Resultado da operação.
    """
    with db() as conn:
        row = conn.execute("SELECT * FROM deleted_documents WHERE id=?", (deleted_id,)).fetchone()
    if not row:
        return False, "Registro de documento apagado não encontrado"
    ok, msg = _purge_deleted_document_record(row)
    if ok:
        audit(actor, "document.deleted.purge.manual", str(deleted_id))
    return ok, msg


# ---------------------------------------------------------------------------
# Exclusão lógica de documento para área recuperável
# ---------------------------------------------------------------------------
def delete_document(slug: str, actor: str) -> tuple[bool, str]:
    """
    Remove logicamente um documento ativo, movendo-o para a área de recuperação.

    Parâmetros
    ----------
    slug:
        Documento alvo.
    actor:
        Usuário responsável pela exclusão.

    Retorno
    -------
    tuple[bool, str]
        Resultado da operação.

    Como deve ser usada
    -------------------
    Esta é a forma preferencial de remoção de documento no sistema, preservando
    restaurabilidade e trilha operacional.
    """
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
        conn.execute("DELETE FROM document_dependencies WHERE document_slug=? OR depends_on_slug=?", (slug, slug))
        conn.execute("DELETE FROM documents WHERE slug=?", (slug,))
    return True, "ok"


def get_user_profile(username: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT username, role, email, phone, extension, work_area, notes, priority_color_enabled, priority_colors_json FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if not row:
        return None

    profile = dict(row)
    default_colors = {
        "Baixa": "#dbeafe",
        "Média": "#fef3c7",
        "Alta": "#fed7aa",
        "Urgente": "#fecaca",
    }
    raw = str(profile.get("priority_colors_json") or "").strip()
    try:
        parsed = json.loads(raw) if raw else {}
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    normalized_parsed: dict[str, str] = {}
    for k, v in parsed.items():
        nk = _normalize_priority_label(str(k))
        if nk:
            normalized_parsed[nk] = str(v)

    colors = {
        "Baixa": str(normalized_parsed.get("Baixa") or default_colors["Baixa"]),
        "Média": str(normalized_parsed.get("Média") or default_colors["Média"]),
        "Alta": str(normalized_parsed.get("Alta") or default_colors["Alta"]),
        "Urgente": str(normalized_parsed.get("Urgente") or default_colors["Urgente"]),
    }

    profile["priority_color_enabled"] = bool(int(profile.get("priority_color_enabled") or 0))
    profile["priority_colors"] = colors
    profile.pop("priority_colors_json", None)
    return profile


def _normalize_priority_label(raw: str) -> str:
    v = str(raw or "").strip().lower()
    if v in {"baixa"}:
        return "Baixa"
    if v in {"media", "média"}:
        return "Média"
    if v in {"alta"}:
        return "Alta"
    if v in {"urgente"}:
        return "Urgente"
    return ""


def update_user_profile(username: str, payload: dict) -> tuple[bool, str]:
    email = str(payload.get("email") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    extension = str(payload.get("extension") or "").strip()
    work_area = str(payload.get("work_area") or "").strip()
    notes = str(payload.get("notes") or "").strip()

    if len(email) > 200 or len(phone) > 80 or len(extension) > 40 or len(work_area) > 120 or len(notes) > 4000:
        return False, "Campos do perfil excedem o limite permitido"

    priority_color_enabled = bool(payload.get("priority_color_enabled"))
    default_colors = {
        "Baixa": "#dbeafe",
        "Média": "#fef3c7",
        "Alta": "#fed7aa",
        "Urgente": "#fecaca",
    }
    incoming_colors = payload.get("priority_colors") or {}
    if not isinstance(incoming_colors, dict):
        incoming_colors = {}

    normalized_incoming: dict[str, str] = {}
    for raw_k, raw_v in incoming_colors.items():
        nk = _normalize_priority_label(str(raw_k))
        if nk:
            normalized_incoming[nk] = str(raw_v)

    colors = {}
    for key in ["Baixa", "Média", "Alta", "Urgente"]:
        value = str(normalized_incoming.get(key) or default_colors[key]).strip()
        if not re.match(r"^#[0-9a-fA-F]{6}$", value):
            return False, f"Cor inválida para prioridade {key}"
        colors[key] = value

    with db() as conn:
        row = conn.execute("SELECT username FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return False, "Usuário não encontrado"
        conn.execute(
            "UPDATE users SET email=?, phone=?, extension=?, work_area=?, notes=?, priority_color_enabled=?, priority_colors_json=? WHERE username=?",
            (email, phone, extension, work_area, notes, int(priority_color_enabled), json.dumps(colors, ensure_ascii=False), username),
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
    return create_auth_session(SESSIONS, SESSION_TTL_SECONDS, username, role)


def current_user_from_cookie(raw_cookie: str | None) -> dict | None:
    return current_user_from_session_cookie(SESSIONS, SESSION_COOKIE, raw_cookie)


# ---------------------------------------------------------------------------
# Handler HTTP principal da aplicação
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    """
    Handler HTTP central do ProjectDashboard.

    Papel desta classe
    ------------------
    Esta classe concentra o ciclo de atendimento HTTP da aplicação, incluindo:
    - leitura de sessão/cookie
    - autorização por página e módulo
    - entrega de assets estáticos
    - dispatch de endpoints HTML e API
    - serialização de respostas JSON

    Como ela deve ser tratada no restante do programa
    -----------------------------------------------
    - Regras de negócio não devem crescer desnecessariamente dentro do Handler.
    - Sempre que possível, o Handler deve delegar para funções/módulos de domínio.
    - O Handler deve atuar principalmente como camada de transporte, autenticação,
      validação de acesso e composição de resposta.
    """

    # -----------------------------------------------------------------------
    # Resposta JSON padrão
    # -----------------------------------------------------------------------
    def _json(self, code: int, payload: dict, set_cookie: str | None = None):
        """
        Envia uma resposta JSON HTTP padronizada.

        Parâmetros
        ----------
        code:
            Status HTTP da resposta.
        payload:
            Dicionário serializável para JSON.
        set_cookie:
            Cookie opcional a ser anexado ao header da resposta.

        Retorno
        -------
        None

        Como deve ser usada
        -------------------
        É o helper padrão para respostas de API. Deve ser preferido em vez de
        escrita manual repetitiva no socket HTTP.
        """
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -----------------------------------------------------------------------
    # Entrega de arquivo estático/HTML
    # -----------------------------------------------------------------------
    def _serve(self, path: Path, content_type: str):
        """
        Entrega um arquivo estático/HTML com headers de cache desabilitado.

        Parâmetros
        ----------
        path:
            Caminho do arquivo a servir.
        content_type:
            MIME type da resposta.

        Retorno
        -------
        None

        Como deve ser usada
        -------------------
        Helper interno para páginas HTML, JS e CSS. Mantém o frontend sem cache
        agressivo durante desenvolvimento e rollout iterativo.
        """
        if not path.exists():
            self.send_error(404); return
        b = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        # Avoid stale frontend assets during iterative rollout/debug.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    # -----------------------------------------------------------------------
    # Leitura de payload JSON da requisição
    # -----------------------------------------------------------------------
    def _read_json(self):
        """
        Lê e faz parse do corpo JSON da requisição atual.

        Retorno
        -------
        tuple[bool, dict]
            `(ok, payload)` com o dicionário parseado ou mensagem de erro.

        Como deve ser usada
        -------------------
        Deve ser usada por rotas POST/PATCH/DELETE que esperam JSON no body.
        """
        l = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(l).decode("utf-8") if l else "{}"
        try:
            return True, json.loads(raw)
        except Exception:
            return False, {"error": "JSON inválido"}

    # -----------------------------------------------------------------------
    # Resolução do usuário autenticado
    # -----------------------------------------------------------------------
    def _user(self):
        """
        Resolve o usuário autenticado a partir do cookie da requisição atual.

        Retorno
        -------
        dict | None
            Estrutura de usuário autenticado ou `None`.
        """
        return current_user_from_cookie(self.headers.get("Cookie"))

    def _is_user_role_active(self, user: dict | None = None) -> bool:
        u = user or self._user()
        if not u:
            return False
        return role_is_active(u.get("role") or "")

    def _inactive_role_payload(self, user: dict | None) -> dict:
        username = ""
        role = ""
        if user:
            username = str(user.get("username") or "")
            role = str(user.get("role") or "")
        return {
            "ok": False,
            "error": "role_inactive",
            "message": "Os privilégios de acesso deste usuário estão inativados temporariamente. Entre em contato com o administrador do sistema.",
            "user": {"username": username, "role": role},
        }

    # -----------------------------------------------------------------------
    # Guarda de autenticação
    # -----------------------------------------------------------------------
    def _require_auth(self, allow_inactive: bool = False):
        """
        Garante que a rota atual só prossiga com usuário autenticado.

        Parâmetros
        ----------
        allow_inactive:
            Quando `True`, permite usuário autenticado com role inativa.

        Retorno
        -------
        dict | None
            Usuário autenticado enriquecido com `role_active`, ou `None` quando
            a requisição já foi respondida com erro.
        """
        u = self._user()
        if not u:
            self._json(401, {"ok": False, "error": "unauthorized"})
            return None
        is_active = self._is_user_role_active(u)
        merged = {**u, "role_active": is_active}
        if not is_active and not allow_inactive:
            self._json(403, self._inactive_role_payload(merged))
            return None
        return merged

    # -----------------------------------------------------------------------
    # Guarda de administração equivalente
    # -----------------------------------------------------------------------
    def _require_admin(self):
        """
        Garante que o usuário atual tenha um role administrativo equivalente.

        Retorno
        -------
        dict | None
            Usuário autenticado quando autorizado; `None` quando a requisição já
            foi encerrada com erro de autenticação/autorização.
        """
        u = self._require_auth()
        if not u: return None
        if (u.get("role") or "").strip().lower() not in ADMIN_EQUIV_ROLES:
            self._json(403, {"ok": False, "error": "forbidden"}); return None
        return u

    # -----------------------------------------------------------------------
    # Guarda de admin raiz
    # -----------------------------------------------------------------------
    def _require_root_admin(self):
        """
        Garante que o usuário atual seja exatamente o role `admin` raiz.

        Retorno
        -------
        dict | None
            Usuário autenticado quando permitido; `None` em caso contrário.
        """
        u = self._require_auth()
        if not u: return None
        if (u.get("role") or "").strip().lower() != "admin":
            self._json(403, {"ok": False, "error": "forbidden"}); return None
        return u

    # -----------------------------------------------------------------------
    # Guarda de acesso por módulo
    # -----------------------------------------------------------------------
    def _require_module(self, module_id: str):
        """
        Garante que o usuário atual possua acesso ao módulo informado.

        Parâmetros
        ----------
        module_id:
            Identificador lógico do módulo protegido.

        Retorno
        -------
        dict | None
            Usuário autenticado quando autorizado; `None` caso contrário.
        """
        u = self._require_auth()
        if not u:
            return None
        if not self._has_module_access(module_id, u):
            self._json(403, {"ok": False, "error": "forbidden"})
            return None
        return u

    # -----------------------------------------------------------------------
    # Guarda de acesso por lista de módulos
    # -----------------------------------------------------------------------
    def _require_any_module(self, module_ids: list[str]):
        """
        Garante que o usuário atual tenha acesso a pelo menos um dos módulos informados.

        Parâmetros
        ----------
        module_ids:
            Lista de módulos aceitos pela rota.

        Retorno
        -------
        dict | None
            Usuário autenticado quando autorizado; `None` caso contrário.
        """
        u = self._require_auth()
        if not u:
            return None
        for module_id in module_ids:
            if self._has_module_access(module_id, u):
                return u
        self._json(403, {"ok": False, "error": "forbidden"})
        return None

    def _can_manage_setting_keys(self, user: dict, keys: list[str]) -> tuple[bool, str | None]:
        # defensive canonicalization to tolerate cached/legacy frontend payload variations
        canonical_map = {re.sub(r"[^a-z0-9._-]", "", str(k).strip().lower()): v for k, v in SETTING_KEY_TO_MODULE.items()}

        for key in keys:
            raw_key = str(key or "")
            normalized_key = raw_key.strip()
            canonical_key = re.sub(r"[^a-z0-9._-]", "", normalized_key.lower())

            module_id = SETTING_KEY_TO_MODULE.get(normalized_key) or canonical_map.get(canonical_key)
            if not module_id:
                return False, f"chave de configuração não mapeada: {normalized_key}"
            if not self._has_module_access(module_id, user):
                return False, f"forbidden: {normalized_key}"
        return True, None

    def _projects_for_user(self, user: dict | None) -> list[dict]:
        all_projects = list_projects_registry()
        if not user:
            return all_projects
        role = (user.get("role") or "").strip().lower()
        if role in ADMIN_EQUIV_ROLES:
            return all_projects
        return [p for p in all_projects if project_role_allowed(p, role)]

    def _project_by_id(self, project_id: int) -> dict | None:
        return next((p for p in list_projects_registry() if int(p.get("project_id") or 0) == int(project_id)), None)

    def _effective_permissions(self, user: dict | None = None) -> dict:
        return get_effective_permissions(user or self._user())

    def _has_module_access(self, module_id: str, user: dict | None = None) -> bool:
        user = user or self._user()
        if not user:
            return False
        perms = self._effective_permissions(user)
        return module_id in set(perms.get("allowedModules") or [])

    def _can_open_page(self, page_key: str, user: dict | None = None) -> bool:
        user = user or self._user()
        if not user:
            return False
        perms = self._effective_permissions(user)
        return page_key in set(perms.get("allowedPages") or [])

    def _project_access_error(self, project_id: int, user: dict | None) -> str:
        if not user:
            return "Autenticação necessária."
        if (user.get("role") or "").strip().lower() in ADMIN_EQUIV_ROLES:
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
        if (user.get("role") or "").strip().lower() in ADMIN_EQUIV_ROLES:
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

    # -----------------------------------------------------------------------
    # Dispatch principal de rotas GET
    # -----------------------------------------------------------------------
    def do_GET(self):
        """
        Processa requisições HTTP GET.

        O que este método faz
        ---------------------
        - resolve path e query string
        - aplica lógica de autenticação/role inativa
        - entrega páginas HTML e assets estáticos
        - expõe endpoints de leitura via API

        Como deve ser tratado no restante do programa
        ---------------------------------------------
        Idealmente deve permanecer como dispatch/orquestração, delegando para
        funções de domínio e helpers específicos sempre que a lógica crescer.
        """
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)

        u = self._user()
        is_inactive = bool(u) and (not self._is_user_role_active(u))

        if p == "/inactive.html":
            return self._serve(WEB_DIR / "inactive.html", "text/html; charset=utf-8")

        if is_inactive and p in [
            "/", "/index.html", "/kanban.html", "/edit.html", "/projects.html", "/admin-users.html", "/profile.html", "/settings.html"
        ]:
            self.send_response(302)
            self.send_header("Location", "/inactive.html")
            self.end_headers()
            return

        if p in ["/", "/index.html"]: return self._serve(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if p == "/login.html": return self._serve(WEB_DIR / "login.html", "text/html; charset=utf-8")
        if p == "/signup.html": return self._serve(WEB_DIR / "signup.html", "text/html; charset=utf-8")
        if p == "/kanban.html": return self._serve(WEB_DIR / "kanban.html", "text/html; charset=utf-8")
        if p == "/edit.html": return self._serve(WEB_DIR / "edit.html", "text/html; charset=utf-8")
        if p == "/projects.html":
            u = self._user()
            if not u or not self._can_open_page("projects.html", u):
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            return self._serve(WEB_DIR / "projects.html", "text/html; charset=utf-8")
        if p == "/admin-users.html":
            u = self._user()
            if not u or not self._can_open_page("admin-users.html", u):
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            return self._serve(WEB_DIR / "admin-users.html", "text/html; charset=utf-8")
        if p == "/profile.html": return self._serve(WEB_DIR / "profile.html", "text/html; charset=utf-8")
        if p == "/settings.html":
            u = self._user()
            if not u or not self._can_open_page("settings.html", u):
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
            if not u:
                return self._json(401, {"ok": False, "user": None})
            active = self._is_user_role_active(u)
            return self._json(200, {
                "ok": True,
                "user": {
                    "username": u["username"],
                    "role": u["role"],
                    "role_active": active,
                },
                "role_active": active,
                "inactive_message": None if active else "Os privilégios de acesso deste usuário estão inativados temporariamente. Entre em contato com o administrador do sistema.",
            })

        if p == "/api/me/permissions":
            u = self._require_auth(allow_inactive=True)
            if not u: return
            perms = self._effective_permissions(u)
            if not bool(u.get("role_active")):
                return self._json(200, {
                    "ok": True,
                    "permissions": perms,
                    "role_active": False,
                    "inactive_message": "Os privilégios de acesso deste usuário estão inativados temporariamente. Entre em contato com o administrador do sistema.",
                })
            return self._json(200, {"ok": True, "permissions": perms, "role_active": True})

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
                "dependencyMaxStatus": dependency_max_status(),
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
            return self._json(200, {"ok": True, "document": doc, "statuses": STATUSES, "priorities": PRIORITIES, "users": list_usernames(), "dependencyMaxStatus": dependency_max_status()})

        if p == "/api/projects-registry":
            user = self._require_auth()
            if not user: return
            return self._json(200, {"ok": True, "projects": self._projects_for_user(user)})

        if p == "/api/admin/projects":
            if not self._require_module("projects.create_edit"): return
            return self._json(200, {"ok": True, "projects": list_projects_registry()})

        if p == "/api/admin/users":
            user = self._require_auth()
            if not user: return
            if not self._has_module_access("admin_users.list", user):
                return self._json(403, {"ok": False, "error": "forbidden"})
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
            return self._json(200, {"ok": True, "users": users, "roles": list_role_catalog(include_admin=True)})

        if p == "/api/admin/roles":
            user = self._require_auth()
            if not user: return
            can_view = self._has_module_access("projects.create_edit", user)
            if not can_view:
                return self._json(403, {"ok": False, "error": "forbidden"})
            items = list_roles_admin_view()
            return self._json(200, {
                "ok": True,
                "roles": [r["role_key"] for r in items if r.get("role_key") != "admin" and bool(r.get("active", True))],
                "items": items,
                "can_manage": (str(user.get("role") or "").strip().lower() == "admin"),
            })

        if p == "/api/admin/settings":
            if not self._require_any_module(["settings.smtp", "settings.system_behavior", "settings.backup", "settings.system_diagnostics", "settings.recoverable_documents"]): return
            return self._json(200, {"ok": True, "settings": get_admin_settings()})

        if p == "/api/modules/catalog":
            if not self._require_root_admin(): return
            return self._json(200, {"ok": True, "modules": list_app_modules(active_only=False)})

        if p == "/api/roles/modules":
            if not self._require_root_admin(): return
            return self._json(200, {
                "ok": True,
                "roles": list_role_catalog(include_admin=True),
                "modules": list_app_modules(active_only=False),
                "matrix": list_role_module_matrix(),
            })

        if p == "/api/admin/reports":
            if not self._require_module("settings.periodic_reports"): return
            return self._json(200, {"ok": True, "reports": list_periodic_reports(), "statuses": STATUSES, "roles": list_role_catalog(include_admin=True), "priorities": ["TODOS", *PRIORITIES]})

        if p == "/api/admin/audit":
            user = self._require_auth()
            if not user: return
            if not self._has_module_access("admin_users.audit_log", user):
                return self._json(403, {"ok": False, "error": "forbidden"})
            return self._json(200, {"ok": True, "logs": list_audit_logs(300)})

        if p == "/api/admin/deleted-documents":
            if not self._require_module("settings.recoverable_documents"): return
            settings = get_admin_settings()
            retention_days = _setting(settings, "deleted.retention_days", "PDASH_DELETED_RETENTION_DAYS", "30")
            q = (qs.get("q", [""])[0] or "").strip()
            deleted_by = (
                (qs.get("deleted_by", [""])[0] or "").strip()
                or (qs.get("deletedBy", [""])[0] or "").strip()
                or (qs.get("by", [""])[0] or "").strip()
            )
            deleted_from = (
                (qs.get("deleted_from", [""])[0] or "").strip()
                or (qs.get("deletedFrom", [""])[0] or "").strip()
            )
            deleted_to = (
                (qs.get("deleted_to", [""])[0] or "").strip()
                or (qs.get("deletedTo", [""])[0] or "").strip()
            )
            try:
                page = int((qs.get("page", ["1"])[0] or "1").strip())
            except Exception:
                page = 1
            try:
                page_size = int((qs.get("page_size", ["10"])[0] or "10").strip())
            except Exception:
                page_size = 10

            data = list_deleted_documents(
                q=q,
                deleted_by=deleted_by,
                deleted_from=deleted_from,
                deleted_to=deleted_to,
                page=page,
                page_size=page_size,
            )

            return self._json(200, {
                "ok": True,
                "retention_days": retention_days,
                "filters": {
                    "q": q,
                    "deleted_by": deleted_by,
                    "deleted_from": deleted_from,
                    "deleted_to": deleted_to,
                },
                "deleted_documents": data["items"],
                "total": data["total"],
                "page": data["page"],
                "page_size": data["page_size"],
                "total_pages": data["total_pages"],
            })

        if p == "/api/admin/system/diagnostics":
            if not self._require_module("settings.system_diagnostics"): return
            return self._json(200, {"ok": True, "diagnostics": run_system_diagnostics()})

        if p == "/api/admin/system/backup/available":
            if not self._require_module("settings.backup_restore"): return
            path_raw = (qs.get("path", [""])[0] or "").strip() or None
            done, msg, data = list_available_backups(path_raw)
            return self._json(200 if done else 400, {
                "ok": done,
                "path": data.get("path") if done else None,
                "items": data.get("items") if done else [],
                "total": data.get("total") if done else 0,
                "error": None if done else msg,
            })

        if p == "/api/admin/system/backup/next-run":
            if not self._require_module("settings.backup"): return
            return self._json(200, {"ok": True, "schedule": next_backup_run()})

        self.send_error(404)

    # -----------------------------------------------------------------------
    # Dispatch principal de rotas POST
    # -----------------------------------------------------------------------
    def do_POST(self):
        """
        Processa requisições HTTP POST.

        O que este método faz
        ---------------------
        Trata fluxos de criação, autenticação, ações administrativas e operações
        que geram efeitos colaterais no sistema.
        """
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
            role_active = role_is_active(row["role"])
            return self._json(200, {
                "ok": True,
                "user": {
                    "username": row["username"],
                    "role": row["role"],
                    "role_active": role_active,
                },
                "role_active": role_active,
                "inactive_message": None if role_active else "Os privilégios de acesso deste usuário estão inativados temporariamente. Entre em contato com o administrador do sistema.",
            }, set_cookie=cookie)

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
            can_via_module = self._has_module_access("projects.cards_list", user)
            if not (can_create_document(user["role"]) or can_via_module):
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
            can_via_module = self._has_module_access("projects.cards_list", user)
            if not (can_upload_document(user["role"]) or can_via_module):
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
            can_via_module = self._has_module_access("projects.cards_list", user)
            if not (can_add_review_note(user["role"]) or can_via_module):
                return self._json(403, {"ok": False, "error": "Sem permissão para adicionar nota de revisão"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = add_review_note(slug, body.get("note") or "", user["username"])
            if done:
                audit(user["username"], "document.review_note.create", slug, "note_added")
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p == "/api/admin/settings/test-smtp":
            admin = self._require_module("settings.smtp")
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
            admin = self._require_module("settings.backup")
            if not admin: return
            ok, body = self._read_json()
            if not ok:
                body = {}
            path_raw = str((body or {}).get("path") or "").strip() or None
            done, msg = run_system_backup(admin["username"], path_raw)
            return self._json(200 if done else 400, {"ok": done, "message": msg if done else None, "error": None if done else msg})

        if p == "/api/admin/system/backup/test-path":
            admin = self._require_module("settings.backup")
            if not admin: return
            ok, body = self._read_json()
            if not ok:
                body = {}
            path_raw = str((body or {}).get("path") or "").strip() or None
            done, msg, detail = test_backup_path_permissions(path_raw)
            return self._json(200 if done else 400, {
                "ok": done,
                "message": msg if done else None,
                "error": None if done else msg,
                "detail": detail,
            })

        if p == "/api/admin/system/backup/restore":
            admin = self._require_module("settings.backup_restore")
            if not admin: return
            ok, body = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": body.get("error") or "JSON inválido"})

            stamp = str((body or {}).get("stamp") or "").strip()
            path_raw = str((body or {}).get("path") or "").strip() or None
            confirm = str((body or {}).get("confirm_text") or "").strip().upper()

            if not stamp:
                return self._json(400, {"ok": False, "error": "Stamp do backup é obrigatório"})
            if confirm != "RESTAURAR":
                return self._json(400, {"ok": False, "error": "Confirmação obrigatória: digite RESTAURAR"})

            done, msg = restore_backup_from_stamp(stamp, path_raw, admin["username"])
            return self._json(200 if done else 400, {"ok": done, "message": msg if done else None, "error": None if done else msg})

        if p.startswith("/api/admin/deleted-documents/") and p.endswith("/restore"):
            admin = self._require_module("settings.recoverable_documents")
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
            admin = self._require_module("settings.periodic_reports")
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = create_periodic_report(body, admin["username"])
            if done:
                audit(admin["username"], "report.periodic.create", body.get("name", ""))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/reports/") and p.endswith("/run"):
            admin = self._require_module("settings.periodic_reports")
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
            admin = self._require_module("projects.create_edit")
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg, new_project_id = create_project_registry(body)
            if done:
                audit(admin["username"], "project.registry.create", body.get("project_name", ""))
            return self._json(200 if done else 400, {"ok": done, "project_id": new_project_id if done else None, "error": None if done else msg})

        if p.startswith("/api/admin/projects/") and p.endswith("/clone"):
            admin = self._require_module("projects.create_edit")
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

        if p == "/api/admin/roles":
            admin = self._require_root_admin()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            done, msg, data = create_role_admin(body or {}, admin["username"])
            if done:
                audit(admin["username"], "roles.create", str(data.get("role_key") if data else ""), json.dumps(data or {}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg, "role": data if done else None})

        if p == "/api/admin/users":
            admin = self._require_auth()
            if not admin: return
            if not self._has_module_access("admin_users.create", admin):
                return self._json(403, {"ok": False, "error": "forbidden"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            username = (body.get("username") or "").strip()
            password = body.get("password") or ""
            requested_role = str(body.get("role") or "").strip().lower()
            role = requested_role if role_exists(requested_role, active_only=True) else resolve_fallback_role("member")
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
            admin = self._require_auth()
            if not admin: return
            if not self._has_module_access("admin_users.invite", admin):
                return self._json(403, {"ok": False, "error": "forbidden"})
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            requested_role = str(body.get("role") or "").strip().lower()
            role = requested_role if role_exists(requested_role, active_only=True) else resolve_fallback_role("member")
            token = secrets.token_urlsafe(24)
            exp = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
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

        if p == "/api/modules/catalog/sync":
            admin = self._require_root_admin()
            if not admin: return
            sync_module_catalog()
            audit(admin["username"], "modules.catalog.sync", "app_modules")
            return self._json(200, {"ok": True, "modules": list_app_modules(active_only=False)})

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
                if datetime.fromisoformat(inv["expires_at"].replace("Z", "+00:00")) < datetime.now(UTC):
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

    # -----------------------------------------------------------------------
    # Dispatch principal de rotas PATCH
    # -----------------------------------------------------------------------
    def do_PATCH(self):
        """
        Processa requisições HTTP PATCH.

        O que este método faz
        ---------------------
        Trata atualizações parciais de recursos existentes, principalmente em
        rotas de edição incremental de documentos, projetos, settings e afins.
        """
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
            admin = self._require_auth()
            if not admin: return
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})
            keys = list((body or {}).keys())
            allowed, reason = self._can_manage_setting_keys(admin, keys)
            if not allowed:
                return self._json(403, {"ok": False, "error": reason or "forbidden"})
            done, msg = update_admin_settings(body, admin["username"])
            if done:
                audit(admin["username"], "admin.settings.update", "app_settings", json.dumps({k: ("***" if "pass" in k else v) for k, v in body.items()}, ensure_ascii=False))
                settings_now = get_admin_settings()
                backup_state = _backup_state(settings_now)

                mismatches: list[dict] = []
                for key, sent_value in (body or {}).items():
                    persisted_raw = settings_now.get(key, {}).get("value", "")
                    sent_norm = _normalize_setting_value_for_compare(str(key), str(sent_value))
                    persisted_norm = _normalize_setting_value_for_compare(str(key), str(persisted_raw))
                    if sent_norm != persisted_norm:
                        mismatches.append({
                            "key": str(key),
                            "sent": sent_norm,
                            "persisted": persisted_norm,
                        })

                return self._json(200, {
                    "ok": True,
                    "error": None,
                    "settings": settings_now,
                    "saved": {
                        "backup": backup_state,
                    },
                    "mismatch": mismatches,
                })
            return self._json(400, {"ok": False, "error": msg, "settings": None})

        if p.startswith("/api/admin/roles/"):
            admin = self._require_root_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 4:
                return self._json(404, {"ok": False, "error": "not found"})
            selector = str(parts[3] or "").strip()
            ok, body = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": body["error"]})
            done, msg, data = update_role_admin(selector, body or {}, admin["username"])
            if done:
                audit(admin["username"], "roles.update", selector, json.dumps(data or {}, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg, "role": data if done else None})

        if p.startswith("/api/roles/") and p.endswith("/modules"):
            admin = self._require_root_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 4:
                return self._json(404, {"ok": False, "error": "not found"})
            role_name = str(parts[2] or "").strip().lower()
            ok, body = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": body["error"]})
            done, msg = update_role_modules(role_name, body, admin["username"])
            if done:
                audit(admin["username"], "roles.modules.updated", role_name)
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

            can_via_module = self._has_module_access("projects.cards_list", user)
            if not (can_resolve_review_note(user["role"]) or can_via_module):
                return self._json(403, {"ok": False, "error": "Sem permissão para alterar status da revisão"})

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
            can_via_module = self._has_module_access("projects.cards_list", user)
            if not (can_edit_document(user["role"]) or can_via_module):
                return self._json(403, {"ok": False, "error": "Sem permissão para editar documento"})
            slug = p.split("/")[3]
            if not self._get_document_in_scope(slug, qs, user):
                return self._reply_document_scope_error(slug, qs, user)
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})

            done, msg = patch_document(slug, body, self._selected_project_id(qs, user), user["username"])
            if done:
                audit(user["username"], "document.update", slug, json.dumps(body, ensure_ascii=False))
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

        if p.startswith("/api/admin/reports/"):
            admin = self._require_module("settings.periodic_reports")
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
            admin = self._require_module("projects.create_edit")
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
            admin = self._require_auth()
            if not admin: return
            if not self._has_module_access("admin_users.create", admin):
                return self._json(403, {"ok": False, "error": "forbidden"})
            username = p.split("/")[4]
            ok, body = self._read_json()
            if not ok: return self._json(400, {"ok": False, "error": body["error"]})

            updates = []
            params = []
            if "role" in body:
                role = str(body.get("role") or "").strip().lower()
                if not role_exists(role, active_only=True):
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

    # -----------------------------------------------------------------------
    # Dispatch principal de rotas DELETE
    # -----------------------------------------------------------------------
    def do_DELETE(self):
        """
        Processa requisições HTTP DELETE.

        O que este método faz
        ---------------------
        Trata remoções lógicas ou administrativas de recursos, sempre respeitando
        autenticação, autorização e rotinas de auditoria quando aplicável.
        """
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)

        if p.startswith("/api/admin/roles/"):
            admin = self._require_root_admin()
            if not admin: return
            parts = p.strip("/").split("/")
            if len(parts) != 4:
                return self._json(404, {"ok": False, "error": "not found"})
            selector = str(parts[3] or "").strip()
            reassign_to = (qs.get("reassign_to", [""])[0] or "").strip().lower()
            done, msg = delete_role_admin(selector, admin["username"], reassign_to or None)
            return self._json(200 if done else 400, {"ok": done, "error": None if done else msg})

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
            admin = self._require_module("settings.recoverable_documents")
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
            admin = self._require_module("settings.periodic_reports")
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
            admin = self._require_module("projects.create_edit")
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
            admin = self._require_auth()
            if not admin: return
            if not self._has_module_access("admin_users.create", admin):
                return self._json(403, {"ok": False, "error": "forbidden"})
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
