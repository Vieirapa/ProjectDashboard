from __future__ import annotations

"""
backend.admin.recovery_actions
==============================

Operações de domínio para exclusão lógica, restauração e expurgo definitivo de
registros recuperáveis.
"""

import shutil
import sqlite3
from pathlib import Path
from collections.abc import Callable


def delete_document(db_factory: Callable[[], sqlite3.Connection], audit_fn, document_file_path_fn, slug: str, actor: str) -> tuple[bool, str]:
    with db_factory() as conn:
        row = conn.execute('SELECT * FROM documents WHERE slug=?', (slug,)).fetchone()
        if not row:
            return False, 'Document not found'
        d = dict(row)
        conn.execute(
            """
            INSERT INTO deleted_documents(
                slug, name, status, priority, owner, note, description,
                project_id, project_name, createdBy, openedAt, releasedAt, dueDate,
                deleted_by, deleted_at, retention_days, file_name, file_path, ageDays,
                trash_path, document_json, review_notes_json, document_versions_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.get('slug'), d.get('name'), d.get('status'), d.get('priority'), d.get('owner'),
                d.get('note') or '', d.get('description') or '', d.get('project_id'), d.get('project_name') or '',
                d.get('created_by') or '', d.get('opened_at') or '', d.get('released_at') or '', d.get('due_date') or '',
                actor, d.get('updated_at') or d.get('opened_at') or '', 30, d.get('document_name') or '',
                str(document_file_path_fn(slug)) if d.get('document_name') else '', 0,
                '', '{}', '[]', '[]',
            ),
        )
        conn.execute('DELETE FROM document_dependencies WHERE document_slug=? OR depends_on_slug=?', (slug, slug))
        conn.execute('DELETE FROM review_notes WHERE document_slug=?', (slug,))
        conn.execute('DELETE FROM document_versions WHERE document_slug=?', (slug,))
        conn.execute('DELETE FROM documents WHERE slug=?', (slug,))
    audit_fn(actor, 'document.delete', slug, 'logical delete to recovery area')
    return True, 'ok'


def restore_deleted_document(db_factory: Callable[[], sqlite3.Connection], audit_fn, deleted_id: int, actor: str) -> tuple[bool, str]:
    with db_factory() as conn:
        row = conn.execute('SELECT * FROM deleted_documents WHERE id=?', (deleted_id,)).fetchone()
        if not row:
            return False, 'Documento apagado não encontrado'
        d = dict(row)
        exists = conn.execute('SELECT 1 FROM documents WHERE slug=?', (d['slug'],)).fetchone()
        if exists:
            return False, 'Já existe documento ativo com este slug'
        conn.execute(
            """
            INSERT INTO documents(slug, name, status, priority, owner, due_date, description, path, updated_at, document_status, document_name, document_mime, document_path, created_by, opened_at, released_at, project_id)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.get('slug'), d.get('name'), d.get('status'), d.get('priority'), d.get('owner'), d.get('dueDate') or '', d.get('description') or '', '',
                d.get('deleted_at') or '', d.get('status') or '', d.get('file_name') or '', '', d.get('file_path') or '',
                d.get('createdBy') or '', d.get('openedAt') or '', d.get('releasedAt') or '', d.get('project_id'),
            ),
        )
        conn.execute('DELETE FROM deleted_documents WHERE id=?', (deleted_id,))
    audit_fn(actor, 'document.restore', str(deleted_id), d.get('slug', ''))
    return True, 'ok'


def delete_deleted_document_permanently(db_factory: Callable[[], sqlite3.Connection], audit_fn, deleted_id: int, actor: str) -> tuple[bool, str]:
    with db_factory() as conn:
        row = conn.execute('SELECT * FROM deleted_documents WHERE id=?', (deleted_id,)).fetchone()
        if not row:
            return False, 'Documento apagado não encontrado'
        d = dict(row)
        file_path = str(d.get('file_path') or '').strip()
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass
        conn.execute('DELETE FROM deleted_documents WHERE id=?', (deleted_id,))
    audit_fn(actor, 'document.delete.permanent', str(deleted_id), d.get('slug', ''))
    return True, 'ok'


def purge_expired_deleted_documents(db_factory: Callable[[], sqlite3.Connection], audit_fn, actor: str = 'system') -> tuple[int, int]:
    purged = 0
    failed = 0
    with db_factory() as conn:
        rows = conn.execute('SELECT id, file_path, slug FROM deleted_documents').fetchall()
        for r in rows:
            try:
                file_path = str(r['file_path'] or '').strip()
                if file_path:
                    Path(file_path).unlink(missing_ok=True)
                conn.execute('DELETE FROM deleted_documents WHERE id=?', (r['id'],))
                purged += 1
            except Exception:
                failed += 1
    audit_fn(actor, 'deleted.purge.expired', str(purged), f'failed={failed}')
    return purged, failed
