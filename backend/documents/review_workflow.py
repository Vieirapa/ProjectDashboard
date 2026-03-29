from __future__ import annotations

"""
backend.documents.review_workflow
=================================

Funções de domínio relacionadas a dependências entre documentos e fluxo de
notas de revisão.
"""

import sqlite3
from collections.abc import Callable


def list_review_notes(db_factory: Callable[[], sqlite3.Connection], slug: str) -> list[dict]:
    with db_factory() as conn:
        rows = conn.execute(
            "SELECT id, slug, note, is_resolved, created_by, created_at, resolved_by, resolved_at FROM review_notes WHERE slug=? ORDER BY id DESC",
            (slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_review_note(db_factory: Callable[[], sqlite3.Connection], audit_fn, slug: str, note: str, actor: str) -> tuple[bool, str]:
    text = str(note or '').strip()
    if not text:
        return False, 'Nota obrigatória'
    with db_factory() as conn:
        row = conn.execute('SELECT slug FROM documents WHERE slug=?', (slug,)).fetchone()
        if not row:
            return False, 'Documento não encontrado'
        conn.execute(
            "INSERT INTO review_notes(slug, note, is_resolved, created_by, created_at, resolved_by, resolved_at) VALUES(?, ?, 0, ?, datetime('now'), NULL, NULL)",
            (slug, text, actor),
        )
    audit_fn(actor, 'review.note.add', slug, text[:300])
    return True, 'ok'


def set_review_note_resolution(db_factory: Callable[[], sqlite3.Connection], audit_fn, slug: str, note_id: int, actor: str, resolved: bool) -> tuple[bool, str]:
    with db_factory() as conn:
        row = conn.execute('SELECT id, is_resolved FROM review_notes WHERE id=? AND slug=?', (note_id, slug)).fetchone()
        if not row:
            return False, 'Nota não encontrada'
        if resolved:
            conn.execute(
                "UPDATE review_notes SET is_resolved=1, resolved_by=?, resolved_at=datetime('now') WHERE id=? AND slug=?",
                (actor, note_id, slug),
            )
            audit_fn(actor, 'review.note.resolve', slug, f'note_id={note_id}')
        else:
            conn.execute(
                "UPDATE review_notes SET is_resolved=0, resolved_by=NULL, resolved_at=NULL WHERE id=? AND slug=?",
                (note_id, slug),
            )
            audit_fn(actor, 'review.note.reopen', slug, f'note_id={note_id}')
    return True, 'ok'


def list_document_dependencies(db_factory: Callable[[], sqlite3.Connection], slug: str, project_id: int) -> list[dict]:
    with db_factory() as conn:
        rows = conn.execute(
            """
            SELECT d.slug, d.name, d.status, d.priority, d.owner, d.project_id
              FROM document_dependencies dd
              JOIN documents d ON d.slug = dd.depends_on_slug
             WHERE dd.slug=? AND dd.project_id=?
             ORDER BY d.name COLLATE NOCASE
            """,
            (slug, project_id),
        ).fetchall()
    return [dict(r) for r in rows]


def unresolved_dependencies(db_factory: Callable[[], sqlite3.Connection], slug: str, project_id: int) -> list[dict]:
    deps = list_document_dependencies(db_factory, slug, project_id)
    return [d for d in deps if str(d.get('status') or '') != 'Concluído']


def would_create_cycle(conn: sqlite3.Connection, source_slug: str, candidate_dep_slug: str, project_id: int) -> bool:
    if source_slug == candidate_dep_slug:
        return True
    seen = set()
    stack = [candidate_dep_slug]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur == source_slug:
            return True
        rows = conn.execute(
            'SELECT depends_on_slug FROM document_dependencies WHERE slug=? AND project_id=?',
            (cur, project_id),
        ).fetchall()
        for r in rows:
            nxt = str(r['depends_on_slug'] or '').strip()
            if nxt:
                stack.append(nxt)
    return False


def set_document_dependencies(db_factory: Callable[[], sqlite3.Connection], audit_fn, slug: str, project_id: int, depends_on_slugs: list[str], actor: str) -> tuple[bool, str]:
    clean = []
    seen = set()
    for item in depends_on_slugs or []:
        dep = str(item or '').strip()
        if not dep or dep in seen:
            continue
        seen.add(dep)
        clean.append(dep)

    with db_factory() as conn:
        row = conn.execute('SELECT slug FROM documents WHERE slug=? AND project_id=?', (slug, project_id)).fetchone()
        if not row:
            return False, 'Documento não encontrado'

        for dep in clean:
            dep_row = conn.execute('SELECT slug FROM documents WHERE slug=? AND project_id=?', (dep, project_id)).fetchone()
            if not dep_row:
                return False, f'Dependência inválida: {dep}'
            if would_create_cycle(conn, slug, dep, project_id):
                return False, f'Dependência criaria ciclo: {dep}'

        conn.execute('DELETE FROM document_dependencies WHERE slug=? AND project_id=?', (slug, project_id))
        for dep in clean:
            conn.execute(
                'INSERT INTO document_dependencies(slug, depends_on_slug, project_id) VALUES(?, ?, ?)',
                (slug, dep, project_id),
            )

    audit_fn(actor, 'document.dependencies.set', slug, ','.join(clean))
    return True, 'ok'
