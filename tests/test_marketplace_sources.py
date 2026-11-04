"""Remote catalogue entries must stay pinned and preserve local validation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('marketplace_validator', Path(__file__).resolve().parents[1] / 'validate_plugin.py')
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class MarketplaceSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_root, self.old_plugins = validator.ROOT, validator.PLUGIN_DIR
        validator.ROOT, validator.PLUGIN_DIR = self.root, self.root / 'plugins'
        validator.errors.clear()
        (self.root / 'plugins/local').mkdir(parents=True)
        self.external = {'name': 'remote', 'version': '1.0.0', 'runtimes': ['codex'], 'source': {'source': 'url', 'url': 'https://github.com/Artypoul/example.git', 'sha': 'a' * 40}, 'skills': ['remote-skill'], 'license': 'MIT'}
        self.codex = {'name': 'test', 'plugins': [{'name': 'local', 'source': {'source': 'local', 'path': './plugins/local'}}, {'name': 'remote', 'version': '1.0.0', 'description': 'Remote plugin', 'source': copy.deepcopy(self.external['source'])}]}
        self.claude = {'name': 'test', 'plugins': [{'name': 'local', 'source': './plugins/local', 'description': 'Local plugin'}]}

    def tearDown(self):
        validator.ROOT, validator.PLUGIN_DIR = self.old_root, self.old_plugins
        validator.errors.clear()
        self.temp.cleanup()

    def run_validation(self, externals=None):
        for rel, data in [('.agents/plugins/marketplace.json', self.codex), ('.claude-plugin/marketplace.json', self.claude), ('external-plugins.lock.json', {'schema_version': 1, 'plugins': externals if externals is not None else [self.external]})]:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data), encoding='utf-8')
        validator.validate_marketplaces({'local'})
        return list(validator.errors)

    def test_mixed_catalogue_accepts_runtime_specific_pinned_source(self):
        self.assertEqual(self.run_validation(), [])

    def test_shared_git_subdir_source_works_for_both_runtimes(self):
        self.external['runtimes'] = ['codex', 'claude']
        self.external['source'].update(source='git-subdir', path='plugins/remote')
        self.codex['plugins'][1]['source'] = copy.deepcopy(self.external['source'])
        self.claude['plugins'].append(copy.deepcopy(self.codex['plugins'][1]))
        self.assertEqual(self.run_validation(), [])

    def test_unpinned_source_is_rejected(self):
        del self.external['source']['sha']
        self.assertTrue(self.run_validation())

    def test_different_marketplace_pin_is_rejected(self):
        self.codex['plugins'][1]['source']['sha'] = 'b' * 40
        self.assertTrue(self.run_validation())

    def test_runtime_not_supported_by_upstream_is_rejected(self):
        self.claude['plugins'].append(copy.deepcopy(self.codex['plugins'][1]))
        self.assertTrue(self.run_validation())

    def test_external_cannot_shadow_local_plugin(self):
        self.external['name'] = 'local'
        self.assertTrue(self.run_validation())

    def test_duplicate_catalogue_entry_is_rejected(self):
        self.codex['plugins'].append(copy.deepcopy(self.codex['plugins'][1]))
        self.assertTrue(self.run_validation())

    def test_duplicate_lock_entry_is_rejected(self):
        self.assertTrue(self.run_validation([self.external, copy.deepcopy(self.external)]))

    def test_local_path_escape_is_still_rejected(self):
        self.codex['plugins'][0]['source']['path'] = './plugins/../outside'
        self.assertTrue(self.run_validation())

    def test_external_path_escape_is_rejected(self):
        self.external['source'].update(source='git-subdir', path='../outside')
        self.assertTrue(self.run_validation())

    def test_windows_drive_source_path_is_rejected(self):
        self.external['source'].update(source='git-subdir', path='C:/outside')
        self.codex['plugins'][1]['source'] = copy.deepcopy(self.external['source'])
        self.assertTrue(self.run_validation())

    def test_credentials_cannot_be_stored_in_source_url(self):
        self.external['source']['url'] = 'https://user:secret@github.com/Artypoul/example.git'
        self.assertTrue(self.run_validation())

    def test_missing_external_entry_is_rejected(self):
        self.codex['plugins'].pop()
        self.assertTrue(self.run_validation())

    def test_version_drift_is_rejected(self):
        self.codex['plugins'][1]['version'] = '2.0.0'
        self.assertTrue(self.run_validation())


class SuperpowersCatalogueTests(unittest.TestCase):
    """The portable profile consumes the complete Codex-only upstream package."""

    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.lock = json.loads((self.root / 'external-plugins.lock.json').read_text(encoding='utf-8'))
        self.codex = json.loads((self.root / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
        self.claude = json.loads((self.root / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))

    def superpowers(self):
        entries = [entry for entry in self.lock['plugins'] if entry['name'] == 'superpowers']
        self.assertEqual(len(entries), 1)
        return entries[0]

    def test_canonical_whole_package_has_an_immutable_source(self):
        entry = self.superpowers()
        self.assertEqual(entry['source']['source'], 'url')
        self.assertEqual(entry['source']['url'], 'https://github.com/obra/superpowers.git')
        self.assertRegex(entry['source']['sha'], r'^[0-9a-f]{40}$')
        self.assertNotIn('path', entry['source'])
        self.assertEqual(entry['manifest'], '.codex-plugin/plugin.json')
        self.assertEqual(entry['license'], 'MIT')

    def test_native_entry_is_codex_only_and_matches_the_lock(self):
        entry = self.superpowers()
        self.assertEqual(entry['runtimes'], ['codex'])
        selected = [item for item in self.codex['plugins'] if item['name'] == 'superpowers']
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['source'], entry['source'])
        self.assertEqual(selected[0]['version'], entry['version'])
        self.assertFalse(any(item['name'] == 'superpowers' for item in self.claude['plugins']))

    def test_upstream_skills_are_declared_without_a_second_local_owner(self):
        entry = self.superpowers()
        skills = entry['skills']
        self.assertEqual(len(skills), len(set(skills)))
        self.assertTrue({'using-superpowers', 'systematic-debugging', 'test-driven-development',
            'executing-plans', 'verification-before-completion'}.issubset(skills))
        self.assertFalse((self.root / 'plugins/superpowers').exists())
        for name in skills:
            self.assertFalse((self.root / '.codex/skills' / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
