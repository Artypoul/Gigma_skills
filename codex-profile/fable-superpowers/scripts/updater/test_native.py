from pathlib import Path
import subprocess
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from core import Conflict, inventory, write_json
from native import NativeBackend, verification_fingerprint

class NativeIsolationTests(unittest.TestCase):
    def setUp(self):
        self.which=patch('native.shutil.which',return_value=sys.executable);self.which.start();self.addCleanup(self.which.stop)
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.home=self.base/'selected-home';self.home.mkdir();self.root=self.base/'marketplace';self.root.mkdir()
        (self.home/'config.toml').write_text('[plugins."superpowers@fable-superpowers"]\nenabled=false\n[plugins."fable5-codex@fable5"]\nenabled=true\n')
        self.package=self.base/'package';self.package.mkdir();(self.package/'test.txt').write_text('verified')
    def tearDown(self):self.temp.cleanup()
    def test_native_command_uses_selected_home(self):
        backend=NativeBackend(self.root,self.home)
        with patch('native.subprocess.run',return_value=subprocess.CompletedProcess([],0,'{}','')) as run:
            backend.command(['plugin','list','--json'])
        self.assertEqual(run.call_args.kwargs['env']['CODEX_HOME'],str(self.home))
    def test_native_install_cannot_reenable_disabled_plugin(self):
        backend=NativeBackend(self.root,self.home)
        with patch('native.subprocess.run') as run:
            with self.assertRaises(Conflict):backend.install(self.package,'7.0.1',inventory(self.package))
        run.assert_not_called()
    def test_health_helper_receives_unique_nonexistent_probe_directory(self):
        probes=[]
        def helper(path,*args,**kwargs):
            self.assertFalse(path.exists())
            path.mkdir()
            probes.append(path)
            return {'status':'passed'}
        backend=NativeBackend(self.root,self.home,health_function=helper)
        rows=[{'pluginId':'superpowers@fable-superpowers','name':'superpowers','enabled':True,'version':'7.0.1'},{'pluginId':'fable5-codex@fable5','name':'fable5-codex','enabled':True,'version':'1.3.2'}]
        with patch.object(backend,'installed',return_value=rows):
            for _ in range(2):self.assertEqual(backend.health(self.package,'7.0.1',inventory(self.package))['status'],'healthy')
        self.assertNotEqual(probes[0],probes[1])
    def test_verification_context_changes_with_observer_or_fixture(self):
        maintenance=self.base/'maintenance';resources=maintenance/'resources';resources.mkdir(parents=True)
        (maintenance/'compatibility.py').write_text('validator')
        observer=resources/'appserver_eval.py';observer.write_text('old observer')
        fixture=resources/'fixture.txt';fixture.write_text('old fixture')
        first=verification_fingerprint(maintenance)
        observer.write_text('new observer');second=verification_fingerprint(maintenance)
        self.assertNotEqual(first,second)
        fixture.write_text('new fixture');self.assertNotEqual(second,verification_fingerprint(maintenance))
        cache=resources/'__pycache__';cache.mkdir();(cache/'observer.pyc').write_bytes(b'cache')
        self.assertFalse(any('__pycache__' in name for name in verification_fingerprint(maintenance)))

    def test_context_and_health_reuse_fable_from_gigma_marketplace(self):
        backend=NativeBackend(self.root,self.home,health_function=lambda *a,**kw:{'status':'passed'})
        rows=[{'pluginId':'superpowers@fable-superpowers','name':'superpowers','enabled':True,'version':'7.0.1'},
            {'pluginId':'fable5-codex@gigma-skills','name':'fable5-codex','enabled':True,'version':'1.3.2'}]
        with patch.object(backend,'installed',return_value=rows) as installed, patch.object(backend,'command',return_value=subprocess.CompletedProcess([],0,'codex test','')):
            self.assertEqual(backend.context()['fable_id'],'fable5-codex@gigma-skills')
            self.assertEqual(backend.health(self.package,'7.0.1',inventory(self.package))['fable_id'],'fable5-codex@gigma-skills')
        self.assertTrue(all(not call.args for call in installed.call_args_list))

    def test_fresh_home_discovery_does_not_invoke_native_or_create_home(self):
        home=self.base/'missing';backend=NativeBackend(self.root,home)
        with patch.object(backend,'command') as command:
            self.assertEqual(backend.installed(),[]);self.assertEqual(backend.marketplaces(),[])
        command.assert_not_called();self.assertFalse(home.exists())

    def test_marketplace_shape_uses_native_catalogue(self):
        backend=NativeBackend(self.root,self.home)
        rows=[{'name':'gigma-skills','root':str(self.root),'marketplaceSource':{'sourceType':'local','source':str(self.root)}}]
        with patch.object(backend,'command',return_value=subprocess.CompletedProcess([],0,json.dumps({'marketplaces':rows}),'')):
            self.assertEqual(backend.marketplaces(),rows)

    def installation_row(self):
        return {'pluginId':'superpowers@fable-superpowers','name':'superpowers','marketplaceName':'fable-superpowers',
            'version':'7.0.1','installed':True,'enabled':True,'source':{'source':'local','path':str(self.package)},
            'marketplaceSource':{'sourceType':'local','source':str(self.root)},'installPolicy':'AVAILABLE','authPolicy':'ON_INSTALL'}

    def test_installation_snapshot_observes_cache_independently_from_declared_version(self):
        backend=NativeBackend(self.root,self.home);row=self.installation_row()
        cache=self.home/'plugins/cache/fable-superpowers/superpowers/7.0.1';cache.mkdir(parents=True)
        (cache/'test.txt').write_text('verified')
        with patch.object(backend,'installed',return_value=[row]):first=backend.installation_snapshot()
        row['enabled']=False
        with patch.object(backend,'installed',return_value=[row]):self.assertEqual(backend.installation_snapshot(),first)
        unexpected=cache.parent/'9.0.0';unexpected.mkdir();(unexpected/'test.txt').write_text('user installed')
        with patch.object(backend,'installed',return_value=[row]):changed=backend.installation_snapshot()
        self.assertEqual(first['version'],'7.0.1');self.assertEqual(changed['version'],'7.0.1')
        self.assertNotEqual(first['caches'],changed['caches']);self.assertEqual(changed['caches']['9.0.0'],inventory(unexpected))
        (cache/'test.txt').write_text('user edited')
        with patch.object(backend,'installed',return_value=[row]):self.assertNotEqual(backend.installation_snapshot()['caches']['7.0.1'],first['caches']['7.0.1'])

    def test_installation_snapshot_rejects_missing_duplicate_or_external_native_state(self):
        backend=NativeBackend(self.root,self.home);row=self.installation_row()
        for rows in [[],[row,row],[{**row,'installed':False}],
                [{**row,'installedPath':str(self.base/'user-cache')}],
                [{**row,'source':{'source':'git','url':'https://example.test/user.git'}}]]:
            with self.subTest(rows=rows),patch.object(backend,'installed',return_value=rows):
                with self.assertRaises(Conflict):backend.installation_snapshot()

    def test_installation_snapshot_supports_managed_gigma_identity_and_explicit_cache_path(self):
        write_json(self.root/'.agents/plugins/marketplace.json',{'name':'gigma-skills'})
        backend=NativeBackend(self.root,self.home);row=self.installation_row()
        cache=self.home/'plugins/cache/gigma-skills/superpowers/7.0.1';cache.mkdir(parents=True)
        (cache/'test.txt').write_text('verified')
        row.update(pluginId='superpowers@gigma-skills',marketplaceName='gigma-skills',installedPath=str(cache))
        with patch.object(backend,'installed',return_value=[row]):snapshot=backend.installation_snapshot()
        self.assertEqual(snapshot['installed_cache'],'7.0.1');self.assertEqual(snapshot['caches'],{'7.0.1':inventory(cache)})
        self.assertEqual(snapshot['source'],str(self.package.resolve()))

if __name__=='__main__':unittest.main()
