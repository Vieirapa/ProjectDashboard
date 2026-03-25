import os
import tempfile
import unittest

import app


class RolesDeleteRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="pdash-roles-reg-")
        self.db_path = os.path.join(self.tmpdir.name, "projectdashboard.db")
        self.old_db_path = app.DB_PATH
        app.DB_PATH = self.db_path
        app.init_db()

    def tearDown(self):
        app.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def _roles_table(self):
        with app.db() as conn:
            rows = conn.execute("SELECT role_key FROM roles ORDER BY id").fetchall()
        return [str(r["role_key"]) for r in rows]

    def test_sequential_delete_persists_and_does_not_resurrect(self):
        self.assertIn("member", self._roles_table())
        self.assertIn("desenhista", self._roles_table())

        ok, msg = app.delete_role_admin("member", "tester", reassign_to="admin")
        self.assertTrue(ok, msg)
        ok, msg = app.delete_role_admin("desenhista", "tester", reassign_to="admin")
        self.assertTrue(ok, msg)

        roles_after_delete = self._roles_table()
        self.assertNotIn("member", roles_after_delete)
        self.assertNotIn("desenhista", roles_after_delete)

        # Simula sincronização/bootstraps posteriores
        with app.db() as conn:
            app.ensure_roles_foundation(conn)
        app.sync_module_catalog()

        roles_after_sync = self._roles_table()
        self.assertNotIn("member", roles_after_sync)
        self.assertNotIn("desenhista", roles_after_sync)

        # Catálogo consumido pelo frontend também não pode reintroduzir roles apagadas
        catalog = app.list_role_catalog(include_admin=True)
        self.assertNotIn("member", catalog)
        self.assertNotIn("desenhista", catalog)
        self.assertIn("admin", catalog)

    def test_admin_protection_kept(self):
        ok, msg = app.delete_role_admin("admin", "tester")
        self.assertFalse(ok)
        self.assertIn("protegida", msg)


if __name__ == "__main__":
    unittest.main()
