"""Public, immutable Superpowers release acquisition. No installation or auth.

The eligible Codex package is staged from an explicit whitelist. Other-harness
root instructions, hooks and package-manager entrypoints are not installed.
Native ``hooks: {}`` is required to make excluded root hooks unambiguously inert.
New Codex execution surfaces are rejected rather than silently removed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile


MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_JSON_BYTES = 2 * 1024 * 1024
REQUIRED_SKILLS = (
    'using-superpowers', 'brainstorming', 'writing-plans', 'executing-plans',
    'systematic-debugging', 'test-driven-development',
    'verification-before-completion', 'requesting-code-review',
    'receiving-code-review', 'subagent-driven-development',
    'dispatching-parallel-agents', 'using-git-worktrees',
    'finishing-a-development-branch', 'writing-skills', 'diagnosing-superpowers',
)
_VERSION = re.compile(r'^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
_REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
_SHA = re.compile(r'^[a-f0-9]{40}$')
_MANIFEST_KEYS = {'name', 'version', 'description', 'author', 'homepage', 'repository', 'license', 'keywords', 'skills', 'interface', 'hooks', '$schema'}
_UI_PATH_FIELDS = {'composerIcon', 'logo', 'logoDark'}
_DEFAULT_EXECUTION_PATHS = ('.mcp.json', 'mcp.json', '.app.json', 'agents', 'commands', 'scheduledTasks', 'scheduled_tasks', 'plugin.json')
_TOP_LEVEL_FILES = ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'README.md', 'CODE_OF_CONDUCT.md')


class SourceError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not (match := _VERSION.fullmatch(value)):
        raise SourceError('Expected a stable major.minor.patch version.')
    return tuple(int(part) for part in match.groups())


def _repo_name(repo: str) -> str:
    if not isinstance(repo, str) or not _REPO.fullmatch(repo) or any(x in {'.', '..'} for x in repo.split('/')):
        raise SourceError('Invalid GitHub repository identifier.')
    return repo


def _request_bytes(url: str, maximum: int = MAX_ARCHIVE_BYTES) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc not in {'api.github.com', 'codeload.github.com'} or parsed.username or parsed.password:
        raise SourceError('Unsupported release source URL.')
    request = urllib.request.Request(url, headers={'User-Agent': 'Codex-Superpowers-Updater/1', 'Accept': 'application/vnd.github+json' if parsed.netloc == 'api.github.com' else 'application/zip'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != 'https' or final.netloc not in {'api.github.com', 'codeload.github.com'}:
                raise SourceError('Unexpected release-source redirect.')
            length = response.headers.get('Content-Length')
            if length and int(length) > maximum:
                raise SourceError('Release response exceeds size limit.')
            chunks, size = [], 0
            while chunk := response.read(min(1024 * 1024, maximum + 1 - size)):
                size += len(chunk)
                if size > maximum:
                    raise SourceError('Release response exceeds size limit.')
                chunks.append(chunk)
            return b''.join(chunks)
    except urllib.error.HTTPError as error:
        retry = error.headers.get('Retry-After') if error.headers else None
        raise SourceError(f'GitHub request failed: HTTP {error.code}' + (f'; Retry-After={retry}' if retry else '')) from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise SourceError(f'Release source unavailable: {type(error).__name__}') from error


def _get_json(url: str) -> dict:
    try:
        result = json.loads(_request_bytes(url, MAX_JSON_BYTES))
    except (ValueError, UnicodeDecodeError) as error:
        raise SourceError('Release source returned invalid JSON.') from error
    if not isinstance(result, dict):
        raise SourceError('Release source returned an unexpected JSON shape.')
    return result


def latest_release(repo: str = 'obra/superpowers') -> dict:
    repo = _repo_name(repo)
    api_url = f'https://api.github.com/repos/{repo}/releases/latest'
    payload = _get_json(api_url)
    if payload.get('draft') is not False or payload.get('prerelease') is not False:
        raise SourceError('Only published stable releases are eligible.')
    tag = payload.get('tag_name')
    version = '.'.join(map(str, version_tuple(tag)))
    url = f'https://github.com/{repo}/releases/tag/{urllib.parse.quote(tag, safe="")}'
    return {'repo': repo, 'tag': tag, 'version': version, 'url': url,
            'api_url': api_url, 'release_id': payload.get('id'),
            'published_at': payload.get('published_at')}


def _safe_parts(name: str) -> tuple[str, ...]:
    if not name or '\\' in name or name.startswith('/'):
        raise SourceError('Unsafe ZIP member path.')
    raw = name[:-1] if name.endswith('/') else name
    parts = raw.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$', *(f'COM{x}' for x in [*range(1, 10), '¹', '²', '³']), *(f'LPT{x}' for x in [*range(1, 10), '¹', '²', '³'])}
    for part in parts:
        if not part or part in {'.', '..'} or part.endswith(('.', ' ')) or any(ord(char) < 32 or char in '<>:"|?*' for char in part) or part.split('.')[0].upper() in reserved:
            raise SourceError('Unsafe ZIP member path.')
    return tuple(parts)


def _extract_archive(data: bytes, destination: Path) -> Path:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise SourceError('ZIP exceeds compressed size limit.')
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        entries = archive.infolist()
    except (zipfile.BadZipFile, OSError) as error:
        raise SourceError('Invalid release ZIP.') from error
    with archive:
        if not entries or len(entries) > MAX_ENTRIES:
            raise SourceError('Unexpected ZIP entry count.')
        seen, roots, planned, file_paths, total = set(), set(), [], set(), 0
        for entry in entries:
            parts = _safe_parts(entry.filename)
            root, relative = parts[0], parts[1:]
            roots.add(root)
            folded = '/'.join(parts).casefold()
            if folded in seen:
                raise SourceError('Duplicate or case-colliding ZIP path.')
            seen.add(folded)
            mode = entry.external_attr >> 16
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR} or entry.flag_bits & 1:
                raise SourceError('ZIP links, special files and encryption are unsupported.')
            if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise SourceError('Unsupported release ZIP compression.')
            if not relative:
                if not entry.is_dir():
                    raise SourceError('Release ZIP must have one root directory.')
                continue
            if entry.file_size > MAX_FILE_BYTES:
                raise SourceError('ZIP member exceeds size limit.')
            total += entry.file_size
            if total > MAX_TOTAL_BYTES or (entry.file_size and entry.file_size > max(entry.compress_size, 1) * 2000):
                raise SourceError('ZIP expansion exceeds limits.')
            planned.append((entry, relative, mode))
            if not entry.is_dir():
                file_paths.add(folded)
        if len(roots) != 1:
            raise SourceError('Release ZIP must have one root directory.')
        for folded in seen:
            pieces = folded.split('/')
            if any('/'.join(pieces[:index]) in file_paths for index in range(1, len(pieces))):
                raise SourceError('Conflicting file and directory ZIP paths.')
        if destination.exists():
            raise SourceError('Extraction destination already exists.')
        destination.mkdir(parents=True)
        for entry, relative, mode in planned:
            target = destination.joinpath(*relative)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target.write_bytes(archive.read(entry))
                    if os.name != 'nt':
                        target.chmod(0o755 if mode & 0o111 else 0o644)
                except (zipfile.BadZipFile, OSError) as error:
                    raise SourceError('ZIP extraction failed.') from error
    return destination


def _relative_resource(value: str) -> str:
    if not isinstance(value, str) or not value.startswith('./'):
        raise SourceError('Plugin resource paths must be ./-relative.')
    parts = _safe_parts(value[2:])
    if parts[0] != 'assets':
        raise SourceError('UI resources must stay inside assets/.')
    return '/'.join(parts)


def _ui_paths(interface: dict | None) -> list[str]:
    if interface is None:
        return []
    if not isinstance(interface, dict):
        raise SourceError('Invalid plugin interface metadata.')
    values = [interface[key] for key in _UI_PATH_FIELDS if interface.get(key)]
    screenshots = interface.get('screenshots', [])
    if not isinstance(screenshots, list):
        raise SourceError('Invalid interface screenshot metadata.')
    values.extend(screenshots)
    return [_relative_resource(value) for value in values]


def _read_manifest(root: Path) -> dict:
    path = root / '.codex-plugin/plugin.json'
    try:
        manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        raise SourceError('Native Codex manifest is missing or invalid.') from error
    if not isinstance(manifest, dict):
        raise SourceError('Native Codex manifest must be an object.')
    return manifest


def _validate_metadata_file(path: Path) -> None:
    # Deliberately accept only the existing simple UI-only YAML shape. A regex
    # that merely searches unquoted root keys can miss quoted keys, YAML tags,
    # aliases or a uniformly-indented document. New syntax/capabilities require
    # manual review instead of a permissive ad-hoc YAML parser.
    text = path.read_text(encoding='utf-8-sig')
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if not lines or lines[0] != 'interface:':
        raise SourceError('Only canonical UI-only skill metadata is supported.')
    keys = set()
    for line in lines[1:]:
        match = re.fullmatch(r'  (display_name|short_description|default_prompt|brand_color|icon_small|icon_large): (.+)', line)
        if not match or match.group(1) in keys:
            raise SourceError('New or ambiguous skill metadata requires manual review.')
        key, scalar = match.groups()
        keys.add(key)
        if scalar.startswith('"'):
            try:
                value = json.loads(scalar)
            except ValueError as error:
                raise SourceError('Unsupported skill metadata string.') from error
            if not isinstance(value, str):
                raise SourceError('Skill interface values must be strings.')
        elif re.fullmatch(r"'(?:[^']|'')*'", scalar):
            value = scalar[1:-1].replace("''", "'")
        elif re.fullmatch(r'[A-Za-z0-9 .,_()/+\-]+', scalar):
            value = scalar
        else:
            raise SourceError('Unsupported YAML syntax in skill metadata.')
        if key in {'icon_small', 'icon_large'}:
            if not value.startswith('./'):
                raise SourceError('Skill UI resources must be relative.')
            _safe_parts(value[2:])


def _build_package(upstream: Path, package: Path, version: str, baseline_package: Path | None) -> dict:
    manifest = _read_manifest(upstream)
    if manifest.get('name') != 'superpowers' or manifest.get('version') != version:
        raise SourceError('Upstream manifest does not match the selected release.')
    version_tuple(version)
    if set(manifest) - _MANIFEST_KEYS:
        raise SourceError('New plugin manifest capabilities require manual review.')
    if manifest.get('hooks') != {} or not isinstance(manifest.get('skills'), str) or manifest['skills'] not in {'./skills', './skills/'}:
        raise SourceError('Only the declared skills directory and explicit empty Codex hooks are eligible.')
    for relative in _DEFAULT_EXECUTION_PATHS:
        if (upstream / relative).exists():
            raise SourceError(f'New default executable surface requires manual review: {relative}')
    license_paths = [upstream / name for name in _TOP_LEVEL_FILES[:3] if (upstream / name).is_file()]
    if not license_paths or not any(path.stat().st_size > 0 for path in license_paths):
        raise SourceError('A nonempty upstream license is required.')
    skills_root = upstream / 'skills'
    skill_names = sorted(path.parent.name for path in skills_root.glob('*/SKILL.md'))
    if not set(REQUIRED_SKILLS).issubset(skill_names):
        raise SourceError('A required compatibility skill is missing.')
    for name in skill_names:
        text = (skills_root / name / 'SKILL.md').read_text(encoding='utf-8-sig')
        front = re.match(r'^---\s*\n(.*?)\n---', text, re.S)
        if not front or not re.search(r'(?m)^name:\s*[\"\x27]?' + re.escape(name) + r'[\"\x27]?\s*$', front.group(1)) or not re.search(r'(?m)^description:\s*\S', front.group(1)):
            raise SourceError(f'Invalid skill front matter: {name}')
    for metadata in skills_root.glob('*/agents/openai.yaml'):
        _validate_metadata_file(metadata)
    upstream_ui = manifest.get('interface')
    upstream_ui_paths = _ui_paths(upstream_ui)
    overlays = []
    baseline = Path(baseline_package) if baseline_package is not None else None
    if baseline is not None and (upstream_ui is None or any(not (upstream / relative).is_file() for relative in upstream_ui_paths)):
        baseline_manifest = _read_manifest(baseline)
        if baseline_manifest.get('name') != 'superpowers':
            raise SourceError('Invalid baseline package.')
        if baseline_manifest.get('interface') is not None:
            _ui_paths(baseline_manifest['interface'])
            manifest['interface'] = baseline_manifest['interface']
            overlays.append({'path': '.codex-plugin/plugin.json', 'reason': 'Preserved curated interface metadata.'})
    if package.exists():
        raise SourceError('Candidate package already exists.')
    package.mkdir(parents=True)
    for directory in ['.codex-plugin', 'skills', 'assets']:
        if (upstream / directory).is_dir():
            shutil.copytree(upstream / directory, package / directory)
    for name in _TOP_LEVEL_FILES:
        if (upstream / name).is_file():
            shutil.copy2(upstream / name, package / name)
    if baseline is not None:
        for name in skill_names:
            metadata = baseline / 'skills' / name / 'agents/openai.yaml'
            if metadata.is_file():
                if metadata.is_symlink():
                    raise SourceError('Baseline metadata links are unsupported.')
                _validate_metadata_file(metadata)
                target = package / 'skills' / name / 'agents/openai.yaml'
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(metadata, target)
                overlays.append({'path': target.relative_to(package).as_posix(), 'reason': 'Preserved same-name curated skill interface metadata.', 'sha256': hashlib.sha256(metadata.read_bytes()).hexdigest()})
        for relative in _ui_paths(manifest.get('interface')):
            if not (package / relative).is_file() and (baseline / relative).is_file():
                if (baseline / relative).is_symlink():
                    raise SourceError('Baseline resource links are unsupported.')
                (package / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, package / relative)
                overlays.append({'path': relative, 'reason': 'Preserved required curated UI resource.'})
    for relative in _ui_paths(manifest.get('interface')):
        if not (package / relative).is_file():
            raise SourceError(f'Declared UI resource is missing: {relative}')
    (package / '.codex-plugin/plugin.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    inventory = [{'path': path.relative_to(package).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size} for path in sorted(package.rglob('*')) if path.is_file()]
    excluded = sorted(path.name for path in upstream.iterdir() if path.name not in {'.codex-plugin', 'skills', 'assets', *_TOP_LEVEL_FILES})
    return {'skills': skill_names, 'inventory': inventory, 'overlays': overlays, 'excluded_top_level': excluded, 'hook_handling': 'Native hooks:{} retained; excluded root other-harness hooks cannot be auto-discovered by Codex.'}


def stage_release(release: dict, stage_root: str | Path, baseline_package: str | Path | None = None) -> dict:
    repo = _repo_name(release.get('repo', 'obra/superpowers'))
    tag = release.get('tag')
    version = '.'.join(map(str, version_tuple(tag)))
    if release.get('version') != version:
        raise SourceError('Release version and tag disagree.')
    commit_url = f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(tag, safe="")}'
    commit_info = _get_json(commit_url)
    commit = str(commit_info.get('sha', '')).lower()
    if not _SHA.fullmatch(commit):
        raise SourceError('Release did not resolve to an immutable Git commit.')
    archive_url = f'https://codeload.github.com/{repo}/zip/{commit}'
    archive = _request_bytes(archive_url, MAX_ARCHIVE_BYTES)
    stage = Path(stage_root).resolve() / f'release-{version}-{commit[:12]}'
    if stage.exists():
        raise SourceError('This release stage already exists; preserve it for inspection.')
    stage.mkdir(parents=True)
    (stage / 'upstream.zip').write_bytes(archive)
    extracted = _extract_archive(archive, stage / 'upstream')
    package = stage / 'package'
    package_info = _build_package(extracted, package, version, Path(baseline_package).resolve() if baseline_package is not None else None)
    result = {**release, **package_info, 'repo': repo, 'tag': tag, 'version': version,
              'commit': commit, 'commit_url': commit_url, 'archive_url': archive_url,
              'commit_verification': bool(commit_info.get('commit', {}).get('verification', {}).get('verified')),
              'archive_sha256': hashlib.sha256(archive).hexdigest(),
              'upstream_manifest_sha256': hashlib.sha256((extracted / '.codex-plugin/plugin.json').read_bytes()).hexdigest(),
              'stage_path': str(stage), 'package_path': str(package)}
    (stage / 'source-provenance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
