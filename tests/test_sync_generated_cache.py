import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GeneratedCacheSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '.superpowers', '__pycache__', '.gitlab-ci-local', '*.pyc', '*.pyo'))
        self.skill = self.root / 'plugins/devops-skills/skills/gitlab-ci-validator'
        self.reference = self.root / 'plugins/devops-skills/reference'
        self.reference.mkdir(exist_ok=True)
        for base in (self.skill / 'examples', self.reference / 'nested'):
            for cache in ('.gitlab-ci-local', '__pycache__'):
                path = base / cache / 'deep' / 'generated'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('generated')
            (base / 'generated.pyc').write_text('generated')
            (base / 'ordinary.txt').write_text('ordinary')
        # Reject recursive copy or any direct cache copy at the actual cp boundary.
        bin_dir = Path(self.temp.name) / 'bin'
        bin_dir.mkdir()
        cp = bin_dir / 'cp'
        cp.write_text('''#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in
    -r|-R|-a|*'.gitlab-ci-local'*|*'__pycache__'*|*.pyc|*.pyo) echo "unsafe copy: $arg" >&2; exit 97 ;;
  esac
done
exec "${REAL_CP}" "$@"
''')
        cp.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], REAL_CP=shutil.which('cp'))

    def run_sync(self, script, *args):
        return subprocess.run(['bash', str(self.root / script), *map(str, args)], cwd=self.root,
                              env=self.env, capture_output=True, text=True)

    def assert_filtered(self, base):
        self.assertEqual((base / 'ordinary.txt').read_text(), 'ordinary')
        for name in ('.gitlab-ci-local', '__pycache__', 'generated.pyc'):
            self.assertFalse((base / name).exists(), name)

    def test_codex_filters_before_copy_and_validator_accepts_source_caches(self):
        result = self.run_sync('sync-codex.sh')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_filtered(self.root / '.codex/skills/gitlab-ci-validator/examples')
        self.assert_filtered(self.root / '.codex/reference/nested')
        validation = subprocess.run(['python', '-B', 'validate_plugin.py'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)

    def test_claude_filters_before_copy_and_adopts_unmanaged_with_caches(self):
        for cache_state in ('identical', 'absent', 'different'):
            with self.subTest(cache_state=cache_state):
                dest = Path(self.temp.name) / f'claude-{cache_state}'
                target = dest / 'skills/gitlab-ci-validator'
                target.parent.mkdir(parents=True)
                shutil.copytree(self.skill, target)
                cache = target / 'examples/.gitlab-ci-local'
                if cache_state != 'identical':
                    shutil.rmtree(cache)
                if cache_state == 'different':
                    cache.mkdir()
                    (cache / 'different').write_text('different cache contents')
                result = self.run_sync('sync-claude.sh', '--dest', dest, '--plugin', 'devops-skills')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_filtered(target / 'examples')
                self.assert_filtered(dest / 'reference/nested')
                self.assertIn('gitlab-ci-validator', (dest / '.gigma-managed-skills').read_text().splitlines())


if __name__ == '__main__':
    unittest.main()
