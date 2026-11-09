"""The plugin must work as a self-contained install, without personal skills."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def test_fresh_plugin_copy_resolves_all_skill_files(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / 'vps-support'
            shutil.copytree(PLUGIN, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            names = {p.parent.name for p in (installed / 'skills').glob('*/SKILL.md')}
            self.assertEqual(names, {'vps-support', 'vps-connect', 'happ-setup', 'vps-troubleshoot', 'vps-node-network-setup', 'vps-node-panel-setup', 'vps-panel-setup', 'pasarguard-advanced-config', 'vps-configuration-analysis'})
            for path in (installed / 'skills').glob('*/SKILL.md'):
                with self.subTest(skill=path.parent.name):
                    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                        if '://' in target or target.startswith('#'):
                            continue
                        resolved = (path.parent / target.split('#', 1)[0]).resolve()
                        self.assertTrue(resolved.is_relative_to(installed.resolve()), target)
                        self.assertTrue(resolved.is_file(), target)
            node_setup = installed / 'skills/vps-node-panel-setup/SKILL.md'
            panel_setup = installed / 'skills/vps-panel-setup/SKILL.md'
            panel_links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', node_setup.read_text(encoding='utf-8'))
            self.assertIn(panel_setup.resolve(), [(node_setup.parent / link).resolve() for link in panel_links if '://' not in link])
            self.assertTrue((installed / 'reference/vps-routing.md').is_file())
            network = installed / 'skills/vps-node-network-setup/SKILL.md'
            setup = installed / 'skills/vps-node-panel-setup/SKILL.md'
            links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', network.read_text(encoding='utf-8'))
            self.assertIn(setup.resolve(), [(network.parent / link).resolve() for link in links if '://' not in link])
            script = installed / 'skills/vps-node-network-setup/scripts/compare_tcp_sequences.py'
            spec = importlib.util.spec_from_file_location('fresh_vps_tcp_comparison', script)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
                self.assertEqual(module.subtract([(0, 200)], [(0, 150)]), [[150, 200]])
            finally:
                sys.modules.pop(spec.name, None)

    def test_both_runtime_manifests_publish_the_same_version(self):
        manifests = [json.loads((PLUGIN / folder / 'plugin.json').read_text(encoding='utf-8')) for folder in ('.codex-plugin', '.claude-plugin')]
        self.assertEqual(manifests[0]['name'], 'vps-support')
        self.assertEqual(manifests[0]['version'], manifests[1]['version'])
        self.assertEqual(manifests[0]['skills'], './skills/')


if __name__ == '__main__':
    unittest.main()
