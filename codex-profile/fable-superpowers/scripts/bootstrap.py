"""Portable Windows setup. Plan is read-only; install never schedules itself."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'updater'))
from core import Conflict, UpdateError, atomic_write, digest, exclusive_lock, inventory, write_json
from native import NativeBackend
from source import latest_release, stage_release

PLUGIN='superpowers@gigma-skills'
FABLE='fable5-codex@gigma-skills'


def settings(home):
    path=Path(home)/'config.toml'
    return tomllib.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def normpath(value):
    return os.path.normcase(str(Path(str(value).removeprefix('\\\\?\\')).resolve()))


def registry_path(row):
    return row.get('root') or row.get('path') or row.get('marketplaceSource',{}).get('source')


def create_owned(path,data):
    """Publish complete bytes without replacing an independently created file."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as output:
            output.write(data);output.flush();os.fsync(output.fileno())
        os.link(temporary,path)
    except FileExistsError as error:raise Conflict('Destination appeared concurrently; it was preserved.') from error
    finally:temporary.unlink(missing_ok=True)


def requirements():
    """No credentials are read or copied. Actual access/delegation is gated by trials."""
    if os.name!='nt':raise UpdateError('This setup currently supports Windows only.')
    if sys.version_info<(3,11):raise UpdateError('Python 3.11 or newer is required.')
    versions={}
    for executable,args in [('node',['--version']),('git',['--version']),('codex',['--version'])]:
        command=shutil.which(executable)
        if not command:raise UpdateError(executable+' is unavailable on PATH.')
        result=subprocess.run([command,*args],capture_output=True,text=True,timeout=30)
        if result.returncode:raise UpdateError('Could not verify '+executable+'.')
        versions[executable]=result.stdout.strip()
    try:node_major=int(versions['node'].lstrip('v').split('.')[0])
    except ValueError as error:raise UpdateError('Unrecognized Node.js version.') from error
    if node_major<20:raise UpdateError('Node.js 20 or newer is required.')
    return {'status':'passed','versions':versions,'model_access_delegation_and_mxc':'required_in_compatibility_trials'}


def runtime_files(source):
    """Only packaged runtime code and pristine fixtures; never deployment receipts."""
    source=Path(source)
    allowed={'core.py','native.py','source.py','compatibility.py','update.py','README.txt','Update-Superpowers.ps1',
        'test_core.py','test_native.py','test_source.py','test_compatibility.py','test_sandbox.py'}
    result={}
    for path in source.rglob('*'):
        relative=path.relative_to(source).as_posix()
        if '__pycache__' in path.parts or path.suffix=='.pyc':continue
        if path.is_symlink():raise Conflict('Runtime source contains a symbolic link.')
        if path.is_file() and (relative in allowed or relative.startswith('resources/')):
            result[relative]=digest(path)
    if not result or 'update.py' not in result:raise UpdateError('Packaged updater is unavailable.')
    return result


def deploy_runtime(source,root,*,apply):
    source,root=Path(source),Path(root)
    destination=root/'maintenance';record=root/'updates/runtime-owned.json';pending=root/'updates/runtime-transaction.json'
    desired=runtime_files(source)
    owned={}
    if record.exists():owned=json.loads(record.read_text())['files']
    elif (destination/'deployment.json').exists():owned=json.loads((destination/'deployment.json').read_text())['files']
    transaction=json.loads(pending.read_text()) if pending.exists() else None
    if transaction and transaction.get('phase')=='prepared':
        if transaction.get('new')!=desired:raise Conflict('An interrupted runtime deployment has different source; preserve it for recovery.')
        old=transaction['old']
    else:old=owned
    before={}
    for relative,sha in desired.items():
        target=destination/relative
        if any(part.is_symlink() for part in [target,*target.parents] if part!=root.parent):
            raise Conflict('Managed runtime path is a symbolic link.')
        current=digest(target) if target.exists() else None
        before[relative]=current
        # Even an identical file requires ownership before it may be adopted.
        if current is not None and relative not in old and not (transaction and transaction.get('phase')=='prepared' and current==sha):
            raise Conflict('Runtime destination contains an unowned file: '+relative)
        if current is not None and current!=old.get(relative) and not (transaction and transaction.get('phase')=='prepared' and current==sha):
            raise Conflict('Managed runtime was modified: '+relative)
    changed=any(before[key]!=sha for key,sha in desired.items()) or not record.exists()
    if not apply:return {'changed':changed,'files':len(desired)}
    if changed:
        write_json(pending,{'phase':'prepared','old':old,'new':desired})
        backup=root/'updates/runtime-backups'/uuid.uuid4().hex
        for relative,sha in desired.items():
            target=destination/relative
            current=target.read_bytes() if target.exists() else None
            if current is not None and hashlib.sha256(current).hexdigest()!=before[relative]:raise Conflict('Runtime changed during deployment.')
            if current is not None and hashlib.sha256(current).hexdigest()==sha:continue
            if current is not None:
                saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(current)
            if current is None and target.exists():raise Conflict('Runtime file appeared concurrently.')
            replacement=(source/relative).read_bytes()
            if hashlib.sha256(replacement).hexdigest()!=sha:raise Conflict('Packaged runtime changed during deployment.')
            if current is None:create_owned(target,replacement)
            else:atomic_write(target,replacement,expected=current)
        if any(digest(destination/relative)!=sha for relative,sha in desired.items()):raise Conflict('Deployed runtime changed before ownership was recorded.')
        write_json(record,{'schema':1,'files':desired})
        write_json(pending,{'phase':'complete','old':old,'new':desired})
    return {'changed':changed,'files':len(desired),'manifest':str(record)}


class Setup:
    def __init__(self,home,marketplace_root=None,*,root=None,backend=None,runtime_source=None,policy_source=None,
                 requirements=requirements,latest=latest_release,stage=stage_release,compatibility=None,failpoint=None,
                 adopt_marketplace=False):
        self.home=Path(home).resolve();self.root=Path(root).resolve() if root else self.home/'local-plugins/gigma-skills'
        default_catalog=HERE.parents[2]
        self.catalog=Path(marketplace_root).resolve() if marketplace_root else (default_catalog if (default_catalog/'.agents/plugins/marketplace.json').is_file() else None)
        self.adopt_marketplace=adopt_marketplace
        self.backend=backend or NativeBackend(self.root,self.home)
        self.runtime_source=Path(runtime_source) if runtime_source else HERE/'updater'
        self.policy_source=Path(policy_source) if policy_source else HERE.parent/'assets/cooperation-AGENTS.md'
        self.requirements,self.latest,self.stage=requirements,latest,stage
        if compatibility is None:
            from compatibility import run_compatibility
            compatibility=run_compatibility
        self.compatibility,self.failpoint=compatibility,failpoint
        self.state=self.root/'updates';self.journal=self.state/'bootstrap-transaction.json'
        self.marketplace=self.root/'.agents/plugins/marketplace.json'

    def catalog_manifest(self):
        if not self.catalog:raise Conflict('Supply --marketplace-root pointing at the complete Gigma Skills checkout.')
        value=json.loads((self.catalog/'.agents/plugins/marketplace.json').read_text(encoding='utf-8-sig'))
        names=[x.get('name') for x in value.get('plugins',[])]
        if value.get('name')!='gigma-skills' or len(names)!=len(set(names)) or not {'fable5-codex','superpowers'}.issubset(names):
            raise Conflict('The supplied repository must contain the full Gigma catalog with Fable and Superpowers.')
        lock=json.loads((self.catalog/'external-plugins.lock.json').read_text(encoding='utf-8-sig'))
        for name in ['fable5-codex','superpowers']:
            entries=[x for x in lock.get('plugins',[]) if x.get('name')==name]
            item=next(x for x in value['plugins'] if x['name']==name)
            if len(entries)!=1 or item.get('source')!=entries[0].get('source') or item['source'].get('source')!='url' or not item['source'].get('sha'):
                raise Conflict('Gigma external plugin source must match its pinned lock: '+name)
        result=deepcopy(value)
        for item in result['plugins']:
            source=item.get('source',{})
            if source.get('source')=='local':source['path']=str((self.catalog/source['path']).resolve())
        return result

    def initial_release(self):
        lock=json.loads((self.catalog/'external-plugins.lock.json').read_text(encoding='utf-8-sig'))
        pinned=next(x for x in lock['plugins'] if x['name']=='superpowers')
        match=re.fullmatch(r'https://github\.com/([^/]+/[^/]+?)(?:\.git)?',pinned['source']['url'])
        if not match or not pinned.get('version'):raise Conflict('The pinned Superpowers release lacks an eligible upstream/version.')
        return {'repo':match[1],'version':pinned['version'],'tag':'v'+pinned['version'],'expected_commit':pinned['source']['sha']}

    @staticmethod
    def without_sp_source(value):
        result=deepcopy(value)
        for item in result['plugins']:
            if item['name']=='superpowers':item['source']={}
        return result

    def pending_catalog(self):
        journal=self.state/'marketplace-transaction.json'
        if not journal.exists():return None
        value=json.loads(journal.read_text())
        if value.get('phase')!='prepared':return None
        for name,path in [('manifest',self.marketplace),('receipt',self.state/'marketplace-owned.json')]:
            current=path.read_bytes().hex() if path.exists() else None
            if current not in [value['old_'+name+'_hex'],value['new_'+name+'_hex']]:
                raise Conflict('Catalog '+name+' changed after interrupted publication; it is preserved.')
        return value

    def recover_catalog(self):
        """Finish exact journaled publication while the caller holds update.lock."""
        value=self.pending_catalog()
        if value is None:return
        for name,path in [('manifest',self.marketplace),('receipt',self.state/'marketplace-owned.json')]:
            current=path.read_bytes() if path.exists() else None
            old=bytes.fromhex(value['old_'+name+'_hex']) if value['old_'+name+'_hex'] is not None else None
            new=bytes.fromhex(value['new_'+name+'_hex'])
            if current not in [old,new]:raise Conflict('Catalog changed during recovery; it is preserved.')
            if current!=new:
                if current is None:create_owned(path,new)
                else:atomic_write(path,new,expected=current)
        # Ownership is complete only if both files still contain the intended bytes.
        for name,path in [('manifest',self.marketplace),('receipt',self.state/'marketplace-owned.json')]:
            if not path.exists() or path.read_bytes().hex()!=value['new_'+name+'_hex']:
                raise Conflict('Catalog changed before publication completed; it is preserved for recovery.')
        value['phase']='complete';write_json(self.state/'marketplace-transaction.json',value)

    def prepare_catalog(self,*,apply):
        desired=self.catalog_manifest();record=self.state/'marketplace-owned.json'
        pending=self.pending_catalog()
        if apply and pending:
            self.recover_catalog();pending=None
        original=self.marketplace.read_bytes() if self.marketplace.exists() else None
        receipt=record.read_bytes() if record.exists() else None
        # Read-only preflight recognizes a durable interrupted write. Recovery itself
        # happens after update.lock is acquired, before any new deployment work.
        if pending:
            original=bytes.fromhex(pending['new_manifest_hex']);receipt=bytes.fromhex(pending['new_receipt_hex'])
        if original is not None:
            if receipt is None:raise Conflict('Managed catalog already exists without ownership evidence; it is preserved.')
            owned=json.loads(receipt.decode('utf-8-sig'))
            current=json.loads(original.decode('utf-8-sig'));previous=json.loads(bytes.fromhex(owned['manifest_hex']).decode('utf-8-sig'))
            if self.without_sp_source(current)!=self.without_sp_source(previous):
                raise Conflict('Managed catalog changed independently; all unrelated entries are preserved.')
            # Normal updater transactions alter only this source pointer.
            sp=next(x for x in current['plugins'] if x['name']=='superpowers')['source']
            if sp.get('source')=='local':
                path=(self.root/sp['path']).resolve()
                if not path.is_relative_to(self.root) or path==self.root:raise Conflict('Managed Superpowers source escapes its marketplace.')
                next(x for x in desired['plugins'] if x['name']=='superpowers')['source']=sp
        encoded=(json.dumps(desired,ensure_ascii=False,indent=2)+'\n').encode()
        if apply:
            new_receipt=(json.dumps({'schema':1,'manifest_hex':encoded.hex(),'source_root':str(self.catalog)},ensure_ascii=False,indent=2)+'\n').encode()
            if original!=encoded or receipt!=new_receipt:
                write_json(self.state/'marketplace-transaction.json',{'schema':1,'phase':'prepared',
                    'old_manifest_hex':original.hex() if original is not None else None,'new_manifest_hex':encoded.hex(),
                    'old_receipt_hex':receipt.hex() if receipt is not None else None,'new_receipt_hex':new_receipt.hex()})
                self.recover_catalog()
        return {'changed':encoded!=original,'name':'gigma-skills','plugins':len(desired['plugins'])}

    def fault(self,point):
        if self.failpoint:self.failpoint(point)

    def discover(self):
        rows=self.backend.installed();registries=self.backend.marketplaces();config=settings(self.home)
        fable=[x for x in rows if str(x.get('pluginId','')).startswith('fable5-codex@') and x.get('enabled') is True]
        if len(fable)>1:raise Conflict('Multiple Fable installations are enabled; select one before setup.')
        plugins=config.get('plugins',{})
        if not fable and (any(str(x.get('pluginId','')).startswith('fable5-codex@') for x in rows)
            or any(k.startswith('fable5-codex@') and v.get('enabled') is False for k,v in plugins.items())):
            raise Conflict('Fable was explicitly disabled; setup will preserve that choice.')
        if fable and plugins.get(fable[0]['pluginId'],{}).get('enabled') is False:
            raise Conflict('Fable settings were explicitly disabled; setup will preserve that choice.')
        sp=[x for x in rows if str(x.get('pluginId','')).startswith('superpowers@')]
        enabled=[x for x in sp if x.get('enabled') is True]
        if len(enabled)>1 or any(x['pluginId']!=PLUGIN for x in enabled):raise Conflict('Another Superpowers source is enabled; setup will not switch it.')
        if any(x['pluginId']==PLUGIN and x.get('enabled') is not True for x in sp) or plugins.get(PLUGIN,{}).get('enabled') is False:
            raise Conflict('Superpowers was explicitly disabled; setup will preserve that choice.')
        if not enabled and any(k.startswith('superpowers@') and v.get('enabled') is False for k,v in plugins.items()):
            raise Conflict('Superpowers was explicitly disabled; setup will preserve that choice.')
        gigma=[x for x in registries if x.get('name')=='gigma-skills']
        if len(gigma)>1:raise Conflict('Ambiguous Gigma marketplace registry.')
        registered=bool(gigma) and normpath(registry_path(gigma[0]))==normpath(self.root)
        if gigma and not registered and not self.adopt_marketplace:
            raise Conflict('Gigma is registered at another source. It is preserved; --adopt-marketplace explicitly opts into repointing it.')
        if enabled:
            manifest=json.loads(self.marketplace.read_text(encoding='utf-8-sig')) if self.marketplace.is_file() else {}
            sources=[x.get('source',{}) for x in manifest.get('plugins',[]) if x.get('name')=='superpowers']
            active_source=enabled[0].get('source',{})
            if (not registered or len(sources)!=1 or sources[0].get('source')!='local'
                or active_source.get('source')!='local' or not active_source.get('path')
                or normpath(active_source['path'])!=normpath(self.root/sources[0]['path'])):
                raise Conflict('Existing direct Superpowers cannot be migrated by setup. Use a clean Codex home or explicitly resolve the existing plugin first; --adopt-marketplace repoints only the registry and does not authorize plugin/cache migration.')
        return {'fable':fable[0] if fable else None,'superpowers':enabled[0] if enabled else None,
            'managed_registry':registered,'gigma_registry':bool(gigma),'settings':config}

    def ensure_no_pending_update(self):
        journal=self.state/'transaction.json'
        if journal.exists() and json.loads(journal.read_text(encoding='utf-8-sig')).get('phase') in {
            'prepared','switched','installed','recovering','recovery_required'}:
            script=str(self.root/'maintenance/Update-Superpowers.ps1').replace("'","''")
            home=str(self.home).replace("'","''")
            raise Conflict("An ordinary Superpowers update needs recovery. Run & '"+script+"' -Action recover -CodexHome '"+home+"', then retry setup.")

    def plan(self):
        self.ensure_no_pending_update()
        prerequisites=self.requirements();found=self.discover();runtime=deploy_runtime(self.runtime_source,self.root,apply=False)
        catalog=self.prepare_catalog(apply=False)
        return {'status':'planned','home':str(self.home),'root':str(self.root),'requirements':prerequisites,
            'fable':found['fable']['pluginId'] if found['fable'] else FABLE,'existing_superpowers':bool(found['superpowers']),
            'runtime':runtime,'catalog':catalog,'adopt_marketplace':self.adopt_marketplace,'validation':'five real compatibility tasks, independent review, native MXC and post-install discovery',
            'automation_status':'pending_native_tool'}

    def recover(self):
        if not self.journal.exists():return None
        value=json.loads(self.journal.read_text())
        if value.get('phase') not in {'activating','installed','recovery_required'}:return None
        if not value.get('owns_new_plugin'):raise Conflict('Bootstrap cannot recover a plugin it did not create.')
        current=self.marketplace.read_bytes()
        if current.hex() not in [value['old_marketplace_hex'],value['new_marketplace_hex']]:raise Conflict('Marketplace changed after interrupted setup; recovery preserves it.')
        if value.get('source') and inventory(value['source'])!=value['inventory']:
            raise Conflict('Managed source changed after interrupted setup; recovery preserves it.')
        rows=[x for x in self.backend.installed() if x.get('pluginId')==PLUGIN]
        if rows:
            if len(rows)!=1:raise Conflict('Ambiguous installed Superpowers state; recovery preserves it.')
            row=rows[0]
            if row.get('enabled') is not True or settings(self.home).get('plugins',{}).get(PLUGIN,{}).get('enabled') is False:
                raise Conflict('Superpowers was disabled after setup; recovery preserves that choice.')
            if row.get('version')!=value['version']:raise Conflict('Installed Superpowers changed after setup; recovery preserves it.')
            source=row.get('source',{});registered=row.get('marketplaceSource',{})
            if (source.get('source')!='local' or not source.get('path')
                or normpath(source['path'])!=normpath(value['source'])
                or registered.get('sourceType')!='local' or not registered.get('source')
                or normpath(registered['source'])!=normpath(self.root)):
                raise Conflict('Installed Superpowers source identity is unknown; recovery preserves it.')
            registries=[x for x in self.backend.marketplaces() if x.get('name')=='gigma-skills']
            if len(registries)!=1 or normpath(registry_path(registries[0]))!=normpath(self.root):
                raise Conflict('Gigma registry changed after setup; recovery preserves it.')
            cache=self.home/'plugins/cache/gigma-skills/superpowers'/value['version']
            if not cache.is_dir() or inventory(cache)!=value['inventory']:
                raise Conflict('Installed Superpowers cache changed or cannot be identified; recovery preserves it.')
            if value.get('installed_row') and row!=value['installed_row']:raise Conflict('Installed Superpowers state changed; recovery preserves it.')
            # Only this newly created plugin is removed. Other settings are never restored wholesale.
            self.backend.remove(PLUGIN)
        old=bytes.fromhex(value['old_marketplace_hex'])
        if current!=old:atomic_write(self.marketplace,old,expected=current)
        write_json(self.state/'marketplace-owned.json',{'schema':1,'manifest_hex':old.hex(),'source_root':str(self.catalog)})
        value['phase']='rolled_back';write_json(self.journal,value)
        return {'status':'recovered','reason':'Interrupted initial activation was rolled back.'}

    def context(self,path,files):
        return {'backend':self.backend.context(),'package':files,'policy':digest(self.home/'AGENTS.md'),
            'settings':settings(self.home),'source':str(Path(path).resolve())}

    def automation(self,factory):
        request=factory(self.home,self.root);path=self.state/'automation-request.json'
        write_json(path,request)
        return {'automation':request,'automation_request_path':str(path)}

    def install(self):
        self.ensure_no_pending_update()
        self.requirements();self.discover();deploy_runtime(self.runtime_source,self.root,apply=False);self.prepare_catalog(apply=False)
        with exclusive_lock(self.state/'update.lock'):
            self.ensure_no_pending_update()
            self.recover_catalog()
            from compatibility import recover_trust_leases
            recover_trust_leases(self.state/'runs',self.home)
            recovered=self.recover()
            if recovered:return recovered
            found=self.discover();runtime=deploy_runtime(self.runtime_source,self.root,apply=True)
            catalog=self.prepare_catalog(apply=True)
            if not found['managed_registry']:self.backend.register_marketplace(self.root)
            from profile_policy import install_policy, automation_request
            policy=install_policy(self.home,self.policy_source,self.state/'policy')
            if not found['fable']:
                self.backend.add(FABLE)
                found=self.discover()
                if not found['fable'] or found['fable']['pluginId']!=FABLE:raise UpdateError('Native Fable installation was not discovered.')
            if found['superpowers']:
                return self.validate_existing(found,policy,runtime,automation_request)
            release=self.initial_release();signature=hashlib.sha256(json.dumps({'release':release,'backend':self.backend.context(),
                'settings':settings(self.home),'policy':digest(self.home/'AGENTS.md')},sort_keys=True).encode()).hexdigest()
            held=self.state/'bootstrap-held.json'
            if held.exists():
                previous=json.loads(held.read_text())
                if previous.get('signature')==signature:return {'status':'held','new_failure':False,'report':previous['report']}
            run=self.state/'runs'/('bootstrap-'+uuid.uuid4().hex)
            candidate=self.stage(release,run/'candidate',baseline_package=None);package=Path(candidate['package_path']);files=inventory(package)
            if candidate.get('version')!=release['version'] or candidate.get('commit')!=release['expected_commit']:
                raise Conflict('The staged release differs from the Gigma catalog pin; it was not activated.')
            before=settings(self.home);policy_hash=digest(self.home/'AGENTS.md')
            checks=self.compatibility(candidate,run/'compatibility',self.home,allow_empty_outside=True)
            if checks.get('status')!='passed':
                write_json(run/'rejected.json',checks);write_json(held,{'signature':signature,'report':str(run/'rejected.json')})
                return {'status':'held','new_failure':True,'report':str(run/'rejected.json'),'reason':'compatibility_failed'}
            if inventory(package)!=files or settings(self.home)!=before or digest(self.home/'AGENTS.md')!=policy_hash:
                raise Conflict('Candidate or destination preferences changed during validation.')
            now=self.discover()
            if not now['managed_registry']:raise Conflict('Gigma registry changed during validation; activation preserves it.')
            if now['superpowers']:raise Conflict('Superpowers appeared during validation; setup preserves it.')
            destination=self.root/'packages'/(candidate['version']+'-'+candidate['commit'][:12])
            if destination.exists():
                if inventory(destination)!=files:raise Conflict('Immutable package destination differs from verified candidate.')
            else:
                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(package,destination)
            if inventory(destination)!=files:raise UpdateError('Immutable package copy failed verification.')
            old_marketplace=self.marketplace.read_bytes()
            manifest=json.loads(old_marketplace.decode('utf-8-sig'))
            next(x for x in manifest['plugins'] if x['name']=='superpowers')['source']={'source':'local','path':'./'+destination.relative_to(self.root).as_posix()}
            encoded=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
            transaction={'phase':'activating','owns_new_plugin':True,'version':candidate['version'],'source':str(destination),'inventory':files,
                'old_marketplace_hex':old_marketplace.hex(),'new_marketplace_hex':encoded.hex()}
            write_json(self.journal,transaction)
            try:
                atomic_write(self.marketplace,encoded,expected=old_marketplace)
                installation=self.backend.add(PLUGIN)
                transaction.update(phase='installed',installed_row=next(x for x in self.backend.installed() if x.get('pluginId')==PLUGIN))
                write_json(self.journal,transaction);self.fault('after_install')
                health=self.backend.health(destination,candidate['version'],files)
                if settings(self.home).get('plugins',{}).get(PLUGIN,{}).get('enabled') is False:raise Conflict('Superpowers was disabled during setup.')
                after=settings(self.home)
                after.get('plugins',{}).pop(PLUGIN,None)
                expected=json.loads(json.dumps(before));expected.get('plugins',{}).pop(PLUGIN,None)
                if after!=expected or digest(self.home/'AGENTS.md')!=policy_hash:
                    raise Conflict('Global instructions or unrelated settings changed during activation; they were preserved.')
                provenance={'version':candidate['version'],'origin':candidate,'sourceFiles':files,'compatibility_report':str(run/'compatibility')}
                write_json(self.root/'provenance.json',provenance)
                context=self.context(destination,files)
                write_json(self.state/'bootstrap-verified.json',{'context':context,'checks':checks,'candidate':candidate})
                write_json(self.state/'marketplace-owned.json',{'schema':1,'manifest_hex':encoded.hex(),'source_root':str(self.catalog)})
                transaction.update(phase='complete',health=health);write_json(self.journal,transaction)
                return {'status':'installed','version':candidate['version'],'checks':checks,'health':health,'policy':policy,'runtime':runtime,
                    **self.automation(automation_request)}
            except Exception as error:
                try:self.recover()
                except Exception as recovery_error:
                    transaction.update(phase='recovery_required',error=str(error),recovery_error=str(recovery_error));write_json(self.journal,transaction)
                    raise UpdateError('Bootstrap rollback requires attention; unrelated changes were preserved.') from recovery_error
                return {'status':'rolled_back','reason':str(error)}

    def validate_existing(self,found,policy,runtime,automation_request):
        from core import Manager
        manager=Manager(self.root,self.home,self.backend,self.compatibility,self.latest,self.stage)
        if not self.marketplace.exists():raise Conflict('Existing Superpowers lacks a managed marketplace source.')
        package=manager.source_path(json.loads(self.marketplace.read_text(encoding='utf-8-sig')));files=inventory(package)
        version=json.loads((package/'.codex-plugin/plugin.json').read_text(encoding='utf-8-sig'))['version']
        context=self.context(package,files);receipt=self.state/'bootstrap-verified.json'
        previous=json.loads(receipt.read_text()) if receipt.exists() else None
        if previous and previous.get('context')==context:
            health=self.backend.health(package,version,files)
            return {'status':'unchanged','version':version,'health':health,'policy':policy,'runtime':runtime,**self.automation(automation_request)}
        run=self.state/'runs'/('bootstrap-validation-'+uuid.uuid4().hex)
        # Validate the actual active package and reuse the provenance of its immutable source.
        provenance=json.loads((self.root/'provenance.json').read_text(encoding='utf-8-sig')) if (self.root/'provenance.json').exists() else {}
        staged=run/'source/package';staged.parent.mkdir(parents=True);shutil.copytree(package,staged)
        if inventory(staged)!=files:raise UpdateError('Existing package staging copy failed verification.')
        candidate={**provenance.get('origin',{}),'package_path':str(staged),'stage_path':str(run/'source'),'version':version}
        checks=self.compatibility(candidate,run/'compatibility',self.home)
        if checks.get('status')!='passed':return {'status':'held','reason':'existing_context_validation_failed','checks':checks}
        if self.context(package,files)!=context:raise Conflict('Existing package or preferences changed during validation.')
        health=self.backend.health(package,version,files)
        write_json(receipt,{'context':context,'checks':checks,'candidate':candidate})
        return {'status':'validated','version':version,'checks':checks,'health':health,'policy':policy,'runtime':runtime,**self.automation(automation_request)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','install']);parser.add_argument('--home',type=Path,required=True)
    parser.add_argument('--marketplace-root',type=Path);parser.add_argument('--adopt-marketplace',action='store_true')
    args=parser.parse_args(argv)
    try:result=getattr(Setup(args.home,args.marketplace_root,adopt_marketplace=args.adopt_marketplace),args.action)()
    except Exception as error:result={'status':'failed','error_type':type(error).__name__,'reason':str(error)}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'] in {'planned','installed','validated','unchanged','recovered'} else 2


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
