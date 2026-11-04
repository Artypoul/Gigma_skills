"""Staged Superpowers/Fable compatibility gate. Never activates the candidate.

The public API is run_compatibility(candidate, run_root, codex_home). A read-only
catalogue/isolation probe is available as probe_candidate with the same inputs.
Only temporary project trust entries are leased globally; their cleanup is
bounded to the generated fixture paths and preserves concurrent unrelated edits.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tomllib
import uuid

HERE = Path(__file__).resolve().parent
RESOURCES = HERE / 'resources'
PLUGIN_ID = 'superpowers@fable-superpowers'
CASES = ('small_config', 'bug_fix', 'approved_plan', 'local_research', 'ambiguous_metric')
CRITICAL = frozenset({'using-superpowers','brainstorming','writing-plans','executing-plans',
    'systematic-debugging','test-driven-development','verification-before-completion',
    'requesting-code-review','receiving-code-review'})
REQUIRED_BY_CASE = {
    'small_config': frozenset(), 'local_research': frozenset(),
    'bug_fix': frozenset({'systematic-debugging','test-driven-development','verification-before-completion'}),
    'approved_plan': frozenset({'executing-plans','test-driven-development','verification-before-completion','requesting-code-review'}),
    'ambiguous_metric': frozenset({'brainstorming'}),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def _normpath(path) -> str:
    result = os.path.normpath(str(path)).replace('\\', '/')
    return result.casefold() if os.name == 'nt' else result


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _cmd(args, cwd: Path, *, env=None, timeout=60) -> dict:
    result = subprocess.run([str(x) for x in args], cwd=cwd, env=env, capture_output=True,
        encoding='utf-8', errors='replace', timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return {'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


_FIXTURE_BOOTSTRAP = r'''import json, os, runpy, socket, subprocess, sys
port, config, fixture, arguments, marker = sys.argv[1:]
try:
    connection = socket.create_connection(('127.0.0.1', int(port)), timeout=2)
except PermissionError:
    pass
except OSError as error:
    raise SystemExit('Cannot verify native network denial: ' + type(error).__name__)
else:
    connection.close()
    raise SystemExit('Native sandbox permits loopback network access; fixture code was not run.')
try:
    descriptor = os.open(config, os.O_WRONLY)
except PermissionError:
    pass
except OSError as error:
    raise SystemExit('Cannot verify native global write denial: ' + type(error).__name__)
else:
    os.close(descriptor)
    raise SystemExit('Native sandbox permits global config writes; fixture code was not run.')
print(marker, flush=True)
invocation = json.loads(arguments)
arguments = invocation['arguments']
sys.path.insert(0, fixture)
if invocation['kind'] == 'git':
    raise SystemExit(subprocess.run([invocation['executable'], *arguments]).returncode)
elif arguments[:2] == ['-m', 'unittest']:
    sys.argv = ['unittest', *arguments[2:]]
    runpy.run_module('unittest', run_name='__main__', alter_sys=True)
elif len(arguments) == 2 and arguments[0] == '-c':
    sys.argv = ['-c']
    exec(compile(arguments[1], '<compatibility-contract>', 'exec'), {'__name__': '__main__'})
else:
    raise SystemExit('Unsupported fixture validation invocation.')
'''


def _fixture_command(invocation: dict, cwd: Path, codex_home: Path, timeout=60) -> dict:
    """Run generated tests/imports only after native confinement is verified.

    The Windows legacy restricted token allows loopback. Prefer MXC, then
    positively verify denial before adding the fixture to Python's import path;
    an unavailable MXC backend therefore fails closed rather than falling back.
    Explicit builtin profiles cannot inherit an ambient full-access profile.
    """
    if os.name != 'nt':
        raise RuntimeError('Native fixture validation is currently supported only on Windows.')
    codex=shutil.which('codex')
    if not codex:
        raise RuntimeError('Codex sandbox executable is unavailable; fixture code was not run.')
    cwd=Path(cwd).resolve(strict=True)
    config=Path(codex_home).resolve(strict=True)/'config.toml'
    if not config.is_file() or config.is_symlink():
        raise RuntimeError('A regular selected-home config is required for sandbox verification.')
    marker='SUPERPOWERS_NATIVE_SANDBOX_READY_'+uuid.uuid4().hex
    # MXC Git requires a writable worktree even for status/diff. Its child
    # process remains confined to the explicit builtin workspace profile.
    profile=':workspace' if invocation['kind']=='git' else ':read-only'
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1',0))
        listener.listen(1)
        command=[codex,'sandbox','--permission-profile',profile,'-C',str(cwd),
            '-c','features.prefer_mxc=true','-c','sandbox_workspace_write.writable_roots=[]',
            '--',sys.executable,'-I','-S','-B','-c',_FIXTURE_BOOTSTRAP,
            str(listener.getsockname()[1]),str(config),str(cwd),json.dumps(invocation,ensure_ascii=True),marker]
        result=_cmd(command,cwd,env=_env(Path(codex_home)),timeout=timeout)
    lines=result['stdout'].splitlines()
    if marker not in lines:
        raise RuntimeError('Native fixture sandbox did not verify confinement; no fallback was attempted. '
            +(result.get('stderr','') or result.get('stdout',''))[:600])
    result['stdout']=re.sub(r'(?m)^'+re.escape(marker)+r'\r?\n','',result['stdout'],count=1)
    result['sandbox']={'profile':profile,'backend':'native-codex','isolated_python':True,
        'loopback_network_denial_verified':True,'global_config_write_denial_verified':True}
    return result


def _fixture_python(arguments: list, cwd: Path, codex_home: Path, timeout=60) -> dict:
    if not (arguments[:2] == ['-m','unittest'] or (len(arguments)==2 and arguments[0]=='-c')):
        raise ValueError('Unsupported fixture validation invocation.')
    return _fixture_command({'kind':'python','arguments':arguments},cwd,codex_home,timeout)


def _fixture_git(arguments: list, cwd: Path, codex_home: Path, timeout=60) -> dict:
    git=shutil.which('git')
    if not git:
        raise RuntimeError('Git is unavailable for confined fixture validation.')
    if not arguments or arguments[0] not in {'status','worktree','show','diff'}:
        raise ValueError('Unsupported fixture git invocation.')
    return _fixture_command({'kind':'git','executable':git,
        'arguments':['--no-pager','-c','core.fsmonitor=false',*arguments]},cwd,codex_home,timeout)


def _fixture_home(fable: dict, codex_home: Path | None) -> Path:
    if codex_home is not None:
        return Path(codex_home).resolve(strict=True)
    path=Path(fable['path']).resolve(strict=True)
    for ancestor in path.parents:
        if _within(path,ancestor/'plugins/cache'):
            return ancestor
    raise RuntimeError('Cannot resolve the selected Codex home from the verified Fable cache path.')


def _env(codex_home: Path) -> dict:
    env = os.environ.copy()
    env['CODEX_HOME'] = str(codex_home)
    env.pop('CODEX_THREAD_ID', None)
    if shutil.which('codex'):
        env['FABLE5_CODEX_BIN'] = shutil.which('codex')
    return env


def _runner_module():
    spec = importlib.util.spec_from_file_location('updater_appserver_eval', RESOURCES / 'appserver_eval.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_skills(candidate: dict) -> dict:
    package = Path(candidate['package_path']).resolve(strict=True)
    stage = Path(candidate['stage_path']).resolve(strict=True)
    if not package.is_dir() or not _within(package, stage):
        raise ValueError('Candidate package must be inside its owned stage directory.')
    manifest_path = package / '.codex-plugin/plugin.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if manifest.get('name') != 'superpowers' or manifest.get('version') != candidate['version']:
        raise ValueError('Candidate name/version does not match its manifest.')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?',candidate['version']):
        raise ValueError('Unsafe candidate version.')
    roots = manifest.get('skills', './skills')
    roots = [roots] if isinstance(roots, str) else roots
    if not isinstance(roots, list) or not roots or not all(isinstance(x,str) for x in roots):
        raise ValueError('Unsupported skill-directory declaration.')
    found = {}
    for relative in roots:
        root = (package / relative).resolve(strict=True)
        if not root.is_dir() or not _within(root, package):
            raise ValueError('Skill directory escapes the candidate package.')
        for filename in root.rglob('SKILL.md'):
            if filename.is_symlink() or not _within(filename, package):
                raise ValueError('Unsafe candidate skill path.')
            text = filename.read_text(encoding='utf-8-sig')
            match = re.search(r'(?m)^name:\s*[\"\x27]?([a-z0-9_-]+)', text)
            if not text.startswith('---') or not match:
                raise ValueError(f'Invalid skill front matter: {filename.name}')
            name = match[1]
            if name in found:
                raise ValueError(f'Duplicate skill name: {name}')
            found[name] = {'name':name,'source_path':str(filename),'sha256':digest(filename)}
    if not CRITICAL.issubset(found):
        raise ValueError('Candidate lacks critical skills: ' + ', '.join(sorted(CRITICAL - found.keys())))
    return found


def prepare_marketplace(candidate: dict) -> Path:
    candidate_skills(candidate)
    stage = Path(candidate['stage_path']).resolve(strict=True)
    package = Path(candidate['package_path']).resolve(strict=True)
    relative = './' + package.relative_to(stage).as_posix()
    target = stage / '.agents/plugins/marketplace.json'
    manifest = {'name':'fable-superpowers','plugins':[{'name':'superpowers',
        'source':{'source':'local','path':relative},
        'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Developer Tools'}]}
    if target.exists():
        current = json.loads(target.read_text(encoding='utf-8-sig'))
        entries = [p for p in current.get('plugins',[]) if p.get('name') == 'superpowers']
        if current.get('name') != 'fable-superpowers' or len(entries) != 1:
            raise ValueError('Existing staging marketplace is not the intended single Superpowers source.')
        source = entries[0].get('source',{})
        if source.get('source') != 'local' or (stage / source.get('path','')).resolve() != package:
            raise ValueError('Existing staging marketplace points at another package.')
    else:
        _json_write(target, manifest)
    return target


def staging_plugin_id(candidate: dict) -> str:
    skills=candidate_skills(candidate)
    fingerprint=hashlib.sha256(json.dumps({k:v['sha256'] for k,v in sorted(skills.items())},sort_keys=True).encode()).hexdigest()[:12]
    return 'superpowers@fable-superpowers-compat-'+fingerprint


def _project_config(stage_id: str, active_plugin_ids=()) -> bytes:
    ids={'superpowers@fable-superpowers','superpowers@gigma-skills','superpowers@openai-curated-remote',
        *(x for x in active_plugin_ids if str(x).startswith('superpowers@'))}-{stage_id}
    text=''.join(f'[plugins.{json.dumps(plugin)}]\nenabled = false\n\n' for plugin in sorted(ids))
    return (text+f'[plugins.{json.dumps(stage_id)}]\nenabled = true\n').encode('utf-8')


def prepare_fixtures(candidate: dict, run_root: Path, active_plugin_ids=()) -> tuple[dict, Path]:
    stage = Path(candidate['stage_path']).resolve(strict=True)
    stage_id=staging_plugin_id(candidate)
    fixtures = {}
    for name in CASES:
        target = run_root / 'fixtures' / name
        shutil.copytree(RESOURCES / 'fixtures' / name, target)
        config = target / '.codex/config.toml'
        config.parent.mkdir()
        config.write_bytes(_project_config(stage_id,active_plugin_ids))
        repo_marketplace={'name':stage_id.split('@',1)[1],'plugins':[{'name':'superpowers',
            'source':{'source':'local','path':'./'+os.path.relpath(candidate['package_path'],target).replace('\\','/')},
            'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Developer Tools'}]}
        _json_write(target/'.agents/plugins/marketplace.json',repo_marketplace)
        for command in [['git','init','-b','main'],['git','add','.'],
            ['git','-c','user.name=Compatibility Fixture','-c','user.email=fixture@example.invalid','commit','-m','Pristine compatibility fixture']]:
            result = _cmd(command,target)
            if result['exit_code']:
                raise RuntimeError('Cannot initialize compatibility fixture: ' + result['stderr'][:500])
        fixtures[name] = target
    outside = run_root / 'outside-probe'
    outside.mkdir()
    return fixtures, outside


class TrustLease:
    """Temporarily trust only generated fixture paths, without whole-config restore."""
    def __init__(self, codex_home: Path, fixture_paths, journal_path: Path | None = None):
        self.codex_home=Path(codex_home).resolve()
        self.path = self.codex_home / 'config.toml'
        self.journal_path=Path(journal_path).resolve() if journal_path is not None else None
        self.journal_id=None
        self.journal_sha256=None
        self.paths = {_normpath(Path(p).resolve()):str(Path(p).resolve()).casefold() if os.name == 'nt' else str(Path(p).resolve()) for p in fixture_paths}
        self.owned = set()
        self.original_bytes = None
        self.exact_addition = None
        self.record = {'added':[],'removed':[],'unrelated_settings_preserved':False}

    def __enter__(self):
        raw = self.path.read_bytes()
        self.original_bytes = raw
        text = raw.decode('utf-8-sig')
        model = tomllib.loads(text)
        projects = model.get('projects',{})
        addition = ''
        newline = '\r\n' if '\r\n' in text else '\n'
        for norm, key in self.paths.items():
            existing = [(k,v) for k,v in projects.items() if _normpath(k) == norm]
            if existing:
                if len(existing) != 1 or existing[0][1].get('trust_level') != 'trusted':
                    raise RuntimeError('A generated fixture already has conflicting trust settings.')
                continue
            addition += newline + '[projects.' + json.dumps(key) + ']' + newline + 'trust_level = "trusted"' + newline
            self.owned.add(norm)
            self.record['added'].append(key)
        if addition:
            self.exact_addition = addition
            replacement=(text+addition).encode('utf-8')
            if raw.startswith(b'\xef\xbb\xbf'):replacement=b'\xef\xbb\xbf'+replacement
            self._journal_before_write(raw,replacement)
            self._replace_if_unchanged(raw,replacement)
        self.record['initial_sha256'] = hashlib.sha256(raw).hexdigest()
        return self

    def _journal_before_write(self, original: bytes, leased: bytes):
        if self.journal_path is None:
            return
        scope=self.journal_path.parent/'fixtures'
        if self.path.is_symlink() or self.path.resolve().parent!=self.codex_home:
            raise RuntimeError('Refusing a trust lease for a redirected config file.')
        if self.journal_path.name!='trust-lease.json' or self.journal_path.exists():
            raise RuntimeError('Trust journal must be new and named trust-lease.json.')
        for key in self.record['added']:
            if not _within(Path(key),scope):
                raise RuntimeError('Owned trust project is outside this lease fixture scope.')
        self.journal_id=uuid.uuid4().hex
        receipt={'schema_version':1,'lease_id':self.journal_id,'codex_home':str(self.codex_home),
            'config_path':str(self.path),'lease_root':str(self.journal_path.parent),
            'fixture_scope':str(scope),'owned_projects':list(self.record['added']),
            'original_config_base64':base64.b64encode(original).decode('ascii'),
            'original_sha256':hashlib.sha256(original).hexdigest(),
            'leased_sha256':hashlib.sha256(leased).hexdigest(),'addition':self.exact_addition}
        payload=json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf-8')
        self.journal_path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.journal_path.with_name('.trust-lease-'+uuid.uuid4().hex+'.tmp')
        try:
            descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if self.journal_path.exists():
                raise RuntimeError('Trust journal appeared concurrently; no config change made.')
            os.replace(temporary,self.journal_path)
            self.journal_sha256=hashlib.sha256(payload).hexdigest()
        finally:
            if temporary.exists():temporary.unlink()

    def _clear_journal(self):
        if self.journal_path is None or not self.journal_path.exists():
            return
        if self.journal_path.is_symlink() or digest(self.journal_path)!=self.journal_sha256:
            raise RuntimeError('Trust journal changed independently; preserving it for inspection.')
        self.journal_path.unlink()

    def _replace_if_unchanged(self, expected: bytes, replacement: bytes):
        if self.path.read_bytes() != expected:
            raise RuntimeError('Concurrent configuration change; no trust settings written.')
        temporary = self.path.with_name(self.path.name + f'.compat-{uuid.uuid4().hex}.tmp')
        created = False
        try:
            with temporary.open('xb') as stream:
                created = True
                stream.write(replacement)
                stream.flush()
                os.fsync(stream.fileno())
            if self.path.read_bytes() != expected:
                raise RuntimeError('Concurrent configuration change; no trust settings written.')
            os.replace(temporary,self.path)
        finally:
            if created and temporary.exists():
                temporary.unlink()

    def __exit__(self, exc_type, exc, tb):
        for attempt in range(3):
            raw = self.path.read_bytes()
            text = raw.decode('utf-8-sig')
            before = tomllib.loads(text)
            original_text=self.original_bytes.decode('utf-8-sig')
            if self.exact_addition and text==original_text+self.exact_addition:
                self._replace_if_unchanged(raw,self.original_bytes)
                self.record.update(removed=list(self.record['added']),unrelated_settings_preserved=True,
                    final_sha256=digest(self.path),exact_original_bytes_restored=True)
                self._clear_journal()
                return False
            headers = list(re.finditer(r'(?m)^\[[^\r\n]+\][ \t]*(?:#[^\r\n]*)?(?:\r?\n|$)',text))
            spans, removed = [], []
            for index, match in enumerate(headers):
                header = match.group().strip()
                if not header.startswith('[projects.'):
                    continue
                key = next(iter(tomllib.loads(header + '\ntrust_level = "trusted"\n')['projects']))
                if _normpath(key) not in self.owned:
                    continue
                if before['projects'][key] != {'trust_level':'trusted'}:
                    raise RuntimeError('Fixture trust entry changed concurrently; preserving it for inspection.')
                spans.append((match.start(), headers[index+1].start() if index+1 < len(headers) else len(text)))
                removed.append(key)
            replacement = text
            for start,end in reversed(spans):
                replacement = replacement[:start] + replacement[end:]
            after = tomllib.loads(replacement)
            expected = copy.deepcopy(before)
            if 'projects' in expected:
                expected['projects'] = {k:v for k,v in expected['projects'].items() if k not in removed}
                if not expected['projects'] and 'projects' not in after:
                    expected.pop('projects')
            remaining_owned={_normpath(key) for key in after.get('projects',{})}.intersection(self.owned)
            if remaining_owned:
                raise RuntimeError('Owned fixture trust entries could not be parsed safely; preserving the journal.')
            if after != expected:
                raise RuntimeError('Refusing unrelated configuration changes during trust cleanup.')
            try:
                if removed:
                    replacement_bytes=replacement.encode('utf-8')
                    if raw.startswith(b'\xef\xbb\xbf'):replacement_bytes=b'\xef\xbb\xbf'+replacement_bytes
                    self._replace_if_unchanged(raw,replacement_bytes)
                self.record.update(removed=removed,unrelated_settings_preserved=True,
                    final_sha256=digest(self.path))
                self._clear_journal()
                return False
            except RuntimeError:
                if attempt == 2:
                    raise


def recover_trust_leases(run_root: Path, codex_home: Path) -> dict:
    """Recover durable test-trust leases; invalid/modified ownership blocks recovery."""
    run_root=Path(run_root).resolve()
    codex_home=Path(codex_home).resolve(strict=True)
    config=codex_home/'config.toml'
    if config.is_symlink() or config.resolve().parent!=codex_home:
        raise RuntimeError('Refusing recovery for a redirected config file.')
    result={'passed':True,'status':'passed','recovered':[]}
    if not run_root.exists():return result
    if not run_root.is_dir():raise RuntimeError('Updater run root is not a directory.')
    for journal in sorted(run_root.rglob('trust-lease.json')):
        if journal.is_symlink() or not _within(journal,run_root):
            raise RuntimeError('Trust journal escapes the updater run directory.')
        payload=journal.read_bytes()
        receipt=json.loads(payload.decode('utf-8'))
        if receipt.get('schema_version')!=1 or not re.fullmatch(r'[0-9a-f]{32}',receipt.get('lease_id','')):
            raise RuntimeError('Unsupported trust recovery journal.')
        owner=journal.parent.resolve()
        scope=owner/'fixtures'
        for field in ['codex_home','config_path','lease_root','fixture_scope']:
            if not isinstance(receipt.get(field),str) or not Path(receipt[field]).is_absolute():
                raise RuntimeError('Trust journal paths must be absolute.')
        if (Path(receipt.get('codex_home','')).resolve()!=codex_home
                or Path(receipt.get('config_path','')).resolve()!=config.resolve()
                or Path(receipt.get('lease_root','')).resolve()!=owner
                or Path(receipt.get('fixture_scope','')).resolve()!=scope):
            raise RuntimeError('Trust journal home/config/fixture scope does not match this updater.')
        owned=receipt.get('owned_projects')
        if not isinstance(owned,list) or not owned or not all(isinstance(key,str) and Path(key).is_absolute() and Path(key).resolve()!=scope and _within(Path(key),scope) for key in owned):
            raise RuntimeError('Trust journal includes a project outside its owned fixture scope.')
        if len({_normpath(key) for key in owned})!=len(owned):
            raise RuntimeError('Duplicate owned project in trust journal.')
        original=base64.b64decode(receipt.get('original_config_base64',''),validate=True)
        if hashlib.sha256(original).hexdigest()!=receipt.get('original_sha256'):
            raise RuntimeError('Trust journal original bytes do not match their recorded hash.')
        original_model=tomllib.loads(original.decode('utf-8-sig'))
        if any(_normpath(key) in {_normpath(k) for k in original_model.get('projects',{})} for key in owned):
            raise RuntimeError('Trust journal claims a pre-existing project as owned.')
        addition=receipt.get('addition')
        if not isinstance(addition,str):raise RuntimeError('Trust journal addition is missing.')
        leased=(original.decode('utf-8-sig')+addition).encode('utf-8')
        if original.startswith(b'\xef\xbb\xbf'):leased=b'\xef\xbb\xbf'+leased
        if hashlib.sha256(leased).hexdigest()!=receipt.get('leased_sha256'):
            raise RuntimeError('Trust journal leased bytes do not match their recorded hash.')
        leased_model=tomllib.loads(leased.decode('utf-8-sig'))
        expected_model=copy.deepcopy(original_model)
        expected_model.setdefault('projects',{}).update({key:{'trust_level':'trusted'} for key in owned})
        if leased_model!=expected_model:
            raise RuntimeError('Trust journal addition changes settings beyond its owned projects.')
        lease=TrustLease(codex_home,[Path(key) for key in owned],journal_path=journal)
        lease.original_bytes=original
        lease.exact_addition=addition
        lease.owned={_normpath(key) for key in owned}
        lease.record['added']=list(owned)
        lease.journal_id=receipt['lease_id']
        lease.journal_sha256=hashlib.sha256(payload).hexdigest()
        lease.__exit__(None,None,None)
        result['recovered'].append({'journal':str(journal),**lease.record})
    return result


def _native_catalog(cwd: Path, logs: Path, codex_home: Path) -> dict:
    module = _runner_module()
    logs.mkdir(parents=True)
    client = module.AppServer(cwd, logs, time.monotonic()+90, codex_home=codex_home)
    try:
        client.rpc('initialize',{'clientInfo':{'name':'superpowers_updater_catalog','version':'0.1.0'},'capabilities':{'experimentalApi':True}},timeout=45)
        client.notify('initialized',{})
        response = client.rpc('skills/list',{'cwds':[str(cwd)],'forceReload':True},timeout=40)
        entries = [x for x in response.get('data',[]) if _normpath(x.get('cwd','')) == _normpath(cwd)]
        if len(entries) != 1 or entries[0].get('errors'):
            raise RuntimeError('Native skill catalogue is incomplete or ambiguous.')
        return {'skills':[x for x in entries[0]['skills'] if x.get('enabled')], 'errors':[]}
    finally:
        client.close()


class McpClient:
    def __init__(self, command, args, cwd: Path, env):
        self.process = subprocess.Popen([command,*args],cwd=cwd,env=env,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.messages = queue.Queue()
        self.responses = {}
        self.next_id = 0
        threading.Thread(target=self._read,daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
        finally:
            self.messages.put(None)

    def send(self, value):
        self.process.stdin.write((json.dumps(value)+'\n').encode('utf-8'))
        self.process.stdin.flush()

    def rpc(self,method,params,timeout=60):
        self.next_id += 1
        request_id = self.next_id
        self.send({'jsonrpc':'2.0','id':request_id,'method':method,'params':params})
        deadline = time.monotonic()+timeout
        while request_id not in self.responses:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Fable MCP request timed out.')
            message = self.messages.get(timeout=remaining)
            if message is None:
                raise RuntimeError('Fable MCP process closed before response.')
            if 'id' in message and 'method' not in message:
                self.responses[message['id']] = message
        response = self.responses.pop(request_id)
        if 'error' in response:
            raise RuntimeError('Fable MCP request failed: '+str(response['error'].get('message',''))[:500])
        return response['result']

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        except (OSError,subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def _tool_payload(result: dict) -> dict:
    if result.get('isError'):
        raise RuntimeError('Fable MCP tool returned an error.')
    payload = result.get('structuredContent') or result.get('structured_content')
    if isinstance(payload,dict):
        return payload
    for block in result.get('content',[]):
        if block.get('type') == 'text':
            try:
                value = json.loads(block['text'])
                if isinstance(value,dict):
                    return value
            except (ValueError,TypeError):
                pass
    raise RuntimeError('Fable MCP returned an unsupported payload.')


def _helper_probe(cwd: Path, fable_skill: dict, expected: dict, codex_home: Path, plugin_id=PLUGIN_ID) -> dict:
    # .../.agents/skills/fable5-codex/SKILL.md -> installed plugin root.
    plugin_root = Path(fable_skill['path']).parents[3]
    wiring = json.loads((plugin_root/'.mcp.json').read_text(encoding='utf-8-sig'))['mcpServers']['fable5_skills']
    command = shutil.which(wiring['command']) or wiring['command']
    args = wiring.get('args',[])
    client = McpClient(command,args,plugin_root/wiring.get('cwd','.'),_env(codex_home))
    try:
        client.rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'superpowers-updater-test','version':'0.1.0'}})
        client.send({'jsonrpc':'2.0','method':'notifications/initialized','params':{}})
        tools = client.rpc('tools/list',{})
        if not {'search_skills','read_skill'}.issubset({x['name'] for x in tools.get('tools',[])}):
            raise RuntimeError('Fable search/read tools are unavailable.')
        response = _tool_payload(client.rpc('tools/call',{'name':'search_skills','arguments':{'cwd':str(cwd),'query':'superpowers','limit':50}}))
        if response.get('partial') or response.get('next_offset') is not None:
            raise RuntimeError('Fable helper catalogue is partial or paginated beyond the supported gate.')
        found = response.get('skills',[])
        by_name = {x['name'].split(':')[-1]:x for x in found if x.get('plugin_id') == plugin_id}
        if not CRITICAL.issubset(by_name):
            raise RuntimeError('Fable helper does not see the staged candidate critical skills.')
        for name in CRITICAL:
            if _normpath(by_name[name]['path']) != _normpath(expected[name]['path']):
                raise RuntimeError('Fable helper and native catalogue select different skill versions.')
        selected = by_name['executing-plans']
        pages, offset, total, actual_sha = [],0,None,None
        while True:
            page = _tool_payload(client.rpc('tools/call',{'name':'read_skill','arguments':{'cwd':str(cwd),'skill_id':selected['id'],'offset':offset,'limit':32000}}))
            if page.get('partial'):
                raise RuntimeError('Fable skill read is partial.')
            if actual_sha is not None and page['sha256'] != actual_sha:
                raise RuntimeError('Skill changed during paginated read.')
            pages.append(page.get('content',''))
            total,actual_sha = page['total_chars'],page['sha256']
            offset = page.get('next_offset')
            if offset is None:
                break
            if len(pages)>40:
                raise RuntimeError('Unexpected skill pagination length.')
        if actual_sha != expected['executing-plans']['sha256'] or len(''.join(pages)) != total:
            raise RuntimeError('Fable read did not return the exact complete staged skill.')
        return {'total':response['total'],'partial':False,'read_skill':'executing-plans','sha256':actual_sha,'fully_read':True,'pages':len(pages)}
    finally:
        client.close()


def verify_catalog(catalog: dict, source_skills: dict, version: str, plugin_id=PLUGIN_ID) -> tuple[dict,dict]:
    entries = [x for x in catalog['skills'] if x.get('pluginId') == plugin_id]
    mapped = {}
    for skill in entries:
        name = skill['name'].split(':')[-1]
        if name not in source_skills:
            continue
        if name in mapped:
            raise RuntimeError('Native catalogue exposes duplicate candidate skill names.')
        path = Path(skill['path'])
        if version not in path.parts or digest(path) != source_skills[name]['sha256']:
            raise RuntimeError('Native catalogue selected old or altered candidate skill: '+name)
        mapped[name] = {**skill,'sha256':source_skills[name]['sha256']}
    if not CRITICAL.issubset(mapped):
        raise RuntimeError('Native catalogue lacks critical staged skills.')
    fable = [x for x in catalog['skills'] if x['name'].split(':')[-1] == 'fable5-codex' and str(x.get('pluginId','')).startswith('fable5-codex@')]
    if len(fable)!=1:
        raise RuntimeError('Exactly one enabled Fable baseline is required.')
    return mapped,fable[0]


def catalogue_fingerprint(catalog: dict) -> list:
    return sorted((x['pluginId'],x['name'],_normpath(x['path']),digest(Path(x['path']))) for x in catalog['skills'] if str(x.get('pluginId','')).startswith('superpowers@'))


def _inventory_map(inventory) -> dict:
    if isinstance(inventory,dict):
        entries=[{'path':key,'sha256':value} if isinstance(value,str) else {'path':key,**value} for key,value in inventory.items()]
    elif isinstance(inventory,list):
        entries=inventory
    else:
        raise ValueError('Expected inventory must be a list or path/hash mapping.')
    result={}
    for entry in entries:
        relative=entry.get('path',entry.get('Path'))
        sha256=entry.get('sha256',entry.get('SHA256'))
        if not isinstance(relative,str) or not isinstance(sha256,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',sha256):
            raise ValueError('Invalid expected inventory entry.')
        relative=relative.replace('\\','/')
        if Path(relative).is_absolute() or '..' in Path(relative).parts or relative in result:
            raise ValueError('Unsafe or duplicate inventory path.')
        result[relative]=sha256.lower()
    if not result:raise ValueError('Expected inventory cannot be empty.')
    return result


def materialize_staging_cache(candidate: dict, codex_home: Path, run_root: Path) -> dict:
    """Populate only a new inert, uniquely named cache namespace, never live cache."""
    package=Path(candidate['package_path']).resolve(strict=True)
    stage_id=staging_plugin_id(candidate)
    namespace=stage_id.split('@',1)[1]
    target=codex_home/'plugins/cache'/namespace/'superpowers'/candidate['version']
    expected={p.relative_to(package).as_posix():digest(p) for p in package.rglob('*') if p.is_file()}
    if candidate.get('inventory') is not None and expected!=_inventory_map(candidate['inventory']):
        raise RuntimeError('Candidate changed after its recorded source inventory.')
    if not _within(target,codex_home/'plugins/cache') or namespace=='fable-superpowers':
        raise RuntimeError('Refusing to populate an active cache namespace.')
    created=False
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(package,target)
        created=True
    actual={p.relative_to(target).as_posix():digest(p) for p in target.rglob('*') if p.is_file()}
    if actual!=expected:
        raise RuntimeError('Staging cache differs from the verified candidate; it was not overwritten.')
    record={'plugin_id':stage_id,'cache_path':str(target),'created':created,'verified_files':len(expected),'globally_enabled':False}
    _json_write(run_root/'staging-cache.json',record)
    return record


def installed_health(probe_dir: Path, expected_version: str, expected_inventory, codex_home: Path, *, plugin_id=PLUGIN_ID) -> dict:
    """Verify live native cache and actual Fable discovery/read, without models."""
    probe_dir=Path(probe_dir).resolve()
    codex_home=Path(codex_home).resolve(strict=True)
    probe_dir.mkdir(parents=True,exist_ok=False)
    policy_hash=digest(codex_home/'AGENTS.md')
    result={'passed':False,'status':'failed','expected_version':expected_version,'errors':[]}
    try:
        inventory=_inventory_map(expected_inventory)
        catalog=_native_catalog(probe_dir,probe_dir/'native-catalogue',codex_home)
        sp=[x for x in catalog['skills'] if str(x.get('pluginId','')).startswith('superpowers@')]
        if not sp or {x['pluginId'] for x in sp}!={plugin_id}:
            raise RuntimeError('Live catalogue must contain one enabled Superpowers installation.')
        package=None
        for ancestor in Path(sp[0]['path']).parents:
            manifest_path=ancestor/'.codex-plugin/plugin.json'
            if manifest_path.is_file():
                manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
                if manifest.get('name')=='superpowers' and manifest.get('version')==expected_version:
                    package=ancestor
                    break
        if package is None or not _within(package,codex_home/'plugins/cache'):
            raise RuntimeError('Cannot resolve the expected installed cache package.')
        actual={p.relative_to(package).as_posix():digest(p) for p in package.rglob('*') if p.is_file()}
        if actual!=inventory:
            raise RuntimeError('Installed package inventory differs from the verified candidate.')
        source=candidate_skills({'package_path':str(package),'stage_path':str(package.parent),'version':expected_version})
        expected,fable=verify_catalog(catalog,source,expected_version,plugin_id)
        helper=_helper_probe(probe_dir,fable,expected,codex_home,plugin_id)
        result.update(passed=True,status='passed',package_path=str(package),verified_files=len(inventory),
            critical_skills=sorted(CRITICAL),fable_helper=helper,enabled_plugin_ids=[plugin_id])
    except Exception as error:
        result['errors'].append({'type':type(error).__name__,'message':str(error)[:1500]})
    result['policy_unchanged']=digest(codex_home/'AGENTS.md')==policy_hash
    if not result['policy_unchanged']:
        result.update(passed=False,status='failed')
        result['errors'].append({'type':'SettingsChanged','message':'Global AGENTS changed during post-install health check; it was not overwritten.'})
    result['report_path']=str(probe_dir/'installed-health.json')
    _json_write(probe_dir/'installed-health.json',result)
    return result


def preflight(candidate: dict, fixtures: dict, outside: Path, run_root: Path, codex_home: Path, *, allow_empty_outside=False) -> dict:
    source_skills = candidate_skills(candidate)
    before = _native_catalog(outside,run_root/'preflight/outside-before',codex_home)
    outside_before = catalogue_fingerprint(before)
    if not outside_before and not allow_empty_outside:
        raise RuntimeError('Live Superpowers outside staging is unavailable.')
    staging_cache=materialize_staging_cache(candidate,codex_home,run_root)
    case = fixtures['approved_plan']
    catalogue = _native_catalog(case,run_root/'preflight/candidate-native',codex_home)
    stage_id=staging_plugin_id(candidate)
    sp_ids={x.get('pluginId') for x in catalogue['skills'] if str(x.get('pluginId','')).startswith('superpowers@')}
    if sp_ids!={stage_id}:
        raise RuntimeError('Fixture must select only its unique staged Superpowers installation; got '+repr(sorted(sp_ids)))
    expected,fable = verify_catalog(catalogue,source_skills,candidate['version'],stage_id)
    helper = _helper_probe(case,fable,expected,codex_home,stage_id)
    after = _native_catalog(outside,run_root/'preflight/outside-after',codex_home)
    if catalogue_fingerprint(after)!=outside_before:
        raise RuntimeError('Staging changed the live catalogue outside its test project.')
    return {'passed':True,'candidate_version':candidate['version'],'staging_plugin_id':stage_id,'candidate_skills':expected,'fable_skill':fable,
        'fable_helper':helper,'staging_cache':staging_cache,'outside_catalogue_unchanged':True,'outside_fingerprint':outside_before}


def _case_run(name: str, fixture: Path, run_root: Path, codex_home: Path) -> dict:
    output = run_root/'observations'/name
    result = _cmd([sys.executable,RESOURCES/'appserver_eval.py','--cwd',fixture,
        '--prompt-file',RESOURCES/'prompts'/f'{name}.txt','--out-dir',output,'--codex-home',codex_home],
        HERE,env=_env(codex_home),timeout=1000)
    if result['exit_code'] or not (output/'result.json').exists():
        raise RuntimeError(f'{name}: app-server run failed: '+result['stderr'][:600])
    native = json.loads((output/'result.json').read_text(encoding='utf-8'))
    if native.get('status')!='completed':
        raise RuntimeError(f'{name}: task did not complete.')
    return native


def native_items(path: Path, root_id: str) -> list:
    result = []
    seen = set()
    for number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        event = json.loads(line)
        params = event.get('params',{})
        if event.get('method')!='item/completed' or params.get('threadId')!=root_id:
            continue
        item = params.get('item',{})
        if item.get('status') in {'inProgress','in_progress'} or item.get('type')=='reasoning':
            continue
        key = item.get('id')
        if key in seen:
            continue
        seen.add(key)
        result.append({'event_line':number,**item})
    return result


def _path_expression(expression: str, variables: dict, fixture: Path | None = None) -> str | None:
    """Resolve the small set of literal PowerShell path forms seen in evidence."""
    expression=expression.strip()
    if expression.startswith('(') and expression.endswith(')'):
        expression=expression[1:-1].strip()
    joined=re.fullmatch(r'Join-Path\s+(\(Get-Location\)|\$[\w]+)\s+(.+)',expression,re.I)
    if joined:
        base=str(fixture) if joined[1].casefold()=='(get-location)' and fixture else variables.get(joined[1][1:].casefold())
        leaf=_path_expression(joined[2],variables)
        return str(Path(base)/leaf) if base and leaf else None
    # Native command strings can include the shell's quote-escaping around an
    # otherwise ordinary quoted path. Strip that wrapping, never path content.
    quoted=expression.startswith(("'",'"'))
    expression=expression.strip(' \'"\\')
    if expression.casefold() in {'$pwd','get-location'}:
        return str(fixture) if fixture else None
    if re.fullmatch(r'\$[\w]+(?:[/\\][^;|]*)?',expression):
        match=re.match(r'\$([\w]+)(.*)',expression)
        base=variables.get(match[1].casefold())
        return base+match[2] if base else None
    if not expression or any(token in expression for token in ('$',';','|','(',')',',')) or (not quoted and re.search(r'\s',expression)):
        return None
    return expression


def _path_variables(command: str, fixture: Path | None = None) -> dict:
    variables={}
    for match in re.finditer(r'\$([\w]+)\s*=\s*([^;]+)',command):
        value=_path_expression(match[2],variables,fixture)
        if value is not None:variables[match[1].casefold()]=value
    return variables


def _evidence_command(command: str) -> str:
    # The native runner can shell-quote its PowerShell -Command text. Restore
    # those quote-boundary escapes before parsing operands inside that text.
    return re.sub(r'\\+','/',command).replace("'\"'","'").replace('"\'$', '$').casefold()


def observed_skill_reads(items: list, expected: dict, fable: dict) -> dict:
    targets = {name:row for name,row in expected.items()}
    targets['fable5-codex'] = {**fable,'sha256':digest(Path(fable['path']))}
    found, pages = {},{}
    for item in items:
        if item.get('type')=='commandExecution':
            command = _evidence_command(item.get('command',''))
            variables=_path_variables(command)
            command=re.sub(r'\$([\w]+)',lambda match:variables.get(match[1],match[0]),command)
            output = item.get('aggregatedOutput','') or ''
            if not re.search(r'get-content|\bcat\b|read_text|readfile|read-file|\btype\b',command):
                continue
            for name,skill in targets.items():
                expected_text=Path(skill['path']).read_text(encoding='utf-8-sig')
                normalize=lambda text:re.sub(r'\r+\n','\n',text).replace('\ufeff','').strip()
                complete=normalize(expected_text) in normalize(output)
                # A later command may fail after this exact complete read. The
                # complete source body and resolved candidate path are evidence;
                # the aggregate shell exit status does not undo that earlier read.
                if _normpath(skill['path']).casefold() in command and complete:
                    found[name]={'event_line':item['event_line'],'path':skill['path'],'sha256':skill['sha256'],'method':'complete_file_read'}
        elif item.get('type')=='mcpToolCall' and item.get('tool')=='read_skill' and item.get('status') in {'completed','success'}:
            try:
                value = _tool_payload(item.get('result') or {})
                skill = value.get('skill',{})
                name = skill.get('name','').split(':')[-1]
                if name not in targets or _normpath(skill.get('path',''))!=_normpath(targets[name]['path']) or value.get('sha256')!=targets[name]['sha256']:
                    continue
                key = (name,value['sha256'])
                pages.setdefault(key,[]).append((value.get('offset',0),len(value.get('content','')),value.get('total_chars'),item['event_line']))
            except (ValueError,RuntimeError,KeyError):
                continue
    for (name,sha256),chunks in pages.items():
        end,total=0,None
        for offset,size,count,line in sorted(chunks):
            if total is None:total=count
            if count!=total or offset>end:break
            end=max(end,offset+size)
        if total is not None and end>=total:
            found[name]={'event_line':chunks[-1][3],'path':targets[name]['path'],'sha256':sha256,'method':'complete_mcp_read'}
    return found


def review_evidence(native: dict, *, after_event_line: int | None = None) -> dict:
    activities = native.get('native_subagent_activity',[])
    valid=[]
    for child_id,reports in native.get('child_reports',{}).items():
        phases={x.get('kind') for x in activities if x.get('agentThreadId')==child_id}
        finals=[x for x in reports if x.get('phase')=='final_answer' and len(x.get('text',''))>=100]
        for report in finals:
            text=report['text']
            plain=text.replace('**','').replace('__','')
            verdicts=re.findall(r'(?im)^\s*(?:verdict|вердикт|итог)\s*[:—-]\s*(.+)$',plain)
            verdict=verdicts[-1].strip() if verdicts else next((line.strip() for line in plain.splitlines() if line.strip()),'')
            negative=bool(re.search(r"\b(?:not|don't|cannot|can't|reject(?:ed)?|conditional|pending|defer(?:red)?|block(?:ed|ing)?|if|once|after|when|provided|unless|until)\b|subject to|as long as|request changes|needs? changes|не\s+(?:готов|одобр|утверж|рекоменд)|при условии|если",verdict,re.I))
            first_sentence=re.split(r'[.!](?:\s|$)',verdict,maxsplit=1)[0].strip().casefold()
            ready_no_findings=bool(re.fullmatch(r'ready\s*:\s*no critical,\s*important,?\s*or minor findings',first_sentence))
            approved=not negative and (first_sentence in {'approve','approved','одобрено','одобряю'} or ready_no_findings)
            severity_lines=re.findall(r'(?im)^\s*[-*]?\s*(?:critical|important|blocker|критическ\w*|важн\w*)\s*:\s*(.*)$',plain)
            unresolved=any(not re.fullmatch(r'(?:none|нет|0|no (?:issues|findings)|not found)[.!\s]*',line.strip(),re.I) for line in severity_lines)
            scope=bool(re.search(r'plan|план|diff|файл|scope',text,re.I))
            validation=bool(re.search(r'test|тест|провер',text,re.I))
            starts=[x['event_line'] for x in activities if x.get('agentThreadId')==child_id and x.get('kind')=='started' and isinstance(x.get('event_line'),int)]
            completions=[x['event_line'] for x in activities if x.get('agentThreadId')==child_id and x.get('kind')=='completed' and isinstance(x.get('event_line'),int)]
            report_line=report.get('event_line')
            eligible=[line for line in starts if (after_event_line is None or line>after_event_line)
                and isinstance(report_line,int) and line<report_line and any(end>=report_line for end in completions)]
            fresh=after_event_line is None or bool(eligible)
            if {'started','completed'}.issubset(phases) and approved and not unresolved and scope and validation and fresh:
                valid.append({'child_id':child_id,'event_line':report.get('event_line'),
                    'reviewer_start_event_line':max(eligible) if eligible else None,'verdict':text})
    if not valid:
        raise RuntimeError('No actual separate reviewer completion and substantive approval report observed.')
    return {'passed':True,'reviewers':valid}


def _writes_path(item: dict, fixture: Path, relative: str) -> bool:
    target=_normpath(fixture/relative)
    if item.get('type')=='fileChange':
        return any(_normpath(row.get('path',''))==target for row in item.get('changes',[]))
    if item.get('type')=='commandExecution':
        command=_evidence_command(item.get('command',''))
        path_mentioned=target.casefold() in command or relative.replace('\\','/').casefold() in command
        variables=_path_variables(command,fixture)
        operands=[]
        for operation in re.finditer(r'\b(?:set-content|add-content)\b\s*(?:(?:-literalpath|-path)\s*)?',command):
            tail=command[operation.end():].lstrip()
            literal=re.match(r'''(?:'([^']*)'|"([^"]*)"|(\$[\w]+(?:/[^\s;|]*)?)|([^\s;|]+))''',tail)
            operands.append(next((part for part in literal.groups() if part is not None),None) if literal else None)
        for operation in re.finditer(r'::writeall(?:text|bytes|lines)\s*\(',command):
            tail=command[operation.end():]
            depth,quote,end=0,None,len(tail)
            for index,char in enumerate(tail):
                if quote:
                    if char==quote:quote=None
                elif char in "\'\"":quote=char
                elif char=='(':depth+=1
                elif char==')':
                    if depth==0:end=index;break
                    depth-=1
                elif char==',' and depth==0:end=index;break
            operands.append(tail[:end])
        for operation in re.finditer(r'''\b(?:path|purepath)\(\s*(['"])(.*?)\1\s*\)\.write_(?:text|bytes)\s*\(''',command):
            operands.append(operation[2])
        if operands:
            resolved=[_path_expression(operand,variables,fixture) if operand is not None else None for operand in operands]
            actual=[_normpath(Path(path) if Path(path).is_absolute() else fixture/path).casefold() for path in resolved if path is not None]
            write_count=len(re.findall(r'set-content|add-content|writeall(?:text|bytes|lines)|write_(?:text|bytes)|\.write\s*\(|sed\s+-i|(?:^|\s)>>?\s*',command))
            return target.casefold() in actual or (path_mentioned and (None in resolved or write_count>len(operands)))
        write_operation=re.search(r'set-content|add-content|writeall(?:text|bytes|lines)|write_(?:text|bytes)|\.write\s*\(|sed\s+-i|(?:^|\s)>>?\s*',command)
        return bool(path_mentioned and write_operation)
    return False


def _green_test(item: dict) -> bool:
    output=item.get('aggregatedOutput') or ''
    return (item.get('type')=='commandExecution' and item.get('exitCode')==0
        and 'unittest' in item.get('command','')
        and bool(re.search(r'\bRan\s+\d+\s+tests?\b',output)) and bool(re.search(r'(?m)^OK\s*$',output)))


def tdd_ordering(name: str, fixture: Path, items: list) -> dict:
    """Use observed root events, not final claims, to check RED/write/GREEN order."""
    def writes(relative):
        return [index for index,item in enumerate(items) if _writes_path(item,fixture,relative)]
    def red_points(interface=None):
        result=[]
        for index,item in enumerate(items):
            output=item.get('aggregatedOutput') or ''
            if item.get('type')!='commandExecution' or item.get('exitCode') in [None,0] or 'unittest' not in item.get('command',''):
                continue
            if interface is None:
                valid='190' in output and '180' in output and bool(re.search(r'AssertionError|FAIL(?:ED)?',output))
            else:
                valid=interface in output and bool(re.search(r'ImportError|AttributeError|NameError|cannot import name|has no attribute',output))
            if valid:result.append(index)
        return result
    green=[index for index,item in enumerate(items) if _green_test(item)]
    tasks=[('discounts.py','tests/test_discounts.py',None)] if name=='bug_fix' else [
        ('invoice_helpers.py','tests/test_invoice_helpers.py','normalize_currency'),
        ('invoice_cli.py','tests/test_invoice_cli.py','format_invoice')]
    proof=[]
    previous_green=-1
    for module,test_file,interface in tasks:
        production=writes(module)
        test_writes=writes(test_file)
        if not production or not test_writes:
            raise RuntimeError(f'{name}: no observable test/implementation writes for {module}.')
        red=[i for i in red_points(interface) if previous_green<i<min(production) and any(j<i for j in test_writes)]
        if not red:
            raise RuntimeError(f'{name}: genuine RED must precede the first production write for {module}.')
        after=[i for i in green if i>max(production)]
        if not after:
            raise RuntimeError(f'{name}: GREEN must follow implementation for {module}.')
        previous_green=min(after)
        proof.append({'module':module,'red_event_line':items[red[0]]['event_line'],
            'first_production_event_line':items[min(production)]['event_line'],
            'last_production_event_line':items[max(production)]['event_line'],
            'green_event_line':items[previous_green]['event_line']})
    return {'passed':True,'tasks':proof}


def _tree_status(fixture: Path, codex_home: Path) -> list:
    result=_fixture_git(['status','--porcelain=v1','-z','--untracked-files=all'],fixture,codex_home)
    if result['exit_code']:raise RuntimeError('Cannot inspect fixture tree.')
    return [x[3:] for x in result['stdout'].split('\0') if x]


def assess_case(name: str, fixture: Path, native: dict, observed: Path, expected: dict, fable: dict, codex_home: Path | None = None) -> dict:
    if native.get('unexpected_client_requests'):
        raise RuntimeError(f'{name}: an interactive approval/input request occurred in an unattended compatibility trial.')
    codex_home=_fixture_home(fable,codex_home)
    items=native_items(observed/'appserver-events.jsonl',native['thread_id'])
    loaded=observed_skill_reads(items,expected,fable)
    if 'fable5-codex' not in loaded or not REQUIRED_BY_CASE[name].issubset(loaded):
        raise RuntimeError(f'{name}: required instructions were not actually read from this candidate.')
    messages=[x for x in items if x.get('type')=='agentMessage']
    questions=sum(x.get('text','').count('?') for x in messages)
    if questions!=(1 if name=='ambiguous_metric' else 0):
        raise RuntimeError(f'{name}: unexpected or repeated question count ({questions}).')
    for item in items:
        if item.get('type')=='fileChange':
            for change in item.get('changes',[]):
                if not _within(Path(change['path']),fixture):
                    raise RuntimeError(f'{name}: file mutation escaped the fixture.')
    worktrees=_fixture_git(['worktree','list','--porcelain'],fixture,codex_home)
    if worktrees['exit_code'] or worktrees['stdout'].count('worktree ')!=1:
        raise RuntimeError(f'{name}: an unnecessary worktree was created.')
    paths=_tree_status(fixture,codex_home)
    forbidden=re.compile(r'(?:^|/)(?:docs/(?:superpowers/)?(?:plans|specs)/|[^/]*(?:design|implementation.plan)[^/]*\.md)',re.I)
    if any(forbidden.search(path.replace('\\','/')) for path in paths):
        raise RuntimeError(f'{name}: a redundant design or plan was created.')
    checks={'passed':True,'loaded_skills':loaded,'question_count':questions,'changed_paths':paths}
    if name in {'local_research','ambiguous_metric'}:
        if paths:raise RuntimeError(f'{name}: read-only fixture was modified.')
        if name=='local_research':
            text='\n'.join(x.get('text','') for x in messages)
            if 'SQLite' not in text or 'memory-queue.md:' not in text or 'sqlite-queue.md:' not in text:
                raise RuntimeError('Research answer lacks the supported choice or source-line citations.')
            forbidden_skills={'brainstorming','writing-plans','executing-plans','test-driven-development','using-git-worktrees'}
            if forbidden_skills.intersection(loaded):raise RuntimeError('Research started an engineering workflow.')
    elif name=='small_config':
        if set(paths)!={'settings.json'} or json.loads((fixture/'settings.json').read_text())!={'retry_count':5,'timeout_seconds':10,'log_level':'info'}:
            raise RuntimeError('Mechanical edit changed more than the requested setting.')
    else:
        checks['tdd_ordering']=tdd_ordering(name,fixture,items)
        test=_fixture_python(['-m','unittest','discover','-s','tests','-v'],fixture,codex_home)
        checks['independent_tests']=test
        if test['exit_code']:raise RuntimeError(f'{name}: independent tests failed.')
        if name=='bug_fix':
            code='from discounts import apply_discount\nassert apply_discount(200,10)==180\nassert apply_discount(200,0)==200\nassert apply_discount(200,100)==0\nfor p in [-1,101]:\n try: apply_discount(200,p)\n except ValueError: pass\n else: raise AssertionError("invalid percentage accepted")\n'
        else:
            code='from invoice_helpers import normalize_currency,invoice_total\nfrom invoice_cli import format_invoice,format_total\nassert normalize_currency(" usd ")=="USD"\nassert normalize_currency("eur")=="EUR"\nassert format_invoice([1.25,2.75]," usd ")=="USD 4.00"\nassert format_invoice([],"eur")=="EUR 0.00"\nassert invoice_total([1,2])==3\nassert format_total(4)=="4.00"\nfor c in ["","US","USDD","12x","éur"]:\n try: normalize_currency(c)\n except ValueError: pass\n else: raise AssertionError("invalid currency accepted")\n'
            original=_fixture_git(['show','HEAD:APPROVED_PLAN.md'],fixture,codex_home)['stdout'].replace('\r\n','\n')
            actual=(fixture/'APPROVED_PLAN.md').read_text(encoding='utf-8').replace('\r\n','\n').replace('- [x]','- [ ]')
            if actual!=original:raise RuntimeError('Approved plan requirements changed or a new plan replaced it.')
            checks['independent_review']=review_evidence(native,after_event_line=max(task['last_production_event_line'] for task in checks['tdd_ordering']['tasks']))
        direct=_fixture_python(['-c',code],fixture,codex_home)
        if direct['exit_code']:raise RuntimeError(f'{name}: direct acceptance checks failed.')
        checks['direct_contract_passed']=True
    diff=_fixture_git(['diff','--check'],fixture,codex_home)
    if diff['exit_code']:raise RuntimeError(f'{name}: diff validation failed.')
    return checks


def _execute(candidate: dict, run_root: Path, codex_home: Path, *, models: bool, allow_empty_outside=False) -> dict:
    run_root=Path(run_root).resolve()
    codex_home=Path(codex_home).resolve(strict=True)
    if run_root.exists():raise ValueError('Compatibility run directory must be new.')
    run_root.mkdir(parents=True)
    policy=codex_home/'AGENTS.md'
    policy_hash=digest(policy)
    result={'passed':False,'status':'failed','candidate_version':candidate.get('version'),'policy_sha256':policy_hash,'cases':{},'errors':[]}
    lease=None
    try:
        prepare_marketplace(candidate)
        active_ids=tomllib.loads((codex_home/'config.toml').read_text(encoding='utf-8-sig')).get('plugins',{})
        fixtures,outside=prepare_fixtures(candidate,run_root,active_ids)
        config_hashes={name:digest(path/'.codex/config.toml') for name,path in fixtures.items()}
        with TrustLease(codex_home,fixtures.values(),journal_path=run_root/'trust-lease.json') as lease:
            selected=preflight(candidate,fixtures,outside,run_root,codex_home,allow_empty_outside=allow_empty_outside)
            result['preflight']=selected
            if models:
                result['model_sandbox_guard']=_fixture_python(['-c','pass'],fixtures['approved_plan'],codex_home)
                if result['model_sandbox_guard']['exit_code']:
                    raise RuntimeError('Native sandbox guard failed before model trials.')
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures={pool.submit(_case_run,name,fixture,run_root,codex_home):(name,fixture) for name,fixture in fixtures.items()}
                    for future in as_completed(futures):
                        name,fixture=futures[future]
                        try:
                            native=future.result()
                            if digest(fixture/'.codex/config.toml')!=config_hashes[name]:
                                raise RuntimeError('Candidate selection configuration changed during the trial.')
                            result['cases'][name]=assess_case(name,fixture,native,run_root/'observations'/name,selected['candidate_skills'],selected['fable_skill'],codex_home=codex_home)
                        except Exception as error:
                            result['cases'][name]={'passed':False,'error':str(error)[:1000]}
                after=_native_catalog(outside,run_root/'preflight/outside-final',codex_home)
                if catalogue_fingerprint(after)!=selected['outside_fingerprint']:
                    raise RuntimeError('Candidate trials changed the active global skill source.')
            result['passed']=all(case.get('passed') for case in result['cases'].values()) if models else True
            result['status']='passed' if result['passed'] else 'failed'
    except Exception as error:
        result['errors'].append({'type':type(error).__name__,'message':str(error)[:1500]})
        result['passed']=False
        result['status']='failed'
    finally:
        result['trust_cleanup']=lease.record if lease else None
        result['policy_unchanged']=digest(policy)==policy_hash
        if not result['policy_unchanged']:
            result['passed']=False
            result['status']='failed'
            result['errors'].append({'type':'SettingsChanged','message':'Global AGENTS changed during compatibility testing; it was not overwritten.'})
        result['report_path']=str(run_root/'compatibility.json')
        _json_write(run_root/'compatibility.json',result)
    return result


def run_compatibility(candidate: dict, run_root: Path, codex_home: Path, *, allow_empty_outside=False) -> dict:
    return _execute(candidate,run_root,codex_home,models=True,allow_empty_outside=allow_empty_outside)


def probe_candidate(candidate: dict, run_root: Path, codex_home: Path) -> dict:
    return _execute(candidate,run_root,codex_home,models=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['probe','run'])
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--run-root',required=True)
    parser.add_argument('--codex-home',required=True)
    args=parser.parse_args()
    candidate=json.loads(Path(args.candidate).read_text(encoding='utf-8-sig'))
    fn=probe_candidate if args.mode=='probe' else run_compatibility
    result=fn(candidate,Path(args.run_root),Path(args.codex_home))
    print(json.dumps({'passed':result['passed'],'status':result['status'],'report_path':result['report_path'],'errors':result['errors']},ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
