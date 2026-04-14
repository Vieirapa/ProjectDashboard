import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / 'install.sh'
README = ROOT / 'README.md'
DEPLOY_DOC = ROOT / 'docs' / '08-operacao-deploy.md'


class InstallContractsTest(unittest.TestCase):
    def test_installer_does_not_ship_fixed_admin_password_default(self):
        content = INSTALL_SH.read_text(encoding='utf-8')
        self.assertNotIn('ADMIN_PASSWORD="admin"', content)
        self.assertIn('ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"', content)
        self.assertIn('token_urlsafe', content)

    def test_secure_cookie_defaults_to_true_when_https_enabled(self):
        content = INSTALL_SH.read_text(encoding='utf-8')
        self.assertIn('if [[ "${ENABLE_HTTPS}" == "yes" ]]; then', content)
        self.assertIn('PDASH_FORCE_SECURE_COOKIE', content)
        self.assertIn('${PDASH_FORCE_SECURE_COOKIE:-true}', content)

    def test_docs_no_longer_advertise_admin_admin_bootstrap(self):
        for path in (README, DEPLOY_DOC):
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('admin / `admin`', content)
            self.assertNotIn('`admin` / `admin`', content)
            self.assertNotIn('installer default: `admin`', content)


if __name__ == '__main__':
    unittest.main()
