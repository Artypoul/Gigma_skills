"""Native install adapter. All catalogue/MCP checks are model-free."""
import json
from pathlib import Path
import shutil
import subprocess
import os
import tomllib
import uuid

from core import PLUGIN_ID, Conflict, UpdateError, digest, inventory, fable_identity, managed_plugin_id

def verification_fingerprint(maintenance):
    maintenance=Path(maintenance)
    files=[maintenance/name for name in ['core.py','native.py','source.py','compatibility.py']]
    files.extend(path for path in (maintenance/'resources').rglob('*')
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc')
    return {path.relative_to(maintenance).as_posix():digest(path) for path in sorted(files) if path.is_file()}

class NativeBackend:
    def __init__(self,root,home,health_function=None):
        self.root,self.home=Path(root),Path(home)
        self.codex=shutil.which('codex')
        if not self.codex: raise UpdateError('Codex CLI is unavailable on PATH.')
        self.health_function=health_function

    @property
    def plugin_id(self):return managed_plugin_id(self.root)

    def command(self,args,timeout=120):
        env=os.environ.copy()
        env['CODEX_HOME']=str(self.home)
        cwd=self.root if self.root.is_dir() else (self.home if self.home.is_dir() else Path.cwd())
        result=subprocess.run([self.codex,*args],cwd=cwd,env=env,capture_output=True,encoding='utf-8',errors='replace',timeout=timeout)
        return result

    def installed(self,marketplace=None):
        if not self.home.exists():return []
        args=['plugin','list','--json']
        if marketplace: args+=['--marketplace',marketplace]
        result=self.command(args)
        if result.returncode: raise UpdateError('Native plugin catalogue query failed.')
        try: return json.loads(result.stdout)['installed']
        except (ValueError,KeyError) as error: raise UpdateError('Invalid native plugin catalogue response.') from error

    def installation_snapshot(self):
        """Observe the managed identity and cache without activating anything.

        `plugin list` can obtain version/source from the marketplace manifest,
        even before `plugin add` materializes that version. Its row is not proof
        of the actual installed cache. Record every observable cache version too;
        a new, missing or edited cache must not be overwritten by crash recovery.
        This cannot distinguish an unobservable reinstall of identical bytes.
        """
        rows=[row for row in self.installed() if row.get('pluginId')==self.plugin_id]
        if len(rows)!=1 or rows[0].get('installed') is not True:
            raise Conflict('Managed native installation is missing or ambiguous; preserving user state.')
        row=rows[0];source=row.get('source',{})
        if source.get('source')!='local' or not source.get('path') or not isinstance(row.get('version'),str):
            raise Conflict('Managed native installation source is unknown; preserving user state.')
        marketplace=self.plugin_id.split('@',1)[1]
        cache_root=(self.home/'plugins/cache'/marketplace/'superpowers').resolve()
        caches={}
        if cache_root.exists():
            for path in sorted(cache_root.iterdir()):
                if path.is_symlink() or not path.is_dir():
                    raise Conflict('Managed native installation cache has an unexpected entry.')
                caches[path.name]=inventory(path)
        installed_cache=None
        if row.get('installedPath') is not None:
            installed_path=Path(row['installedPath']).resolve()
            if installed_path.parent!=cache_root or installed_path.name not in caches:
                raise Conflict('Managed native installation uses an unexpected cache path.')
            installed_cache=installed_path.name
        identity={key:value for key,value in row.items() if key not in {'enabled','version','source','installedPath'}}
        source_path=Path(source['path']).resolve()
        return {'identity':identity,'version':row['version'],'source':str(source_path),
            'source_inventory':inventory(source_path) if source_path.is_dir() else None,
            'installed_cache':installed_cache,'caches':caches}

    def context(self):
        version=self.command(['--version'],timeout=30)
        if version.returncode: raise UpdateError('Could not verify Codex version.')
        fable=[x for x in self.installed() if str(x.get('pluginId','')).startswith('fable5-codex@') and x.get('enabled')]
        if len(fable)!=1: raise UpdateError('Fable is not installed and enabled.')
        maintenance=Path(__file__).resolve().parent
        validators=verification_fingerprint(maintenance)
        return {'codex':version.stdout.strip(),'fable_id':fable[0]['pluginId'],'fable_version':fable[0]['version'],'validator_hashes':validators}

    def marketplaces(self):
        if not self.home.exists():return []
        result=self.command(['plugin','marketplace','list','--json'])
        if result.returncode:raise UpdateError('Native marketplace query failed.')
        try:
            value=json.loads(result.stdout)
            return value['marketplaces'] if isinstance(value,dict) else value
        except (ValueError,KeyError) as error:raise UpdateError('Invalid native marketplace response.') from error

    def _mutation(self,args):
        result=self.command([*args,'--json'],timeout=180)
        if result.returncode:raise UpdateError('Native plugin operation failed: '+str(args[:3]))
        try:return json.loads(result.stdout)
        except ValueError as error:raise UpdateError('Native plugin operation returned invalid JSON.') from error

    def register_marketplace(self,path):return self._mutation(['plugin','marketplace','add',str(path)])
    def remove_marketplace(self,name):return self._mutation(['plugin','marketplace','remove',name])
    def add(self,plugin):return self._mutation(['plugin','add',plugin])
    def remove(self,plugin):return self._mutation(['plugin','remove',plugin])

    def install(self,path,version,files):
        if inventory(path)!=files: raise UpdateError('Verified package changed before native installation.')
        settings=tomllib.loads((self.home/'config.toml').read_text(encoding='utf-8-sig'))
        if any(settings.get('plugins',{}).get(plugin,{}).get('enabled') is not True for plugin in [self.plugin_id,fable_identity(settings)]):
            raise Conflict('Required plugin disabled by user; native install will not re-enable it.')
        result=self.command(['plugin','add',self.plugin_id,'--json'],timeout=180)
        if result.returncode:
            # An already materialized immutable cache can make a repeat native
            # install fail. Only an independently verified desired state counts.
            try: health=self.health(path,version,files)
            except Exception as error: raise UpdateError('Native installation failed and desired state is not healthy.') from error
            return {'version':version,'native_exit':result.returncode,'idempotent_health':health}
        try: installed=json.loads(result.stdout)
        except ValueError as error: raise UpdateError('Native installer returned invalid JSON.') from error
        if installed.get('pluginId')!=self.plugin_id or installed.get('version')!=version:
            raise UpdateError('Native installer selected an unexpected package version.')
        return {'version':version,'path':installed.get('installedPath'),'native_exit':0}

    def health(self,path,version,files):
        if inventory(path)!=files: raise UpdateError('Managed source differs from the verified package.')
        active=self.installed()
        superpowers=[x for x in active if x.get('name')=='superpowers' and x.get('enabled')]
        if len(superpowers)!=1 or superpowers[0].get('pluginId')!=self.plugin_id or superpowers[0].get('version')!=version:
            raise UpdateError('Exactly one active Superpowers at the selected version is required.')
        fable=[x for x in active if str(x.get('pluginId','')).startswith('fable5-codex@') and x.get('enabled')]
        if len(fable)!=1: raise UpdateError('Fable must remain installed and enabled.')
        if self.health_function is None:
            from compatibility import installed_health
            function=installed_health
        else: function=self.health_function
        probe=self.root/'updates'/'health-probes'/uuid.uuid4().hex
        probe.parent.mkdir(parents=True,exist_ok=True)
        result=function(probe,version,files,self.home,plugin_id=self.plugin_id)
        if result.get('status') not in ['passed','healthy']:
            raise UpdateError('Fable/native catalogue post-install health failed.')
        return {'status':'healthy','version':version,'fable_id':fable[0]['pluginId'],'fable_version':fable[0]['version'],'catalogue':result}
