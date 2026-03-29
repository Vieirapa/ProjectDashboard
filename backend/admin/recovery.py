from __future__ import annotations

"""
backend.admin.recovery
======================

Operações administrativas ligadas ao catálogo de documentos apagados e sua
recuperação controlada.
"""

import sqlite3
from collections.abc import Callable


def list_deleted_documents(db_factory: Callable[[], sqlite3.Connection], q: str | None = None, deleted_by: str | None = None, deleted_from: str | None = None, deleted_to: str | None = None, page: int = 1, page_size: int = 10) -> dict:
    where = []
    args: list = []
    if q:
        like = f"%{str(q).strip()}%"
        where.append("(slug LIKE ? OR name LIKE ?)")
        args.extend([like, like])
    if deleted_by:
        where.append("deleted_by = ?")
        args.append(str(deleted_by).strip())
    if deleted_from:
        where.append("substr(deleted_at,1,10) >= ?")
        args.append(str(deleted_from).strip())
    if deleted_to:
        where.append("substr(deleted_at,1,10) <= ?")
        args.append(str(deleted_to).strip())
    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 10)))
    offset = (page - 1) * page_size
    with db_factory() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM deleted_documents {sql_where}", args).fetchone()['c']
        rows = conn.execute(
            f"""
            SELECT id, slug, name, status, priority, owner, project_id, project_name,
                   createdBy, openedAt, releasedAt, dueDate,
                   deleted_by, deleted_at, retention_days,
                   file_name, file_path,
                   note, description,
                   ageDays
              FROM deleted_documents
              {sql_where}
             ORDER BY deleted_at DESC, id DESC
             LIMIT ? OFFSET ?
            """,
            (*args, page_size, offset),
        ).fetchall()
    items = [dict(r) for r in rows]
    return {
        'items': items,
        'page': page,
        'page_size': page_size,
        'total': int(total or 0),
        'pages': max(1, ((int(total or 0) + page_size - 1) // page_size)),
    }
