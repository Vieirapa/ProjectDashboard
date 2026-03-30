from __future__ import annotations

"""
backend.admin.settings
======================

Módulo responsável pela leitura e atualização das configurações administrativas
persistidas em `app_settings`.

Objetivo
--------
Removesr do `app.py` a lógica central de leitura/escrita de settings
administrativas, preparando o backend para crescimento modular.
"""

import json
import sqlite3
from collections.abc import Callable


def get_admin_settings(db_factory: Callable[[], sqlite3.Connection]) -> dict:
    """Lê as configurações administrativas persistidas."""
    with db_factory() as conn:
        rows = conn.execute(
            "SELECT key, value, updated_by, updated_at FROM app_settings ORDER BY key"
        ).fetchall()
    return {
        str(r['key']): {
            'value': r['value'],
            'updated_by': r['updated_by'],
            'updated_at': r['updated_at'],
        }
        for r in rows
    }


def update_admin_settings(db_factory: Callable[[], sqlite3.Connection], now_iso_fn, payload: dict, actor: str) -> tuple[bool, str]:
    """Updates configurações administrativas com validações centrais."""
    if not isinstance(payload, dict) or not payload:
        return False, 'Invalid payload'

    if 'workflow.default_due_days' in payload:
        try:
            days = int(str(payload.get('workflow.default_due_days') or '').strip())
        except Exception:
            return False, 'Prazo padrão inválido'
        if days < 0 or days > 3650:
            return False, 'Prazo padrão deve estar entre 0 e 3650 dias'
        payload['workflow.default_due_days'] = str(days)

    if 'workflow.dependency_max_status' in payload:
        allowed = {'Backlog', 'Em andamento', 'Em revisão', 'Concluído'}
        v = str(payload.get('workflow.dependency_max_status') or '').strip()
        if v not in allowed:
            return False, 'Status máximo de dependência inválido'
        payload['workflow.dependency_max_status'] = v

    if 'backup.weekdays' in payload:
        try:
            days = json.loads(str(payload.get('backup.weekdays') or '[]'))
        except Exception:
            return False, 'Dias de backup inválidos'
        if not isinstance(days, list) or any(str(x) not in {'0','1','2','3','4','5','6'} for x in days):
            return False, 'Dias de backup inválidos'
        payload['backup.weekdays'] = json.dumps([str(x) for x in days])

    if 'backup.run_time' in payload:
        run_time = str(payload.get('backup.run_time') or '').strip()
        if run_time and len(run_time) != 5:
            return False, 'Horário de backup inválido'

    if 'deleted.retention_days' in payload:
        try:
            days = int(str(payload.get('deleted.retention_days') or '').strip())
        except Exception:
            return False, 'Retenção inválida'
        if days < 1 or days > 3650:
            return False, 'Retenção deve estar entre 1 e 3650 dias'
        payload['deleted.retention_days'] = str(days)

    now = now_iso_fn()
    with db_factory() as conn:
        for key, value in payload.items():
            conn.execute(
                """
                INSERT INTO app_settings(key, value, updated_by, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_by=excluded.updated_by,
                    updated_at=excluded.updated_at
                """,
                (str(key), str(value), actor, now),
            )
    return True, 'ok'
