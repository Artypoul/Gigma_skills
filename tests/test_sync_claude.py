import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / 'plugins' / 'vps-support' / 'skills' / 'vps-connect'


class ClaudeSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dest = Path(self.temp.name) / 'claude'
        self.skill = self.dest / 'skills' / 'vps-connect'

    def sync(self, *args):
        return subprocess.run(
            ['bash', str(ROOT / 'sync-claude.sh'), '--dest', str(self.dest), *args],
            text=True, capture_output=True, check=False,
        )

    def symlink(self, link, target):
        try:
            link.symlink_to(target)
        except OSError:
            if sys.platform == 'win32':
                self.skipTest('creating symlinks requires Windows privileges')
            raise

    def managed_names(self):
        manifest = self.dest / '.gigma-managed-skills'
        return set(manifest.read_text().splitlines()) if manifest.exists() else set()

    def test_unmanaged_same_name_changed_content_is_preserved(self):
        self.skill.mkdir(parents=True)
        personal_skill = self.skill / 'SKILL.md'
        original_bytes = b'---\nname: vps-connect\n---\nPersonal content\n'
        personal_skill.write_bytes(original_bytes)
        completed = self.sync('--plugin', 'vps-support')
        self.assertEqual(personal_skill.read_bytes(), original_bytes)
        self.assertEqual(completed.returncode, 3)
        self.assertNotIn('vps-connect', self.managed_names())
        self.assertIn('vps-connect', completed.stdout + completed.stderr)

    def test_identical_unmanaged_copy_is_accepted(self):
        self.skill.parent.mkdir(parents=True)
        shutil.copytree(CANON, self.skill, ignore=shutil.ignore_patterns('__pycache__'))
        completed = self.sync('--plugin', 'vps-support')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('vps-connect', self.managed_names())
        self.assertEqual((self.skill / 'SKILL.md').read_bytes(), (CANON / 'SKILL.md').read_bytes())

    def test_previously_managed_copy_is_updated(self):
        self.assertEqual(self.sync('--plugin', 'vps-support').returncode, 0)
        (self.skill / 'SKILL.md').write_bytes(b'outdated managed content')
        completed = self.sync('--plugin', 'vps-support')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.skill / 'SKILL.md').read_bytes(), (CANON / 'SKILL.md').read_bytes())
        self.assertIn('vps-connect', self.managed_names())

    def test_adopt_explicitly_replaces_personal_skill(self):
        self.skill.mkdir(parents=True)
        (self.skill / 'SKILL.md').write_bytes(b'personal content')
        completed = self.sync('--plugin', 'vps-support', '--adopt', 'vps-connect')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.skill / 'SKILL.md').read_bytes(), (CANON / 'SKILL.md').read_bytes())
        self.assertIn('vps-connect', self.managed_names())

    def test_unmanaged_copy_with_extra_file_is_preserved(self):
        self.skill.parent.mkdir(parents=True)
        shutil.copytree(CANON, self.skill, ignore=shutil.ignore_patterns('__pycache__'))
        extra = self.skill / 'personal.txt'
        extra.write_bytes(b'personal file')
        completed = self.sync('--plugin', 'vps-support')
        self.assertEqual(completed.returncode, 3)
        self.assertEqual(extra.read_bytes(), b'personal file')
        self.assertNotIn('vps-connect', self.managed_names())
        self.assertIn('vps-connect', completed.stdout + completed.stderr)

    def test_unmanaged_symlinks_are_preserved(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                shutil.rmtree(self.dest, ignore_errors=True)
                self.skill.parent.mkdir(parents=True)
                shutil.copytree(CANON, self.skill, ignore=shutil.ignore_patterns('__pycache__'))
                target = Path(self.temp.name) / 'private-target'
                if target.exists():
                    target.unlink()
                if not broken:
                    target.write_text('private data')
                link = self.skill / 'private-notes.txt'
                self.symlink(link, target)
                completed = self.sync('--plugin', 'vps-support')
                self.assertEqual(completed.returncode, 3)
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.readlink(), target)
                if not broken:
                    self.assertEqual(target.read_text(), 'private data')
                self.assertNotIn('vps-connect', self.managed_names())
                self.assertIn('vps-connect', completed.stdout + completed.stderr)

    def test_unmanaged_broken_skill_symlink_is_preserved(self):
        self.skill.parent.mkdir(parents=True)
        self.symlink(self.skill, Path(self.temp.name) / 'missing')
        completed = self.sync('--plugin', 'vps-support')
        self.assertEqual(completed.returncode, 3)
        self.assertTrue(self.skill.is_symlink())
        self.assertNotIn('vps-connect', self.managed_names())
        self.assertIn('vps-connect', completed.stdout + completed.stderr)

    def test_plugin_prune_preserves_other_canonical_managed_skills(self):
        self.assertEqual(self.sync('--plugin', 'gigma-erp').returncode, 0)
        self.assertIn('create-tenant', self.managed_names())
        existing = self.dest / 'skills' / 'create-tenant' / 'SKILL.md'
        before = existing.read_bytes()
        completed = self.sync('--plugin', 'vps-support', '--prune')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('create-tenant', self.managed_names())
        self.assertEqual(existing.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
