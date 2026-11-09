"""First-boot sudo must work before the template removes root access.

Execute the actual embedded Python against temporary files. Only account
lookup and privileged commands are substituted; no host configuration is used.
"""
import contextlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'plugins/devops-skills/skills/vps-forge/assets/cloud-init.yaml'


def template_text():
    return TEMPLATE.read_text(encoding='utf-8')


def bootstrap_namespace():
    # Extract this literal block, not a general YAML parser. Full YAML/schema
    # validation remains a separate packaging check.
    match = re.search(r'  - - python3\n    - -c\n    - \|\n((?:      .*\n|\n)+)', template_text())
    if not match:
        raise AssertionError('Missing first-boot admin bootstrap before SSH hardening')
    namespace = {'__name__': 'cloud_init_test'}
    fake_pwd = types.SimpleNamespace()
    with patch.dict(sys.modules, {'pwd': fake_pwd}):
        exec(compile(textwrap.dedent(match.group(1)), str(TEMPLATE), 'exec'), namespace)
    return namespace


class CloudInitOrderingTests(unittest.TestCase):
    def test_cloud_init_does_not_disable_root_before_admin_bootstrap(self):
        # These cloud-init fields act before runcmd; either one bypasses the
        # bootstrap's failure gate even if its Python code is correct.
        text = template_text()
        self.assertNotRegex(text, r'(?m)^disable_root:\s*true\s*$')
        self.assertNotIn('  - path: /etc/ssh/sshd_config.d/00-vps-forge.conf', text)
        self.assertIn('  - path: /var/lib/vps-forge/00-vps-forge.conf', text)
        self.assertRegex(text, r'runcmd:\n(?:  #.*\n)*  - set -e\n')
        bootstrap_namespace()


@unittest.skipUnless(os.name == 'posix', 'POSIX file permissions and dir_fd; runs in Linux CI')
class CloudInitAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home/admin'
        self.home.mkdir(parents=True)
        for directory in ['etc/sudoers.d', 'etc/ssh/sshd_config.d', 'var/lib/vps-forge']:
            (self.root / directory).mkdir(parents=True)
        self.pending = self.root / 'var/lib/vps-forge/00-vps-forge.conf'
        self.pending.write_text('PermitRootLogin no\n', encoding='utf-8')
        self.active = self.root / 'etc/ssh/sshd_config.d/00-vps-forge.conf'
        self.namespace = bootstrap_namespace()
        self.namespace['Path'] = self.map_path
        self.namespace['pwd'].getpwnam = lambda name: types.SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(self.home))
        self.password_state = 'L'
        self.password = None
        self.fail_command = None
        self.commands = []
        self.namespace['run'] = self.run_command

    def map_path(self, value):
        value = str(value)
        if value.startswith(('/etc/', '/var/lib/vps-forge/')):
            return self.root / value.lstrip('/')
        return Path(value)

    def run_command(self, *args, **kwargs):
        self.commands.append(args)
        if args[0] == self.fail_command:
            raise subprocess.CalledProcessError(1, args)
        if args[0] == 'passwd':
            return types.SimpleNamespace(stdout='admin ' + self.password_state + ' date 0 99999 7 -1\n')
        if args[0] == 'chpasswd':
            self.assertFalse(self.active.exists(), 'SSH hardened before password provisioning')
            user, self.password = kwargs['input'].strip().split(':', 1)
            self.assertEqual(user, 'admin')
            self.password_state = 'P'
        if args[0] == 'runuser':
            rule = (self.root / 'etc/sudoers.d/99-vps-forge-admin').read_text()
            if 'NOPASSWD:' not in rule:
                self.assertEqual(self.password_state, 'P', 'sudo still has a locked password')
                self.assertEqual(kwargs.get('input', '').strip(), self.password)
            self.assertFalse(self.active.exists(), 'SSH hardened before sudo was tested')
            return types.SimpleNamespace(stdout='0\n')
        return types.SimpleNamespace(stdout='')

    def invoke(self, policy='password'):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.namespace['provision_admin']('admin', policy)
        self.assertEqual(output.getvalue(), '')

    def test_password_policy_delivers_private_password_and_working_sudo_first(self):
        self.invoke()
        secret = self.home / 'SUDO-PASSWORD'
        self.assertGreaterEqual(len(self.password), 24)
        self.assertEqual(secret.read_text().strip(), self.password)
        self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
        self.assertEqual(secret.stat().st_uid, os.getuid())
        self.assertEqual(self.active.read_text(), 'PermitRootLogin no\n')
        self.assertIn('PASSWD:ALL', (self.root / 'etc/sudoers.d/99-vps-forge-admin').read_text())
        self.assertFalse(any(self.password in str(args) for args in self.commands))

    def test_nopasswd_policy_keeps_password_locked_and_creates_no_secret(self):
        self.invoke('nopasswd')
        self.assertEqual(self.password_state, 'L')
        self.assertFalse((self.home / 'SUDO-PASSWORD').exists())
        self.assertTrue(self.active.exists())
        self.assertIn('NOPASSWD:ALL', (self.root / 'etc/sudoers.d/99-vps-forge-admin').read_text())

    def test_unselected_policy_does_not_install_privilege_or_ssh_rules(self):
        with self.assertRaises(ValueError):
            self.invoke('<sudo-policy>')
        self.assertFalse(self.active.exists())
        self.assertFalse((self.root / 'etc/sudoers.d/99-vps-forge-admin').exists())
        self.assertFalse((self.home / 'SUDO-PASSWORD').exists())

    def test_password_or_sudo_failure_keeps_ssh_hardening_pending(self):
        for command in ['chpasswd', 'visudo', 'runuser']:
            with self.subTest(command=command):
                # Each failure starts with the first-boot state.
                secret = self.home / 'SUDO-PASSWORD'
                secret.unlink(missing_ok=True)
                self.password_state = 'L'
                self.fail_command = command
                with self.assertRaises(subprocess.CalledProcessError):
                    self.invoke()
                self.assertFalse(self.active.exists())

    def test_existing_password_file_or_symlink_is_not_overwritten(self):
        victim = self.root / 'untouched'
        victim.write_text('keep', encoding='utf-8')
        (self.home / 'SUDO-PASSWORD').symlink_to(victim)
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(victim.read_text(), 'keep')
        self.assertEqual(self.password_state, 'L')
        self.assertFalse(self.active.exists())


if __name__ == '__main__':
    unittest.main()
