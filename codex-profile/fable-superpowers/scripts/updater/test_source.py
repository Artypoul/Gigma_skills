import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import source


def archive_files(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr('superpowers-commit/' + name, content)
    return stream.getvalue()


def package_files(version='7.0.2', manifest_extra=None):
    manifest = {'name': 'superpowers', 'version': version, 'skills': './skills/', 'hooks': {}, 'license': 'MIT'}
    manifest.update(manifest_extra or {})
    files = {'.codex-plugin/plugin.json': json.dumps(manifest), 'LICENSE': 'MIT License\n', 'README.md': '# Superpowers\n'}
    for name in source.REQUIRED_SKILLS:
        files[f'skills/{name}/SKILL.md'] = f'---\nname: {name}\ndescription: A test skill.\n---\nInstructions.\n'
    return files


class VersionTests(unittest.TestCase):
    def test_strict_stable_version(self):
        self.assertEqual(source.version_tuple('v7.0.2'), (7, 0, 2))
        self.assertLess(source.version_tuple('7.0.2'), source.version_tuple('7.1.0'))
        for value in ['7.0', '7.0.2-rc.1', '7.0.2+build', '../7.0.2', 'v07.0.2']:
            with self.subTest(value=value), self.assertRaises(source.SourceError):
                source.version_tuple(value)

    def test_latest_uses_only_stable_release_and_fixed_public_api(self):
        response = {'tag_name': 'v7.0.2', 'prerelease': False, 'draft': False, 'published_at': '2026-11-03T22:17:54Z', 'html_url': 'https://github.com/obra/superpowers/releases/tag/v7.0.2', 'id': 123}
        with patch.object(source, '_get_json', return_value=response) as get:
            result = source.latest_release('Artypoul/superpowers')
        self.assertEqual(result['version'], '7.0.2')
        get.assert_called_once_with('https://api.github.com/repos/Artypoul/superpowers/releases/latest')
        response['prerelease'] = True
        with patch.object(source, '_get_json', return_value=response), self.assertRaises(source.SourceError):
            source.latest_release('Artypoul/superpowers')

    def test_pinned_commit_stages_without_tag_lookup(self):
        release = {'repo': 'Artypoul/superpowers', 'tag': 'v7.0.2', 'version': '7.0.2', 'expected_commit': 'a' * 40}
        with tempfile.TemporaryDirectory() as temp, patch.object(source, '_get_json', return_value={'sha': 'a' * 40}) as get, patch.object(source, '_request_bytes', return_value=archive_files(package_files())):
            candidate = source.stage_release(release, temp)
        get.assert_called_once_with('https://api.github.com/repos/Artypoul/superpowers/commits/' + 'a' * 40)
        self.assertEqual(candidate['commit'], 'a' * 40)

    def test_pinned_commit_mismatch_fails_before_download(self):
        release={'repo':'Artypoul/superpowers','tag':'v7.0.2','version':'7.0.2','expected_commit':'a'*40}
        with tempfile.TemporaryDirectory() as temp, patch.object(source,'_get_json',return_value={'sha':'b'*40}), patch.object(source,'_request_bytes') as download:
            with self.assertRaises(source.SourceError):source.stage_release(release,temp)
            download.assert_not_called()

    def test_stage_requires_repository(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(source, '_get_json', side_effect=AssertionError('unexpected network lookup')), self.assertRaises(source.SourceError):
            source.stage_release({'tag': 'v7.0.2', 'version': '7.0.2'}, temp)


class RedirectTests(unittest.TestCase):
    class Response(io.BytesIO):
        def __init__(self,url,body=b'payload'):
            super().__init__(body);self.url=url;self.headers={}
        def geturl(self):return self.url

    def test_rejects_api_and_archive_cross_repository_redirects(self):
        cases=[('https://api.github.com/repos/Artypoul/superpowers/releases/latest','https://api.github.com/repos/obra/superpowers/releases/latest'),
               ('https://codeload.github.com/Artypoul/superpowers/zip/'+'a'*40,'https://codeload.github.com/obra/superpowers/zip/'+'a'*40)]
        for original,final in cases:
            with self.subTest(original=original), patch.object(source.urllib.request,'build_opener',return_value=SimpleNamespace(open=lambda *a,**k:self.Response(final))), self.assertRaises(source.SourceError):
                source._request_bytes(original)

    def test_redirect_hops_are_checked_before_the_next_request(self):
        original='https://api.github.com/repos/Artypoul/superpowers/releases/latest'
        safe='https://api.github.com/repos/artypoul/SUPERPOWERS/releases/42'
        foreign='https://api.github.com/repos/obra/superpowers/releases/42'
        class Transport:
            def __init__(self,handler,hops):self.handler=handler;self.hops=hops;self.sent=[]
            def open(self,request,timeout):
                self.sent.append(request.full_url)
                for target in self.hops:
                    request=self.handler.redirect_request(request,None,302,'Found',{},target)
                    self.sent.append(request.full_url)
                return RedirectTests.Response(request.full_url)
        for hops,allowed in [([foreign],1),([safe,foreign,original],2),(['https://evil.invalid/repos/Artypoul/superpowers/releases/latest'],1),(['https://codeload.github.com/obra/superpowers/zip/'+'a'*40],1)]:
            holder=[]
            def opener(handler):
                transport=Transport(handler,hops);holder.append(transport);return transport
            with self.subTest(hops=hops), patch.object(source.urllib.request,'build_opener',side_effect=opener), self.assertRaises(source.SourceError):
                source._request_bytes(original)
            self.assertEqual(len(holder[0].sent),allowed)
        holder=[]
        def opener(handler):
            transport=Transport(handler,[safe]);holder.append(transport);return transport
        with patch.object(source.urllib.request,'build_opener',side_effect=opener):
            self.assertEqual(source._request_bytes(original),b'payload')
        self.assertEqual(holder[0].sent,[original,safe])

    def test_rejects_missing_or_encoded_redirect_identity_before_read(self):
        original='https://api.github.com/repos/Artypoul/superpowers/releases/latest'
        for final in ['https://api.github.com/rate_limit','https://api.github.com/repos/Artypoul%2Fsuperpowers/releases/latest','https://evil.invalid/repos/Artypoul/superpowers/releases/latest']:
            response=self.Response(final)
            with self.subTest(final=final), patch.object(source.urllib.request,'build_opener',return_value=SimpleNamespace(open=lambda *a,**k:response)), self.assertRaises(source.SourceError):
                source._request_bytes(original)

    def test_allows_same_repository_redirects_and_case_changes(self):
        cases=[('https://api.github.com/repos/Artypoul/superpowers/releases/latest','https://api.github.com/repos/artypoul/SUPERPOWERS/releases/42'),
               ('https://codeload.github.com/Artypoul/superpowers/zip/'+'a'*40,'https://codeload.github.com/artypoul/SUPERPOWERS/zip/refs/tags/v7.0.2')]
        for original,final in cases:
            with self.subTest(original=original), patch.object(source.urllib.request,'build_opener',return_value=SimpleNamespace(open=lambda *a,**k:self.Response(final))):
                self.assertEqual(source._request_bytes(original),b'payload')


class ArchiveTests(unittest.TestCase):
    def test_traversal_absolute_windows_and_case_collision_are_rejected(self):
        cases = [['root/../escape'], ['/absolute'], ['root/C:/evil'], ['root\\..\\evil'], ['root/skills/A', 'root/skills/a'], ['root/NUL.txt'], ['root/COM¹.txt'], ['root/LPT².txt'], ['root/CONIN$'], ['root/CONOUT$'], ['root/trailing.']]
        for names in cases:
            with self.subTest(names=names), tempfile.TemporaryDirectory() as temp:
                data = io.BytesIO()
                with zipfile.ZipFile(data, 'w') as archive:
                    for name in names:
                        archive.writestr(name, 'bad')
                with self.assertRaises(source.SourceError):
                    source._extract_archive(data.getvalue(), Path(temp) / 'extracted')
                self.assertFalse((Path(temp) / 'escape').exists())

    def test_symlink_and_size_limit_are_rejected(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            entry = zipfile.ZipInfo('root/link')
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, '/outside')
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(source.SourceError):
            source._extract_archive(data.getvalue(), Path(temp) / 'extract')
        with tempfile.TemporaryDirectory() as temp, patch.object(source, 'MAX_FILE_BYTES', 2), self.assertRaises(source.SourceError):
            source._extract_archive(archive_files({'large': '123'}), Path(temp) / 'extract')

    def test_file_directory_conflict_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'extract'
            with self.assertRaises(source.SourceError):
                source._extract_archive(archive_files({'foo': 'file', 'foo/bar': 'child'}), target)
            self.assertFalse(target.exists())


class PackageTests(unittest.TestCase):
    def prepare(self, directory, files):
        for relative, content in files.items():
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')

    def test_package_whitelist_preserves_ui_and_blocks_other_harness_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream = root / 'upstream'
            baseline = root / 'baseline'
            files = package_files()
            files.update({'AGENTS.md': 'Do not copy me', 'GEMINI.md': 'Other harness', 'package.json': '{}', 'hooks/hooks.json': '{"SessionStart":[]}'})
            self.prepare(upstream, files)
            baseline_files = package_files('7.0.1', {'interface': {'displayName': 'Superpowers', 'logo': './assets/logo.png'}})
            baseline_files['assets/logo.png'] = 'image-placeholder'
            baseline_files['skills/brainstorming/agents/openai.yaml'] = 'interface:\n  display_name: "Brainstorming"\n'
            self.prepare(baseline, baseline_files)
            result = source._build_package(upstream, root / 'package', '7.0.2', baseline)
            package = root / 'package'
            self.assertFalse((package / 'AGENTS.md').exists())
            self.assertFalse((package / 'hooks').exists())
            self.assertFalse((package / 'package.json').exists())
            self.assertEqual(json.loads((package / '.codex-plugin/plugin.json').read_text())['hooks'], {})
            self.assertEqual(json.loads((package / '.codex-plugin/plugin.json').read_text())['interface']['displayName'], 'Superpowers')
            self.assertTrue((package / 'assets/logo.png').exists())
            self.assertEqual((package / 'skills/brainstorming/agents/openai.yaml').read_bytes(), (baseline / 'skills/brainstorming/agents/openai.yaml').read_bytes())
            self.assertIn('hooks', result['excluded_top_level'])
            self.assertTrue(result['overlays'])

    def test_new_executable_capabilities_and_version_mismatch_are_rejected(self):
        cases = [({'hooks': {'SessionStart': []}}, {}), ({'skills': {}}, {}), ({'apps': './.app.json'}, {}), ({'mcpServers': {}}, {}), ({}, {'.mcp.json': '{}'}), ({}, {'agents/reviewer.md': 'agent'}), ({'version': '9.0.0'}, {}), ({}, {'plugin.json': '{}'})]
        for extra, extra_files in cases:
            with self.subTest(extra=extra, files=extra_files), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.prepare(root / 'upstream', {**package_files(manifest_extra=extra), **extra_files})
                with self.assertRaises(source.SourceError):
                    source._build_package(root / 'upstream', root / 'package', '7.0.2', None)

    def test_missing_core_skill_and_external_ui_path_are_rejected(self):
        for remove, extra in [('skills/executing-plans/SKILL.md', {}), (None, {'interface': {'logo': '../secret'}})]:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                files = package_files(manifest_extra=extra)
                if remove:
                    files.pop(remove)
                self.prepare(root / 'upstream', files)
                with self.assertRaises(source.SourceError):
                    source._build_package(root / 'upstream', root / 'package', '7.0.2', None)

    def test_ui_metadata_cannot_hide_quoted_or_indented_capabilities(self):
        invalid = [
            'interface:\n  display_name: "Example"\n"dependencies":\n  tools: [{type: mcp, value: example}]\n',
            '  interface:\n    display_name: "Example"\n  dependencies:\n    tools: [{type: mcp, value: example}]\n',
            'interface:\n  display_name: "Example"\n  display_name: "Duplicate"\n',
        ]
        for content in invalid:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'openai.yaml'
                path.write_text(content, encoding='utf-8')
                with self.assertRaises(source.SourceError):
                    source._validate_metadata_file(path)

    def test_stage_uses_resolved_commit_and_records_hashes(self):
        release = {'repo': 'obra/superpowers', 'tag': 'v7.0.2', 'version': '7.0.2', 'url': 'https://github.com/obra/superpowers/releases/tag/v7.0.2'}
        commit = 'a' * 40
        with tempfile.TemporaryDirectory() as temp, patch.object(source, '_get_json', return_value={'sha': commit, 'commit': {'verification': {'verified': True}}}), patch.object(source, '_request_bytes', return_value=archive_files(package_files())) as download:
            result = source.stage_release(release, Path(temp))
            self.assertEqual(result['commit'], commit)
            self.assertEqual(result['version'], '7.0.2')
            self.assertEqual(len(result['archive_sha256']), 64)
            self.assertTrue(Path(result['package_path']).is_dir())
            self.assertTrue(result['inventory'])
            self.assertIn(commit, download.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
