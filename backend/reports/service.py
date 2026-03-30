from __future__ import annotations

"""
backend.reports.service
=======================

Módulo responsável pelo catálogo, composição e execução de relatórios periódicos.
"""

import json
import sqlite3
from collections.abc import Callable


def list_periodic_reports(db_factory: Callable[[], sqlite3.Connection]) -> list[dict]:
    with db_factory() as conn:
        rows = conn.execute(
            "SELECT id, name, statuses, priorities, roles, weekdays, run_time, message, active, created_by, created_at, updated_by, updated_at FROM periodic_reports ORDER BY id DESC"
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            'id': r['id'],
            'name': r['name'],
            'statuses': json.loads(r['statuses'] or '[]'),
            'priorities': json.loads(r['priorities'] or '[]'),
            'roles': json.loads(r['roles'] or '[]'),
            'weekdays': json.loads(r['weekdays'] or '[]'),
            'run_time': r['run_time'],
            'message': r['message'] or '',
            'active': bool(int(r['active'] or 0)),
            'created_by': r['created_by'],
            'created_at': r['created_at'],
            'updated_by': r['updated_by'],
            'updated_at': r['updated_at'],
        })
    return out


def create_periodic_report(db_factory: Callable[[], sqlite3.Connection], now_iso_fn, statuses_ref: list[str], priorities_ref: list[str], payload: dict, actor: str) -> tuple[bool, str]:
    try:
        name = str(payload.get('name') or '').strip()
        statuses = payload.get('statuses') or []
        priorities = payload.get('priorities') or []
        roles = payload.get('roles') or []
        weekdays = payload.get('weekdays') or []
        run_time = str(payload.get('run_time') or '').strip()
        message = str(payload.get('message') or '')
        active = bool(payload.get('active', True))
    except Exception:
        return False, 'Invalid payload'
    if not name:
        return False, 'Nome obrigatório'
    if not isinstance(statuses, list) or any(s not in statuses_ref for s in statuses):
        return False, 'Statuses inválidos'
    if not isinstance(priorities, list) or any(p not in priorities_ref and p != 'TODOS' for p in priorities):
        return False, 'Prioridades inválidas'
    if not isinstance(roles, list) or not all(str(r).strip() for r in roles):
        return False, 'Roles inválidas'
    if not isinstance(weekdays, list) or any(str(d) not in {'0','1','2','3','4','5','6'} for d in weekdays):
        return False, 'Periodicidade inválida'
    if not run_time or len(run_time) != 5:
        return False, 'Horário inválido'
    now = now_iso_fn()
    with db_factory() as conn:
        conn.execute(
            """
            INSERT INTO periodic_reports(name, statuses, priorities, roles, weekdays, run_time, message, active, created_by, created_at, updated_by, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                json.dumps(statuses, ensure_ascii=False),
                json.dumps(priorities, ensure_ascii=False),
                json.dumps(roles, ensure_ascii=False),
                json.dumps([str(x) for x in weekdays], ensure_ascii=False),
                run_time,
                message,
                1 if active else 0,
                actor,
                now,
                actor,
                now,
            ),
        )
    return True, 'ok'


def update_periodic_report(db_factory: Callable[[], sqlite3.Connection], now_iso_fn, statuses_ref: list[str], priorities_ref: list[str], report_id: int, payload: dict, actor: str) -> tuple[bool, str]:
    try:
        rid = int(report_id)
    except Exception:
        return False, 'Invalid ID'
    ok, msg = create_periodic_report(lambda: db_factory(), now_iso_fn, statuses_ref, priorities_ref, {**payload, 'name': payload.get('name') or 'tmp'}, actor)
    if not ok and msg != 'ok':
        return False, msg
    name = str(payload.get('name') or '').strip()
    statuses = payload.get('statuses') or []
    priorities = payload.get('priorities') or []
    roles = payload.get('roles') or []
    weekdays = payload.get('weekdays') or []
    run_time = str(payload.get('run_time') or '').strip()
    message = str(payload.get('message') or '')
    active = bool(payload.get('active', True))
    now = now_iso_fn()
    with db_factory() as conn:
        row = conn.execute('SELECT id FROM periodic_reports WHERE id=?', (rid,)).fetchone()
        if not row:
            return False, 'Report not found'
        conn.execute(
            """
            UPDATE periodic_reports
               SET name=?, statuses=?, priorities=?, roles=?, weekdays=?, run_time=?, message=?, active=?, updated_by=?, updated_at=?
             WHERE id=?
            """,
            (
                name,
                json.dumps(statuses, ensure_ascii=False),
                json.dumps(priorities, ensure_ascii=False),
                json.dumps(roles, ensure_ascii=False),
                json.dumps([str(x) for x in weekdays], ensure_ascii=False),
                run_time,
                message,
                1 if active else 0,
                actor,
                now,
                rid,
            ),
        )
    return True, 'ok'


def delete_periodic_report(db_factory: Callable[[], sqlite3.Connection], report_id: int) -> tuple[bool, str]:
    try:
        rid = int(report_id)
    except Exception:
        return False, 'Invalid ID'
    with db_factory() as conn:
        cur = conn.execute('DELETE FROM periodic_reports WHERE id=?', (rid,))
        if cur.rowcount <= 0:
            return False, 'Report not found'
    return True, 'ok'
