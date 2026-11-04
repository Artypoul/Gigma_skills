"""Transactional local Superpowers updates; no scheduler or model assumptions."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tomllib
import uuid

PLUGIN_ID = 'superpowers@fable-superpowers'

class UpdateError(RuntimeError): pass
class Busy(UpdateError): pass
class Conflict(UpdateError): pass

def managed_plugin_id(root):
    manifest=Path(root)/'.agents/plugins/marketplace.json'
    if not manifest.exists():return PLUGIN_ID
    name=json.loads(manifest.read_text(encoding='utf-8-sig')).get('name')
    if name not in {'gigma-skills','fable-superpowers'}:
        raise Conflict('Unexpected managed marketplace identity.')
    return 'superpowers@'+name

def fable_identity(settings):
    """Select the one enabled Fable without assuming its marketplace name."""
    matches=[name for name,value in settings.get('plugins',{}).items()
        if name.startswith('fable5-codex@') and value.get('enabled') is True]
    if len(matches)!=1:
        raise Conflict('Exactly one enabled Fable baseline is required; user settings are preserved.')
    return matches[0]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inventory(root):
    root = Path(root)
    result = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise UpdateError('Package contains a symbolic link.')
        if path.is_file():
            result.append({'path':path.relative_to(root).as_posix(),'sha256':digest(path),'size':path.stat().st_size})
    return result

def version_key(value):
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value)
    if not match:
        raise UpdateError('Only stable semantic versions are eligible.')
    return tuple(map(int, match.groups()))

def atomic_write(path, data, expected=None):
    path = Path(path)
    if expected is not None and path.read_bytes() != expected:
        raise Conflict('File changed concurrently; no replacement performed.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if expected is not None and path.read_bytes() != expected:
            raise Conflict('File changed while preparing replacement.')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def write_json(path, value):
    atomic_write(path, (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())

@contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            raise Busy('Another update is already running.') from error
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)

class Manager:
    def __init__(self, root, home, backend, compatibility, latest, stage, failpoint=None, recovery=None):
        self.root, self.home = Path(root).resolve(), Path(home).resolve()
        self.backend, self.compatibility = backend, compatibility
        self.latest, self.stage, self.failpoint = latest, stage, failpoint
        self.recovery = recovery
        self.marketplace = self.root / '.agents/plugins/marketplace.json'
        self.state_dir = self.root / 'updates'
        self.journal = self.state_dir / 'transaction.json'

    @property
    def plugin_id(self):return managed_plugin_id(self.root)

    def source_path(self, manifest):
        entries = [p for p in manifest['plugins'] if p['name']=='superpowers']
        if len(entries)!=1 or entries[0]['source'].get('source')!='local':
            raise UpdateError('Unexpected marketplace plugin source.')
        path=(self.root/entries[0]['source']['path']).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise UpdateError('Package source escapes the managed marketplace.')
        return path

    def preferences(self):
        settings=tomllib.loads((self.home/'config.toml').read_text(encoding='utf-8-sig'))
        for plugin in [self.plugin_id,fable_identity(settings)]:
            if settings.get('plugins',{}).get(plugin,{}).get('enabled') is not True:
                raise Conflict('The required plugin was disabled; user settings are preserved.')
        return {'agents_sha256':digest(self.home/'AGENTS.md'),'settings':settings}

    def check_preferences(self, before):
        if self.preferences()!=before:
            raise Conflict('Global instructions or settings changed; update activation aborted.')

    def fault(self, point):
        if self.failpoint:
            self.failpoint(point)

    def check_installation(self, transaction):
        """Compare native observations only with verified transaction states."""
        before=transaction.get('old_installation')
        if before is None:
            raise Conflict('Transaction has no verified native installation snapshot; preserving user state.')
        current=self.backend.installation_snapshot()
        sources={(transaction['old_version'],os.path.normcase(str(Path(transaction['old_source']).resolve()))):transaction['old_inventory'],
            (transaction['new_version'],os.path.normcase(str(Path(transaction['new_source']).resolve()))):transaction['new_inventory']}
        if transaction.get('rollback_source'):
            sources[(transaction['old_version'],os.path.normcase(str(Path(transaction['rollback_source']).resolve())))]=transaction['old_inventory']
        caches=deepcopy(before['caches']);caches[transaction['new_version']]=transaction['new_inventory']
        allowed_caches=[transaction['new_installation']['caches']] if transaction.get('new_installation') else [before['caches'],caches]
        source=(current['version'],os.path.normcase(current['source']))
        if (current['identity']!=before['identity']
                or source not in sources or current['source_inventory']!=sources[source]
                or current['caches'] not in allowed_caches
                or current['installed_cache'] not in [before['installed_cache'],transaction['new_version']]):
            raise Conflict('Native installation changed independently; preserving user state.')
        return current

    def rollback(self, transaction):
        old=bytes.fromhex(transaction['old_marketplace_hex'])
        new=bytes.fromhex(transaction['new_marketplace_hex'])
        current=self.marketplace.read_bytes()
        prior_recovery=bytes.fromhex(transaction['rollback_marketplace_hex']) if transaction.get('rollback_marketplace_hex') else None
        if current not in [old,new,prior_recovery]:
            raise Conflict('Marketplace changed independently; rollback will not overwrite it.')
        self.check_installation(transaction)
        old_path=Path(transaction['old_source'])
        restore_bytes=old
        if not old_path.is_dir() or inventory(old_path)!=transaction['old_inventory']:
            old_path=Path(transaction['backup'])/'package'
            if not old_path.is_dir() or inventory(old_path)!=transaction['old_inventory']:
                raise UpdateError('Neither previous source nor backup matches the verified package.')
            recovery=json.loads(old.decode('utf-8-sig'))
            next(p for p in recovery['plugins'] if p['name']=='superpowers')['source']['path']='./'+old_path.relative_to(self.root).as_posix()
            restore_bytes=(json.dumps(recovery,ensure_ascii=False,indent=2)+'\n').encode()
        # Verify the recovery target before switching away from the candidate.
        transaction.update(phase='recovering',rollback_source=str(old_path),rollback_marketplace_hex=restore_bytes.hex())
        write_json(self.journal,transaction)
        if current!=restore_bytes: atomic_write(self.marketplace,restore_bytes,expected=current)
        settings=tomllib.loads((self.home/'config.toml').read_text(encoding='utf-8-sig'))
        try: fable=fable_identity(settings)
        except Conflict: fable=None
        enabled=fable is not None and settings.get('plugins',{}).get(self.plugin_id,{}).get('enabled') is True
        if enabled:
            self.check_installation(transaction)
            self.backend.install(old_path,transaction['old_version'],transaction['old_inventory'])
            health=self.backend.health(old_path,transaction['old_version'],transaction['old_inventory'])
        else:
            # A concurrent user disable is intentional. Restoring the verified
            # source is safe; reinstalling could re-enable it and is forbidden.
            health={'status':'verified_source_restored_user_disable_preserved','version':transaction['old_version'],'source':str(old_path)}
        provenance=self.root/'provenance.json'
        previous=transaction.get('old_provenance_hex')
        replacement=transaction.get('new_provenance_hex')
        if replacement is not None:
            current_provenance=provenance.read_bytes() if provenance.exists() else None
            old_provenance=bytes.fromhex(previous) if previous is not None else None
            new_provenance=bytes.fromhex(replacement)
            if current_provenance not in [old_provenance,new_provenance]:
                raise Conflict('Provenance changed independently; rollback will not overwrite it.')
            if current_provenance==new_provenance:
                if old_provenance is None: provenance.unlink()
                else: atomic_write(provenance,old_provenance,expected=new_provenance)
        transaction.update(phase='rolled_back',rollback_health=health)
        write_json(self.journal,transaction)
        return health

    def recover_pending(self,force=False):
        if not self.journal.exists(): return None
        transaction=json.loads(self.journal.read_text(encoding='utf-8'))
        if transaction.get('phase')=='recovery_required' and not force:
            raise UpdateError('A previous recovery requires attention; no further update attempted.')
        if transaction.get('phase') in ['prepared','switched','installed','recovering'] or (force and transaction.get('phase')=='recovery_required'):
            try:
                self.rollback(transaction)
            except Exception as error:
                transaction.update(phase='recovery_required',rollback_error=str(error))
                write_json(self.journal,transaction)
                raise UpdateError('Automatic recovery could not be verified; user state and package backup are preserved.') from error
            return {'status':'recovered','version':transaction['old_version']}
        return None

    def run(self):
        with exclusive_lock(self.state_dir/'update.lock'):
            if self.recovery:
                self.recovery()
            recovered=self.recover_pending()
            if recovered: return recovered
            before=self.preferences()
            old_bytes=self.marketplace.read_bytes()
            provenance_path=self.root/'provenance.json'
            old_provenance=provenance_path.read_bytes() if provenance_path.exists() else None
            old_manifest=json.loads(old_bytes.decode('utf-8-sig'))
            old_source=self.source_path(old_manifest)
            old_files=inventory(old_source)
            old_package=json.loads((old_source/'.codex-plugin/plugin.json').read_text(encoding='utf-8-sig'))
            old_version=old_package['version']
            release=self.latest()
            if version_key(release['version'])<=version_key(old_version):
                return {'status':'unchanged','version':old_version,'latest':release['version']}
            context={'release':release,'preferences':before,'backend':self.backend.context() if hasattr(self.backend,'context') else None}
            signature=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
            held_file=self.state_dir/'held.json'
            if held_file.exists():
                held=json.loads(held_file.read_text(encoding='utf-8'))
                if held.get('signature')==signature:
                    return {'status':'held','version':old_version,'candidate':release['version'],'new_failure':False,'report':held['report']}
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
            run_dir=self.state_dir/'runs'/stamp
            run_dir.mkdir(parents=True)
            old_installation=self.backend.installation_snapshot()
            if (old_installation['version']!=old_version
                    or os.path.normcase(old_installation['source'])!=os.path.normcase(str(old_source))
                    or old_installation['source_inventory']!=old_files
                    or old_installation['caches'].get(old_version)!=old_files
                    or old_installation['installed_cache'] not in [None,old_version]):
                raise Conflict('Native installation differs from the verified baseline; activation aborted.')
            candidate=self.stage(release,run_dir/'candidate',baseline_package=old_source)
            if candidate['version']!=release['version']:
                raise UpdateError('Candidate version differs from selected release.')
            candidate_path=Path(candidate['package_path'])
            files=inventory(candidate_path)
            write_json(run_dir/'candidate.json',{**candidate,'verified_inventory':files})
            checks=self.compatibility(candidate,run_dir/'compatibility',self.home)
            if checks.get('status')!='passed':
                write_json(run_dir/'rejected.json',{'reason':'compatibility_failed','checks':checks})
                write_json(held_file,{'signature':signature,'report':str(run_dir/'rejected.json')})
                return {'status':'held','version':old_version,'candidate':candidate['version'],'reason':'compatibility_failed','new_failure':True,'report':str(run_dir/'rejected.json')}
            if inventory(candidate_path)!=files:
                raise UpdateError('Candidate changed during compatibility verification.')
            self.check_preferences(before)
            if self.marketplace.read_bytes()!=old_bytes or inventory(old_source)!=old_files:
                raise Conflict('Active package source changed during verification.')
            destination=self.root/'packages'/(candidate['version']+'-'+candidate['commit'][:12])
            if destination.exists():
                if inventory(destination)!=files: raise Conflict('Immutable version directory has different content.')
            else:
                destination.parent.mkdir(parents=True,exist_ok=True)
                temporary=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.staging')
                shutil.copytree(candidate_path,temporary)
                if inventory(temporary)!=files: raise UpdateError('Prepared versioned copy differs from candidate.')
                if destination.exists(): raise Conflict('Version directory appeared concurrently.')
                os.replace(temporary,destination)
            if inventory(destination)!=files: raise UpdateError('Versioned copy differs from verified candidate.')
            backup=self.root/'backups'/stamp
            backup.mkdir(parents=True)
            shutil.copytree(old_source,backup/'package')
            if inventory(backup/'package')!=old_files: raise UpdateError('Backup verification failed.')
            (backup/'marketplace.json').write_bytes(old_bytes)
            shutil.copy2(self.home/'AGENTS.md',backup/'AGENTS.md')
            shutil.copy2(self.home/'config.toml',backup/'config.toml')
            replacement=deepcopy(old_manifest)
            next(p for p in replacement['plugins'] if p['name']=='superpowers')['source']['path']='./'+destination.relative_to(self.root).as_posix()
            new_bytes=(json.dumps(replacement,ensure_ascii=False,indent=2)+'\n').encode()
            provenance_value={'version':candidate['version'],'origin':candidate,'sourceFiles':files,'compatibility_report':str(run_dir/'compatibility'),'backup':str(backup)}
            new_provenance=(json.dumps(provenance_value,ensure_ascii=False,indent=2)+'\n').encode()
            if old_provenance is not None: (backup/'provenance.json').write_bytes(old_provenance)
            if self.backend.installation_snapshot()!=old_installation:
                raise Conflict('Native installation changed during compatibility verification; activation aborted.')
            if candidate['version'] in old_installation['caches'] and old_installation['caches'][candidate['version']]!=files:
                raise Conflict('Native candidate cache differs from the verified package; activation aborted.')
            transaction={'phase':'prepared','old_version':old_version,'new_version':candidate['version'],'old_source':str(old_source),'new_source':str(destination),'old_inventory':old_files,'new_inventory':files,'old_installation':old_installation,'old_marketplace_hex':old_bytes.hex(),'new_marketplace_hex':new_bytes.hex(),'old_provenance_hex':old_provenance.hex() if old_provenance is not None else None,'new_provenance_hex':new_provenance.hex(),'backup':str(backup),'candidate':candidate,'compatibility':checks,'preferences_sha256':before['agents_sha256']}
            write_json(self.journal,transaction)
            try:
                self.check_preferences(before)
                self.check_installation(transaction)
                atomic_write(self.marketplace,new_bytes,expected=old_bytes)
                transaction['phase']='switched';write_json(self.journal,transaction)
                self.fault('after_pointer')
                self.check_installation(transaction)
                installed=self.backend.install(destination,candidate['version'],files)
                snapshot=self.check_installation(transaction)
                if snapshot['caches'].get(candidate['version'])!=files:
                    raise UpdateError('Native installation did not materialize the verified candidate cache.')
                transaction['phase']='installed';transaction['installation']=installed;transaction['new_installation']=snapshot;write_json(self.journal,transaction)
                self.fault('after_install')
                health=self.backend.health(destination,candidate['version'],files)
                self.fault('after_health')
                self.check_preferences(before)
                if old_provenance is None and provenance_path.exists(): raise Conflict('Provenance appeared concurrently.')
                atomic_write(provenance_path,new_provenance,expected=old_provenance)
                self.fault('after_provenance')
                transaction.update(phase='complete',health=health)
                write_json(self.journal,transaction)
                return {'status':'updated','from':old_version,'version':candidate['version'],'backup':str(backup),'checks':checks,'health':health}
            except Exception as error:
                try:
                    health=self.rollback(transaction)
                except Exception as rollback_error:
                    transaction.update(phase='recovery_required',error=type(error).__name__,rollback_error=str(rollback_error))
                    write_json(self.journal,transaction)
                    raise UpdateError('Automatic rollback could not be verified; previous package backup is preserved.') from rollback_error
                return {'status':'rolled_back','version':old_version,'candidate':candidate['version'],'reason':str(error),'rollback_health':health,'backup':str(backup)}
