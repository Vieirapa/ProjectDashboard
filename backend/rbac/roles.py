from __future__ import annotations

import sqlite3
from collections.abc import Callable


def list_role_catalog(
    db_factory: Callable[[], sqlite3.Connection],
    default_roles: list[str],
    include_admin: bool = True,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def add_role(value: str | None):
        role = str(value or '').strip().lower()
        if not role or role in seen:
            return
        seen.add(role)
        out.append(role)

    with db_factory() as conn:
        role_rows = conn.execute(
            "SELECT role_key FROM roles WHERE active=1 ORDER BY id"
        ).fetchall()
        if role_rows:
            for r in role_rows:
                add_role(r['role_key'])
        else:
            for role in default_roles:
                add_role(role)

            user_roles = conn.execute(
                "SELECT DISTINCT role FROM users WHERE role IS NOT NULL AND TRIM(role)<>''"
            ).fetchall()
            module_roles = conn.execute(
                "SELECT DISTINCT role_name FROM role_modules WHERE role_name IS NOT NULL AND TRIM(role_name)<>''"
            ).fetchall()
            project_roles = conn.execute(
                "SELECT DISTINCT allowed_roles FROM projects WHERE allowed_roles IS NOT NULL AND TRIM(allowed_roles)<>''"
            ).fetchall()

            for r in user_roles:
                add_role(r['role'])
            for r in module_roles:
                add_role(r['role_name'])
            for r in project_roles:
                for role in str(r['allowed_roles'] or '').split(','):
                    add_role(role)

    if include_admin:
        return out
    return [r for r in out if r != 'admin']


def role_exists(
    db_factory: Callable[[], sqlite3.Connection],
    role_key: str,
    active_only: bool = True,
) -> bool:
    role = str(role_key or '').strip().lower()
    if not role:
        return False
    with db_factory() as conn:
        if active_only:
            row = conn.execute('SELECT 1 FROM roles WHERE role_key=? AND active=1', (role,)).fetchone()
        else:
            row = conn.execute('SELECT 1 FROM roles WHERE role_key=?', (role,)).fetchone()
    return row is not None


def role_is_active(
    db_factory: Callable[[], sqlite3.Connection],
    role_key: str,
    default_roles: list[str],
) -> bool:
    role = str(role_key or '').strip().lower()
    if not role:
        return False
    try:
        with db_factory() as conn:
            row = conn.execute('SELECT active FROM roles WHERE role_key=?', (role,)).fetchone()
            if row is None:
                return False
            return bool(int(row['active'] or 0))
    except sqlite3.OperationalError:
        return role in {r.lower() for r in default_roles}


def resolve_fallback_role(
    db_factory: Callable[[], sqlite3.Connection],
    preferred: str = 'member',
) -> str:
    pref = str(preferred or '').strip().lower()
    with db_factory() as conn:
        if pref:
            row = conn.execute('SELECT role_key FROM roles WHERE role_key=? AND active=1', (pref,)).fetchone()
            if row:
                return str(row['role_key'])

        row = conn.execute(
            "SELECT role_key FROM roles WHERE active=1 AND role_key!='admin' ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            return str(row['role_key'])

        admin_row = conn.execute("SELECT role_key FROM roles WHERE role_key='admin' LIMIT 1").fetchone()
        if admin_row:
            return str(admin_row['role_key'])

    return 'admin'
