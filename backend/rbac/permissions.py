from __future__ import annotations

"""
backend.rbac.permissions
========================

Operações de RBAC ligadas a permissões efetivas, páginas permitidas e atualização
administrativa da matriz role-module.
"""

import re
import sqlite3
from collections.abc import Callable


def get_effective_permissions(role_is_active_fn, list_app_modules_fn, get_role_module_permissions_fn, user: dict | None) -> dict:
    if not user:
        return {'role': '', 'roleActive': False, 'allowedModules': [], 'allowedPages': []}
    role = str(user.get('role') or '').strip().lower()
    if not role_is_active_fn(role):
        return {'role': role, 'roleActive': False, 'allowedModules': [], 'allowedPages': []}
    modules = list_app_modules_fn(active_only=True)
    mod_by_id = {m['module_id']: m for m in modules}
    role_perms = get_role_module_permissions_fn(role)
    allowed_modules = [mid for mid, ok in role_perms.items() if ok and mid in mod_by_id]
    allowed_pages = sorted({mod_by_id[mid]['page_key'] for mid in allowed_modules if mid in mod_by_id})
    return {
        'role': role,
        'roleActive': True,
        'allowedModules': allowed_modules,
        'allowedPages': allowed_pages,
    }


def update_role_modules(db_factory: Callable[[], sqlite3.Connection], now_iso_fn, role_name: str, payload: dict, actor: str) -> tuple[bool, str]:
    role = str(role_name or '').strip().lower()
    if not role:
        return False, 'role inválida'
    if not re.fullmatch(r'[a-z0-9_\-]{2,64}', role):
        return False, 'role inválida'
    if role == 'admin':
        return False, 'role admin é imutável'

    permissions_payload = payload.get('permissions')
    normalized: dict[str, int] = {}
    if isinstance(permissions_payload, dict):
        for module_id, can_access in permissions_payload.items():
            normalized[str(module_id)] = 1 if bool(can_access) else 0
    elif isinstance(payload.get('modules'), list):
        for item in payload.get('modules'):
            if not isinstance(item, dict):
                continue
            module_id = str(item.get('module_id') or item.get('moduleId') or '').strip()
            if not module_id:
                continue
            normalized[module_id] = 1 if bool(item.get('can_access') or item.get('canAccess')) else 0
    else:
        return False, 'permissions inválidas'

    if not normalized:
        return False, 'nenhuma permissão informada'

    with db_factory() as conn:
        valid_modules = {r['module_id'] for r in conn.execute('SELECT module_id FROM app_modules').fetchall()}
        invalid = [mid for mid in normalized.keys() if mid not in valid_modules]
        if invalid:
            return False, f"módulos inválidos: {', '.join(invalid)}"

        now = now_iso_fn()
        role_row = conn.execute('SELECT id FROM roles WHERE role_key=?', (role,)).fetchone()
        if role_row is None:
            deleted = conn.execute('SELECT 1 FROM deleted_roles WHERE role_key=?', (role,)).fetchone()
            if deleted is not None:
                return False, 'role foi removida e não pode ser recriada por atualização de permissões'
            conn.execute(
                """
                INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, 0, 0, 1, ?, ?, ?, ?)
                """,
                (role, role, now, now, actor, actor),
            )
            role_row = conn.execute('SELECT id FROM roles WHERE role_key=?', (role,)).fetchone()

        role_id = int(role_row['id'])
        for module_id, can_access in normalized.items():
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
    return True, 'ok'
