from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import Busy, Conflict, Manager, UpdateError, exclusive_lock, inventory, write_json

class Backend:
    def __init__(self,source):
        self.calls=[]; self.installed='7.0.1'; self.source=str(source.resolve())
        self.caches={'7.0.1':inventory(source)}; self.fail_install=False; self.fail_health=False
    def installation_snapshot(self):
        return {'identity':{'pluginId':'superpowers@fable-superpowers'},'version':self.installed,
            'source':self.source,'source_inventory':inventory(self.source) if Path(self.source).is_dir() else None,
            'installed_cache':self.installed,'caches':deepcopy(self.caches)}
    def install(self,path,version,files):
        self.calls.append(('install',version))
        if version=='7.0.2' and self.fail_install: raise RuntimeError('Injected native installation failure')
        self.installed=version;self.source=str(Path(path).resolve());self.caches[version]=deepcopy(files)
        return {'version':version,'path':str(path)}
    def health(self,path,version,files):
        self.calls.append(('health',version))
        if version=='7.0.2' and self.fail_health: raise RuntimeError('Injected catalogue rejection')
        if self.installed!=version or inventory(path)!=files: raise RuntimeError('Incorrect active version')
        return {'verified':True,'version':version}

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'marketplace';self.home=self.base/'home';self.home.mkdir()
        (self.home/'AGENTS.md').write_text('Fable baseline; Superpowers engineering; questions once.\n')
        (self.home/'config.toml').write_text('[plugins."superpowers@fable-superpowers"]\nenabled=true\n[plugins."fable5-codex@fable5"]\nenabled=true\n[unrelated]\nkeep="original"\n')
        self.old=self.root/'superpowers';self.package(self.old,'7.0.1')
        write_json(self.root/'.agents/plugins/marketplace.json',{'name':'fable-superpowers','plugins':[{'name':'superpowers','source':{'source':'local','path':'./superpowers'}}]})
        self.marketplace=self.root/'.agents/plugins/marketplace.json';self.original=self.marketplace.read_bytes()
        self.backend=Backend(self.old);self.compat_calls=0;self.stage_calls=0
    def tearDown(self): self.temp.cleanup()
    def package(self,path,version):
        (path/'.codex-plugin').mkdir(parents=True)
        write_json(path/'.codex-plugin/plugin.json',{'name':'superpowers','version':version,'skills':'./skills/','hooks':{}})
        (path/'content.txt').write_text(version)
    def latest(self): return {'version':'7.0.2','tag':'v7.0.2','id':42}
    def stage(self,release,stage_root,baseline_package=None):
        self.stage_calls+=1;package=stage_root/'package';self.package(package,release['version'])
        return {**release,'package_path':str(package),'stage_path':str(stage_root),'commit':'a'*40}
    def compatible(self,*args): self.compat_calls+=1;return {'status':'passed'}
    def manager(self,**kw): return Manager(self.root,self.home,self.backend,kw.pop('compatibility',self.compatible),kw.pop('latest',self.latest),self.stage,**kw)
    def assert_old(self):
        self.assertEqual(self.marketplace.read_bytes(),self.original)
        self.assertEqual(self.backend.installed,'7.0.1')
    def test_success_preserves_preferences_and_old_package(self):
        agents=(self.home/'AGENTS.md').read_bytes();config=(self.home/'config.toml').read_bytes()
        result=self.manager().run()
        self.assertEqual(result['status'],'updated');self.assertEqual(self.backend.installed,'7.0.2')
        self.assertEqual((self.home/'AGENTS.md').read_bytes(),agents);self.assertEqual((self.home/'config.toml').read_bytes(),config)
        self.assertEqual((self.old/'content.txt').read_text(),'7.0.1')
        self.assertEqual(inventory(Path(result['backup'])/'package'),inventory(self.old))

    def test_update_and_rollback_accept_gigma_fable_identity(self):
        path=self.home/'config.toml';path.write_text(path.read_text().replace('fable5-codex@fable5','fable5-codex@gigma-skills'))
        before=path.read_bytes();self.backend.fail_health=True
        self.assertEqual(self.manager().run()['status'],'rolled_back');self.assert_old()
        self.assertEqual(path.read_bytes(),before)
    def test_same_or_older_version_does_not_stage_or_install(self):
        for version in ['7.0.1','6.3.0']:
            self.assertEqual(self.manager(latest=lambda:{'version':version}).run()['status'],'unchanged')
        self.assertEqual(self.stage_calls,0);self.assertEqual(self.backend.calls,[]);self.assert_old()
    def test_pointer_failure_rolls_back(self):
        def fail(point):
            if point=='after_pointer': raise RuntimeError('Injected pointer boundary failure')
        self.assertEqual(self.manager(failpoint=fail).run()['status'],'rolled_back');self.assert_old()
    def test_native_install_failure_rolls_back(self):
        self.backend.fail_install=True
        self.assertEqual(self.manager().run()['status'],'rolled_back');self.assert_old()
    def test_post_install_discovery_failure_rolls_back(self):
        self.backend.fail_health=True
        self.assertEqual(self.manager().run()['status'],'rolled_back');self.assert_old()
    def test_failure_after_healthy_install_still_rolls_back(self):
        def fail(point):
            if point=='after_health': raise RuntimeError('Injected final boundary failure')
        self.assertEqual(self.manager(failpoint=fail).run()['status'],'rolled_back');self.assert_old()
    def test_changed_global_instructions_are_not_overwritten(self):
        def change(*args):
            (self.home/'AGENTS.md').write_text('Concurrent user instruction change')
            return {'status':'passed'}
        with self.assertRaises(Conflict): self.manager(compatibility=change).run()
        self.assertEqual((self.home/'AGENTS.md').read_text(),'Concurrent user instruction change');self.assert_old()
        self.assertEqual(self.backend.calls,[])
    def test_changed_live_package_prevents_activation(self):
        def change(*args):
            (self.old/'content.txt').write_text('Concurrent user package change')
            return {'status':'passed'}
        with self.assertRaises(Conflict): self.manager(compatibility=change).run()
        self.assertEqual(self.backend.calls,[]);self.assertEqual(self.marketplace.read_bytes(),self.original)
    def test_modified_candidate_prevents_activation(self):
        def change(candidate,*args):
            (Path(candidate['package_path'])/'content.txt').write_text('Changed during verification')
            return {'status':'passed'}
        with self.assertRaises(UpdateError): self.manager(compatibility=change).run()
        self.assertEqual(self.backend.calls,[]);self.assert_old()
    def test_incompatible_version_is_held_without_repeating_model_checks(self):
        def fail(*args): self.compat_calls+=1;return {'status':'failed','reason':'Repeated clarification'}
        first=self.manager(compatibility=fail).run();second=self.manager(compatibility=fail).run()
        self.assertTrue(first['new_failure']);self.assertFalse(second['new_failure']);self.assertEqual(self.compat_calls,1);self.assert_old()
    def test_lock_prevents_overlapping_updates(self):
        recovery_calls=[]
        with exclusive_lock(self.root/'updates/update.lock'):
            with self.assertRaises(Busy): self.manager(recovery=lambda:recovery_calls.append(True)).run()
        self.assertEqual(self.backend.calls,[])
        self.assertEqual(recovery_calls,[])
    def test_trust_recovery_precedes_preferences_and_same_version_exit(self):
        path=self.home/'config.toml';original=path.read_bytes()
        path.write_text('not valid toml!')
        def recovery():
            path.write_bytes(original)
            # The callback runs inside the update lock.
            with self.assertRaises(Busy):
                with exclusive_lock(self.root/'updates/update.lock'): pass
        self.assertEqual(self.manager(recovery=recovery,latest=lambda:{'version':'7.0.1'}).run()['status'],'unchanged')
        self.assertEqual(path.read_bytes(),original);self.assertEqual(self.stage_calls,0)
    def test_unsafe_trust_recovery_blocks_normal_update(self):
        def recovery(): raise Conflict('Owned trust settings changed independently')
        with self.assertRaises(Conflict): self.manager(recovery=recovery).run()
        self.assertEqual(self.stage_calls,0);self.assertEqual(self.backend.calls,[]);self.assert_old()
    def test_trust_recovery_runs_before_held_candidate_exit(self):
        def fail(*args): return {'status':'failed'}
        self.manager(compatibility=fail).run()
        calls=[]
        result=self.manager(compatibility=fail,recovery=lambda:calls.append(True)).run()
        self.assertEqual(result['status'],'held');self.assertFalse(result['new_failure']);self.assertEqual(calls,[True])
    def test_interrupted_transaction_is_recovered_before_new_update(self):
        class Crash(BaseException): pass
        def crash(point):
            if point=='after_pointer': raise Crash()
        with self.assertRaises(Crash): self.manager(failpoint=crash).run()
        self.assertEqual(self.manager().run()['status'],'recovered');self.assert_old()
    def test_recovery_preserves_independently_installed_version_before_pointer_restore(self):
        class Crash(BaseException): pass
        def crash(point):
            if point=='after_pointer': raise Crash()
        with self.assertRaises(Crash): self.manager(failpoint=crash).run()
        pointer=self.marketplace.read_bytes()
        self.backend.installed='9.0.0';self.backend.caches['9.0.0']=[{'path':'user-package','sha256':'user','size':1}]
        calls=list(self.backend.calls)
        with self.assertRaises(UpdateError): self.manager().run()
        self.assertEqual(self.backend.installed,'9.0.0');self.assertEqual(self.backend.calls,calls)
        self.assertEqual(self.marketplace.read_bytes(),pointer)
        journal=json.loads((self.root/'updates/transaction.json').read_text())
        self.assertEqual(journal['phase'],'recovery_required');self.assertIn('installation',journal['rollback_error'].lower())
    def test_recovery_preserves_changed_or_missing_cache_and_source(self):
        class Crash(BaseException): pass
        def crash(point):
            if point=='after_install': raise Crash()
        with self.assertRaises(Crash): self.manager(failpoint=crash).run()
        pointer=self.marketplace.read_bytes();snapshot=self.backend.installation_snapshot();calls=list(self.backend.calls)
        journal=self.root/'updates/transaction.json';transaction=journal.read_bytes()
        changes=[{'caches':{'7.0.1':snapshot['caches']['7.0.1'],'7.0.2':[{'path':'user-edit','sha256':'user','size':1}]}},
            {'caches':{'7.0.1':snapshot['caches']['7.0.1']}},
            {'caches':{}},{'source':str(self.base/'user-source')},{'installed':None}]
        for change in changes:
            with self.subTest(change=change):
                journal.write_bytes(transaction)
                self.backend.caches=deepcopy(snapshot['caches']);self.backend.source=snapshot['source'];self.backend.installed='7.0.2'
                for key,value in change.items():setattr(self.backend,key,value)
                with self.assertRaises(UpdateError):self.manager().recover_pending(force=True)
                self.assertEqual(self.marketplace.read_bytes(),pointer);self.assertEqual(self.backend.calls,calls)
                self.assertEqual(json.loads((self.root/'updates/transaction.json').read_text())['phase'],'recovery_required')
    def test_recovery_preserves_user_edits_to_active_source_content(self):
        class Crash(BaseException):pass
        def crash(point):
            if point=='after_install':raise Crash()
        with self.assertRaises(Crash):self.manager(failpoint=crash).run()
        pointer=self.marketplace.read_bytes();calls=list(self.backend.calls)
        source=Path(self.backend.source);(source/'content.txt').write_text('User edited active source')
        with self.assertRaises(UpdateError):self.manager().run()
        self.assertEqual(self.marketplace.read_bytes(),pointer);self.assertEqual(self.backend.calls,calls)
        self.assertEqual((source/'content.txt').read_text(),'User edited active source')
    def test_native_installation_change_during_compatibility_aborts_activation(self):
        def change(*args):
            self.backend.caches['9.0.0']=[{'path':'user-package','sha256':'user','size':1}]
            return {'status':'passed'}
        with self.assertRaises(Conflict):self.manager(compatibility=change).run()
        self.assertEqual(self.marketplace.read_bytes(),self.original);self.assertEqual(self.backend.calls,[])
    def test_installation_change_after_prepared_journal_preserves_original_pointer(self):
        def write(path,value):
            write_json(path,value)
            if Path(path)==self.root/'updates/transaction.json' and value.get('phase')=='prepared':
                self.backend.installed='9.0.0';self.backend.caches['9.0.0']=[{'path':'user-package','sha256':'user','size':1}]
        with patch('core.write_json',side_effect=write):
            with self.assertRaises(UpdateError):self.manager().run()
        self.assertEqual(self.marketplace.read_bytes(),self.original);self.assertEqual(self.backend.installed,'9.0.0')
        self.assertEqual(self.backend.calls,[])
    def test_immediate_failure_rollback_preserves_independent_installation(self):
        def fail(point):
            if point=='after_health':
                self.backend.installed='9.0.0';self.backend.caches['9.0.0']=[{'path':'user-package','sha256':'user','size':1}]
                raise RuntimeError('User installed another version')
        with self.assertRaises(UpdateError):self.manager(failpoint=fail).run()
        self.assertEqual(self.backend.installed,'9.0.0');self.assertNotIn(('install','7.0.1'),self.backend.calls)
        self.assertNotEqual(self.marketplace.read_bytes(),self.original)
        self.assertEqual(json.loads((self.root/'updates/transaction.json').read_text())['phase'],'recovery_required')
    def test_crash_during_rollback_accepts_only_recorded_transaction_installations(self):
        class Crash(BaseException): pass
        original_install=self.backend.install
        def install(path,version,files):
            result=original_install(path,version,files)
            if version=='7.0.1':raise Crash()
            return result
        self.backend.fail_health=True;self.backend.install=install
        with self.assertRaises(Crash):self.manager().run()
        self.assertEqual(json.loads((self.root/'updates/transaction.json').read_text())['phase'],'recovering')
        self.backend.install=original_install
        self.assertEqual(self.manager().run()['status'],'recovered');self.assert_old()
    def test_disabled_fable_is_preserved_and_blocks_update(self):
        path=self.home/'config.toml';path.write_text(path.read_text().replace('[plugins."fable5-codex@fable5"]\nenabled=true','[plugins."fable5-codex@fable5"]\nenabled=false'))
        with self.assertRaises(Conflict): self.manager().run()
        self.assertIn('enabled=false',path.read_text());self.assertEqual(self.stage_calls,0)
    def test_failure_after_provenance_restores_original_metadata(self):
        provenance=self.root/'provenance.json';original=b'{"version":"7.0.1","keep":"original"}'
        provenance.write_bytes(original)
        def fail(point):
            if point=='after_provenance': raise RuntimeError('Injected metadata boundary failure')
        self.assertEqual(self.manager(failpoint=fail).run()['status'],'rolled_back')
        self.assertEqual(provenance.read_bytes(),original);self.assert_old()
    def test_crash_after_provenance_recovers_original_package_and_metadata(self):
        class Crash(BaseException): pass
        def crash(point):
            if point=='after_provenance': raise Crash()
        with self.assertRaises(Crash): self.manager(failpoint=crash).run()
        self.assertTrue((self.root/'provenance.json').exists())
        self.assertEqual(self.manager().run()['status'],'recovered');self.assert_old()
        self.assertFalse((self.root/'provenance.json').exists())
    def test_modified_old_source_uses_verified_backup_before_restoring_pointer(self):
        def fail(point):
            if point=='after_health':
                (self.old/'content.txt').write_text('User changed the inactive old source')
                raise RuntimeError('Injected failure after concurrent source change')
        result=self.manager(failpoint=fail).run()
        self.assertEqual(result['status'],'rolled_back')
        manifest=json.loads(self.marketplace.read_text());source=self.root/manifest['plugins'][0]['source']['path']
        self.assertEqual((source/'content.txt').read_text(),'7.0.1')
        self.assertEqual((self.old/'content.txt').read_text(),'User changed the inactive old source')
    def test_concurrent_disable_is_not_undone_by_rollback(self):
        def fail(point):
            if point=='after_health':
                path=self.home/'config.toml'
                path.write_text(path.read_text().replace('[plugins."superpowers@fable-superpowers"]\nenabled=true','[plugins."superpowers@fable-superpowers"]\nenabled=false'))
                raise RuntimeError('User disabled the plugin')
        result=self.manager(failpoint=fail).run()
        self.assertEqual(result['status'],'rolled_back')
        self.assertIn('enabled=false',(self.home/'config.toml').read_text())
        self.assertEqual(self.marketplace.read_bytes(),self.original)
        self.assertNotIn(('install','7.0.1'),self.backend.calls)

if __name__=='__main__': unittest.main()
