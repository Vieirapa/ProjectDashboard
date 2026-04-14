import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import app


class ProjectExportArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.DATA_DIR = app.Path(self.tmp.name)
        app.DB_PATH = app.DATA_DIR / 'test.db'
        app.UPLOADS_DIR = app.DATA_DIR / 'uploads'
        app.DOCS_REPO_DIR = app.DATA_DIR / 'docs_repo'
        app.EXPORTS_DIR = app.DATA_DIR / 'exports'
        app.init_db()

        with app.db() as conn:
            conn.execute("INSERT INTO projects (project_name, start_date, notes) VALUES (?, ?, ?)", ('Projeto Exportável', app.now_iso(), 'notes'))
            project_id = conn.execute("SELECT MAX(project_id) AS id FROM projects").fetchone()['id']
            file_path = app.DATA_DIR / 'sample.pdf'
            file_path.write_text('fake-pdf', encoding='utf-8')
            conn.execute(
                "INSERT INTO documents (slug,name,status,priority,owner,due_date,description,path,updated_at,document_status,document_name,document_mime,document_path,created_by,opened_at,released_at,project_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    'doc-export', 'Doc Export', 'Backlog', 'Média', 'admin', '', 'desc', '', app.now_iso(), 'Backlog',
                    'sample.pdf', 'application/pdf', str(file_path), 'admin', app.now_iso(), '', project_id,
                ),
            )
            conn.execute(
                "INSERT INTO document_versions (document_slug, version, document_name, document_mime, document_status, file_rel_path, git_commit, checksum, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    'doc-export', 1, 'sample.pdf', 'application/pdf', 'Backlog', 'documents/doc-export/v0001_sample.pdf', 'commit1', 'checksum1', 'admin', app.now_iso(),
                ),
            )
            docs_repo_file = app.DOCS_REPO_DIR / 'documents' / 'doc-export' / 'v0001_sample.pdf'
            docs_repo_file.parent.mkdir(parents=True, exist_ok=True)
            docs_repo_file.write_text('fake-revision', encoding='utf-8')
            self.project_id = int(project_id)

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_project_package_creates_zip_with_manifest(self):
        ok, msg, package_path = app.export_project_package(self.project_id, 'admin')
        self.assertTrue(ok, msg)
        self.assertTrue(package_path)
        pkg = Path(package_path)
        self.assertTrue(pkg.exists())
        with ZipFile(pkg, 'r') as zf:
            names = set(zf.namelist())
            self.assertIn('manifest.json', names)
            self.assertIn('project/project.json', names)
            self.assertIn('project/documents.json', names)
            self.assertIn('files/current_documents/doc-export_v0001__sample.pdf', names)
            self.assertIn('files/docs_repo/doc-export_v0001__sample.pdf', names)
            manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
            self.assertEqual(manifest['project']['id'], self.project_id)
            self.assertEqual(manifest['counts']['documents'], 1)

    def test_archive_project_flags_project_and_persists_package_path(self):
        ok, msg, package_path = app.archive_project(self.project_id, 'admin')
        self.assertTrue(ok, msg)
        self.assertTrue(package_path)
        projects = app.list_projects_registry()
        proj = next(p for p in projects if int(p['project_id']) == self.project_id)
        self.assertTrue(proj['archived'])
        self.assertEqual(proj['archive_package_path'], package_path)

    def test_reconcile_document_storage_reports_missing_files(self):
        current_doc = Path(app.DATA_DIR / 'sample.pdf')
        current_doc.unlink(missing_ok=True)
        revision_doc = app.DOCS_REPO_DIR / 'documents' / 'doc-export' / 'v0001_sample.pdf'
        revision_doc.unlink(missing_ok=True)
        result = app.reconcile_document_storage('admin')
        self.assertTrue(result['ok'])
        self.assertEqual(result['repaired'], 0)
        self.assertEqual(result['missing'], 1)

    def test_resolve_document_file_path_prefers_versioned_file_over_stale_document_path(self):
        doc = app.get_document('doc-export')
        stale_path = app.DATA_DIR / 'stale.pdf'
        with app.db() as conn:
            conn.execute("UPDATE documents SET document_path=? WHERE slug=?", (str(stale_path), 'doc-export'))
        doc = app.get_document('doc-export')
        resolved, ver = app.resolve_document_file_path(doc, None)
        self.assertIsNotNone(ver)
        self.assertEqual(resolved, app.DOCS_REPO_DIR / 'documents' / 'doc-export' / 'v0001_sample.pdf')


if __name__ == '__main__':
    unittest.main()
