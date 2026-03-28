import os
import tempfile
import unittest

import app


class InactiveRoleLockdownTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="pdash-inactive-role-")
        self.db_path = os.path.join(self.tmpdir.name, "projectdashboard.db")
        self.old_db_path = app.DB_PATH
        app.DB_PATH = self.db_path
        app.init_db()

    def tearDown(self):
        app.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def test_inactive_role_has_no_effective_permissions(self):
        with app.db() as conn:
            now = app.now_iso()
            conn.execute(
                """
                INSERT INTO roles (role_key, display_name, is_system, is_superadmin, active, created_at, updated_at, created_by, updated_by)
                VALUES ('diretor', 'Diretor', 0, 0, 1, ?, ?, 'test', 'test')
                ON CONFLICT(role_key) DO NOTHING
                """,
                (now, now),
            )
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                ("u_diretor", app.hash_password("1234"), "diretor", now),
            )
            conn.execute("UPDATE roles SET active=0 WHERE role_key='diretor'")

        self.assertFalse(app.role_is_active("diretor"))

        perms = app.get_effective_permissions({"username": "u_diretor", "role": "diretor"})
        self.assertEqual(perms.get("role"), "diretor")
        self.assertFalse(bool(perms.get("roleActive")))
        self.assertEqual(perms.get("allowedModules"), [])
        self.assertEqual(perms.get("allowedPages"), [])

    def test_admin_remains_active(self):
        self.assertTrue(app.role_is_active("admin"))
        perms = app.get_effective_permissions({"username": "admin", "role": "admin"})
        self.assertTrue(bool(perms.get("roleActive")))


if __name__ == "__main__":
    unittest.main()
