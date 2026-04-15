import tempfile
import unittest
from datetime import UTC, datetime, timedelta

import app


class RecoveryAndReportsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.DATA_DIR = app.Path(self.tmp.name)
        app.DB_PATH = app.DATA_DIR / 'test.db'
        app.UPLOADS_DIR = app.DATA_DIR / 'uploads'
        app.DOCS_REPO_DIR = app.DATA_DIR / 'docs_repo'
        app.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def _insert_document(self, slug='doc-1'):
        with app.db() as conn:
            conn.execute(
                "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    slug,
                    'Doc 1',
                    'Backlog',
                    'Média',
                    'admin',
                    '',
                    'desc',
                    '',
                    app.now_iso(),
                    'Backlog',
                    'file.pdf',
                    'application/pdf',
                    '/tmp/file.pdf',
                    'admin',
                    app.now_iso(),
                    '',
                    1,
                ),
            )

    def test_periodic_report_create_and_list(self):
        ok, msg = app.create_periodic_report(
            {
                'name': 'r1',
                'statuses': ['Backlog'],
                'priorities': ['TODOS'],
                'roles': ['admin'],
                'weekdays': ['1'],
                'run_time': '09:00',
                'message': 'teste',
                'active': True,
            },
            'admin',
        )
        self.assertTrue(ok, msg)
        reports = app.list_periodic_reports()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['name'], 'r1')
        self.assertEqual(reports[0]['statuses'], ['Backlog'])

    def test_delete_and_restore_document(self):
        self._insert_document('doc-restore')
        with app.db() as conn:
            conn.execute("UPDATE documents SET project_id=? WHERE slug=?", (3, 'doc-restore'))
        ok, msg = app.delete_document('doc-restore', 'admin')
        self.assertTrue(ok, msg)

        deleted = app.list_deleted_documents()
        self.assertEqual(len(deleted['items']), 1)
        deleted_id = deleted['items'][0]['id']
        self.assertEqual(deleted['items'][0]['slug'], 'doc-restore')
        self.assertEqual(int(deleted['items'][0]['project_id'] or 0), 3)

        ok, msg = app.restore_deleted_document(deleted_id, 'admin')
        self.assertTrue(ok, msg)

        docs = app.list_documents(project_id=3)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['slug'], 'doc-restore')
        self.assertEqual(int(docs[0]['project_id'] or 0), 3)

    def test_delete_then_purge_deleted_document(self):
        self._insert_document('doc-purge')
        ok, msg = app.delete_document('doc-purge', 'admin')
        self.assertTrue(ok, msg)

        purged, failed = app.purge_expired_deleted_documents('system')
        self.assertEqual(purged, 0)
        self.assertEqual(failed, 0)
        deleted = app.list_deleted_documents()
        self.assertEqual(len(deleted['items']), 1)

        with app.db() as conn:
            expired_at = (datetime.now(UTC) - timedelta(days=31)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            conn.execute("UPDATE deleted_documents SET deleted_at=?, retention_days=30 WHERE slug=?", (expired_at, 'doc-purge'))

        purged, failed = app.purge_expired_deleted_documents('system')
        self.assertEqual(purged, 1)
        self.assertEqual(failed, 0)
        deleted = app.list_deleted_documents()
        self.assertEqual(len(deleted['items']), 0)


if __name__ == '__main__':
    unittest.main()
