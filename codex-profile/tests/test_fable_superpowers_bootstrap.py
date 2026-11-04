"""Portable setup tests use an isolated home and fake native catalogue only."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'fable-superpowers/scripts'
sys.path.insert(0, str(SCRIPTS / 'updater'))
sys.path.insert(0, str(SCRIPTS))
from bootstrap import Setup, deploy_runtime
import bootstrap
from core import Conflict, exclusive_lock, inventory, write_json


class Backend:
    def __init__(self, home):
        self.home=home; self.rows=[]; self.registries=[]; self.calls=[]; self.fail_health=False
    def installed(self): return self.rows.copy()
    def marketplaces(self): return self.registries.copy()
    def register_marketplace(self, root):
        name=json.loads((root/'.agents/plugins/marketplace.json').read_text())['name']
        self.calls.append(('register',name));self.registries=[x for x in self.registries if x['name']!=name]+[{'name':name,'path':str(root)}]
    def add(self, plugin):
        self.calls.append(('add',plugin))
        row={'pluginId':plugin,'name':plugin.split('@')[0],'enabled':True,'version':'1.3.2' if plugin.startswith('fable5') else '7.0.2'}
        result={'pluginId':plugin}
        if plugin=='superpowers@gigma-skills':
            root=self.home/'local-plugins/gigma-skills'
            manifest=json.loads((root/'.agents/plugins/marketplace.json').read_text())
            source=next(x['source'] for x in manifest['plugins'] if x['name']=='superpowers')
            package=(root/source['path']).resolve();cache=self.home/'plugins/cache/gigma-skills/superpowers'/row['version']
            shutil.copytree(package,cache,dirs_exist_ok=True)
            row.update(source={'source':'local','path':str(package)},marketplaceSource={'sourceType':'local','source':str(root)})
            result['installedPath']=str(cache)
        self.rows=[x for x in self.rows if x['pluginId']!=plugin]+[row]
        path=self.home/'config.toml';text=path.read_text() if path.exists() else ''
        path.parent.mkdir(parents=True,exist_ok=True)
        if plugin not in text:path.write_text(text+'\n[plugins."'+plugin+'"]\nenabled=true\n')
        return result
    def remove(self, plugin):
        self.calls.append(('remove',plugin));self.rows=[x for x in self.rows if x['pluginId']!=plugin]
    def remove_marketplace(self,name):
        self.calls.append(('unregister',name));self.registries=[x for x in self.registries if x['name']!=name]
    def context(self): return {'codex':'test','fable_version':'1.3.2','validator_hashes':{'test':'1'}}
    def health(self,*args):
        self.calls.append(('health',))
        if self.fail_health:raise RuntimeError('bad native health')
        return {'status':'healthy'}


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.home=self.base/'custom home';self.root=self.home/'local-plugins/gigma-skills'
        self.catalog=self.base/'catalog'
        fable={'name':'fable5-codex','source':{'source':'url','url':'https://example.invalid/fable','sha':'a'*40}}
        superpowers={'name':'superpowers','source':{'source':'url','url':'https://github.com/fixture/superpowers.git','sha':'b'*40},'policy':{'installation':'AVAILABLE'},'category':'Developer Tools'}
        write_json(self.catalog/'.agents/plugins/marketplace.json',{'name':'gigma-skills','interface':{'displayName':'Complete catalogue'},'plugins':[
            {'name':'local-tools','source':{'source':'local','path':'./plugins/local-tools'},'category':'Productivity'},fable,superpowers,
            {'name':'other-external','source':{'source':'url','url':'https://example.invalid/other','sha':'c'*40}}]})
        write_json(self.catalog/'external-plugins.lock.json',{'plugins':[fable,{**superpowers,'version':'7.0.2'}]})
        self.backend=Backend(self.home);self.checks=[]
        self.runtime=self.base/'runtime';self.runtime.mkdir();(self.runtime/'update.py').write_text('runtime')
        self.policy=self.base/'policy.md';self.policy.write_text('portable policy\n')
    def tearDown(self):self.temp.cleanup()
    def stage(self,release,run,baseline_package=None):
        package=run/'package';write_json(package/'.codex-plugin/plugin.json',{'name':'superpowers','version':'7.0.2'})
        (package/'content.txt').write_text('verified')
        return {**release,'package_path':str(package),'stage_path':str(run),'commit':'b'*40}
    def compat(self,candidate,run,home,**kw):
        self.checks.append(kw);self.assertFalse(any(x['pluginId'].startswith('superpowers@') for x in self.backend.rows))
        return {'status':'passed','cases':{str(i):{'passed':True} for i in range(5)}}
    def setup(self,**kw):
        return Setup(self.home,backend=self.backend,marketplace_root=self.catalog,runtime_source=self.runtime,policy_source=self.policy,requirements=lambda:{'status':'passed'},latest=lambda:{'version':'7.0.2'},stage=self.stage,compatibility=kw.pop('compatibility',self.compat),**kw)
    def test_plan_is_read_only_for_fresh_home(self):
        result=self.setup().plan();self.assertEqual(result['status'],'planned');self.assertFalse(self.home.exists());self.assertEqual(self.backend.calls,[])
    def test_fresh_custom_home_verifies_before_activation_and_returns_schedule(self):
        result=self.setup().install();self.assertEqual(result['status'],'installed');self.assertEqual(self.checks,[{'allow_empty_outside':True}])
        self.assertTrue(result['automation']['pending_native_tool']);self.assertEqual((self.root/'maintenance/update.py').read_text(),'runtime')
        self.assertEqual(json.loads(Path(result['automation_request_path']).read_text()),result['automation'])
    def test_repeat_reuses_context_and_preserves_unrelated_settings(self):
        self.home.mkdir();(self.home/'config.toml').write_text('[unrelated]\nkeep="yes"\n')
        self.setup().install();before=(self.home/'config.toml').read_bytes()
        self.assertEqual(self.setup().install()['status'],'unchanged');self.assertEqual(len(self.checks),1)
        self.assertEqual((self.home/'config.toml').read_bytes(),before)
    def test_enabled_gigma_fable_reused_without_second_install(self):
        self.backend.rows=[{'pluginId':'fable5-codex@gigma-skills','name':'fable5-codex','enabled':True,'version':'1.3.2'}]
        self.setup().install();self.assertFalse(any(call[0]=='add' and call[1].startswith('fable5') for call in self.backend.calls))
    def test_explicit_disabled_fable_preserved(self):
        self.home.mkdir();(self.home/'config.toml').write_text('[plugins."fable5-codex@fable5"]\nenabled=false\n')
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(self.backend.calls,[])
    def test_disabled_superpowers_preserved(self):
        self.backend.rows=[{'pluginId':'superpowers@gigma-skills','name':'superpowers','enabled':False}]
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(self.backend.calls,[])
    def test_other_enabled_superpowers_source_preserved(self):
        self.backend.rows=[{'pluginId':'superpowers@other','name':'superpowers','enabled':True}]
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(self.backend.calls,[])
    def test_conflicting_registry_preserved(self):
        self.backend.registries=[{'name':'gigma-skills','path':str(self.base/'elsewhere')}]
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(self.backend.calls,[])
    def test_failed_gate_holds_before_activation(self):
        result=self.setup(compatibility=lambda *a,**k:{'status':'failed'}).install()
        self.assertEqual(result['status'],'held');self.assertFalse(any(x['pluginId'].startswith('superpowers@') for x in self.backend.rows))
    def test_failed_health_removes_only_owned_superpowers(self):
        self.backend.fail_health=True;result=self.setup().install();self.assertEqual(result['status'],'rolled_back')
        self.assertIn(('remove','superpowers@gigma-skills'),self.backend.calls)
        self.assertTrue(any(x['pluginId'].startswith('fable5') for x in self.backend.rows))
    def test_interrupted_owned_activation_is_recovered(self):
        def fault(point):
            if point=='after_install':raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.setup(failpoint=fault).install()
        self.assertEqual(self.setup().install()['status'],'recovered');self.assertIn(('remove','superpowers@gigma-skills'),self.backend.calls)
    def test_modified_owned_runtime_is_preserved(self):
        self.setup().install();path=self.root/'maintenance/update.py';path.write_text('user edit')
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(path.read_text(),'user edit')
    def test_unknown_runtime_collision_is_preserved(self):
        path=self.root/'maintenance/update.py';path.parent.mkdir(parents=True);path.write_text('unowned')
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(path.read_text(),'unowned')

    def test_two_enabled_fables_are_rejected_before_any_mutation(self):
        self.backend.rows=[{'pluginId':'fable5-codex@one','enabled':True},{'pluginId':'fable5-codex@two','enabled':True}]
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(self.backend.calls,[]);self.assertFalse(self.home.exists())

    def test_existing_registered_gigma_source_requires_explicit_adoption(self):
        self.backend.registries=[{'name':'gigma-skills','root':str(self.base/'registered elsewhere')}]
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(self.backend.calls,[])
        self.setup(adopt_marketplace=True).install();self.assertIn(('register','gigma-skills'),self.backend.calls)
        self.assertIn(('add','fable5-codex@gigma-skills'),self.backend.calls)

    def test_failed_gate_is_held_without_repeating_trials(self):
        calls=[]
        def fail(*args,**kw):calls.append(True);return {'status':'failed'}
        first=self.setup(compatibility=fail).install();second=self.setup(compatibility=fail).install()
        self.assertTrue(first['new_failure']);self.assertFalse(second['new_failure']);self.assertEqual(len(calls),1)

    def test_recovery_preserves_changed_source_and_unrelated_user_settings(self):
        def fault(point):
            if point=='after_install':raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.setup(failpoint=fault).install()
        config=self.home/'config.toml';config.write_text(config.read_text()+'\n[unrelated]\nkeep="late change"\n')
        self.setup().install();self.assertIn('late change',config.read_text())
        self.assertEqual([x['name'] for x in self.backend.rows],['fable5-codex'])

    def test_recovery_does_not_remove_independently_changed_plugin(self):
        def fault(point):
            if point=='after_install':raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.setup(failpoint=fault).install()
        next(x for x in self.backend.rows if x['pluginId'].startswith('superpowers@'))['version']='8.0.0'
        with self.assertRaises(Conflict):self.setup().install()
        self.assertNotIn(('remove','superpowers@gigma-skills'),self.backend.calls)

    def test_deployment_accepts_verified_legacy_hashes_and_preserves_extra_files(self):
        destination=self.root/'maintenance';destination.mkdir(parents=True)
        (destination/'update.py').write_text('old runtime');(destination/'user-notes.txt').write_text('keep')
        from core import digest
        write_json(destination/'deployment.json',{'files':{'update.py':digest(destination/'update.py')},'reviewer':'machine-local-do-not-copy'})
        result=deploy_runtime(self.runtime,self.root,apply=True)
        self.assertTrue(result['changed']);self.assertEqual((destination/'update.py').read_text(),'runtime')
        self.assertEqual((destination/'user-notes.txt').read_text(),'keep')
        self.assertNotIn('reviewer',(self.root/'updates/runtime-owned.json').read_text())

    def test_interrupted_runtime_copy_resumes_only_owned_old_or_new_bytes(self):
        destination=self.root/'maintenance';destination.mkdir(parents=True);(destination/'update.py').write_text('runtime')
        from core import digest
        desired={'update.py':digest(destination/'update.py')}
        write_json(self.root/'updates/runtime-transaction.json',{'phase':'prepared','old':{},'new':desired})
        deploy_runtime(self.runtime,self.root,apply=True)
        self.assertEqual(json.loads((self.root/'updates/runtime-owned.json').read_text())['files'],desired)

    def test_warm_validation_uses_owned_staging_copy_and_reuses_receipt(self):
        self.setup().install();(self.root/'updates/bootstrap-verified.json').unlink()
        calls=[]
        def check(candidate,run,home):
            calls.append(candidate)
            self.assertTrue(Path(candidate['package_path']).is_relative_to(Path(candidate['stage_path'])))
            self.assertTrue(Path(candidate['package_path']).exists())
            return {'status':'passed'}
        self.assertEqual(self.setup(compatibility=check).install()['status'],'validated')
        self.assertEqual(self.setup(compatibility=check).install()['status'],'unchanged');self.assertEqual(len(calls),1)

    def test_changes_during_activation_are_preserved_and_prevent_success(self):
        def health(*args):
            config=self.home/'config.toml';config.write_text(config.read_text()+'\n[unrelated]\nkeep="late edit"\n')
            (self.home/'AGENTS.md').write_text('user edited instructions')
            return {'status':'healthy'}
        self.backend.health=health
        result=self.setup().install()
        self.assertEqual(result['status'],'rolled_back');self.assertIn('late edit',(self.home/'config.toml').read_text())
        self.assertEqual((self.home/'AGENTS.md').read_text(),'user edited instructions')

    def test_full_gigma_catalog_is_preserved_and_registered_before_fable(self):
        result=self.setup().install();self.assertEqual(result['status'],'installed')
        self.assertEqual(self.backend.calls[:2],[('register','gigma-skills'),('add','fable5-codex@gigma-skills')])
        self.assertEqual([x['name'] for x in self.backend.registries],['gigma-skills'])
        original=json.loads((self.catalog/'.agents/plugins/marketplace.json').read_text())
        generated=json.loads((self.root/'.agents/plugins/marketplace.json').read_text())
        self.assertEqual(generated['interface'],original['interface']);self.assertEqual(len(generated['plugins']),len(original['plugins']))
        for before,after in zip(original['plugins'],generated['plugins']):
            if before['name']=='superpowers':
                self.assertEqual(after['category'],before['category']);self.assertEqual(after['policy'],before['policy'])
                self.assertEqual(after['source']['source'],'local')
            elif before['source']['source']=='local':
                self.assertEqual(after['source']['path'],str((self.catalog/before['source']['path']).resolve()))
            else:self.assertEqual(after,before)

    def test_failed_health_rolls_back_full_catalog_to_external_pin(self):
        self.backend.fail_health=True;self.setup().install()
        manifest=json.loads((self.root/'.agents/plugins/marketplace.json').read_text())
        original=json.loads((self.catalog/'.agents/plugins/marketplace.json').read_text())
        self.assertEqual(next(x for x in manifest['plugins'] if x['name']=='superpowers'),next(x for x in original['plugins'] if x['name']=='superpowers'))
        self.assertEqual(len(manifest['plugins']),len(original['plugins']))

    def test_catalog_user_changes_are_preserved(self):
        self.setup().install();path=self.root/'.agents/plugins/marketplace.json';value=json.loads(path.read_text())
        value['interface']['displayName']='User choice';write_json(path,value);before=path.read_bytes()
        with self.assertRaises(Conflict):self.setup().install()
        self.assertEqual(path.read_bytes(),before)

    def test_initial_release_uses_the_catalog_pin_and_refuses_a_different_commit(self):
        setup=self.setup();release=setup.initial_release()
        self.assertEqual(release['repo'],'fixture/superpowers');self.assertEqual(release['expected_commit'],'b'*40)
        original_stage=setup.stage
        def wrong(*args,**kwargs):return {**original_stage(*args,**kwargs),'commit':'f'*40}
        setup.stage=wrong
        with self.assertRaises(Conflict):setup.install()
        self.assertEqual(self.checks,[]);self.assertFalse(any(x['pluginId'].startswith('superpowers@') for x in self.backend.rows))

    def test_fresh_catalog_resumes_after_manifest_publication_before_receipt(self):
        setup=self.setup();publish=bootstrap.create_owned
        def interrupt(path,data):
            publish(path,data)
            if Path(path)==setup.marketplace:raise KeyboardInterrupt()
        with patch('bootstrap.create_owned',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        journal=setup.state/'marketplace-transaction.json'
        self.assertTrue(journal.exists(),'Manifest publication must have durable ownership evidence first.')
        pending=json.loads(journal.read_text())
        self.assertIsNone(pending['old_manifest_hex']);self.assertIsNone(pending['old_receipt_hex'])
        self.assertEqual(pending['new_manifest_hex'],setup.marketplace.read_bytes().hex())
        self.assertFalse((setup.state/'marketplace-owned.json').exists())
        self.assertEqual(self.setup().install()['status'],'installed')
        self.assertEqual(json.loads(journal.read_text())['phase'],'complete')

    def test_catalog_update_resumes_after_manifest_publication_before_receipt(self):
        self.setup().install();setup=self.setup();publish=bootstrap.atomic_write
        old=setup.marketplace.read_bytes();receipt=(setup.state/'marketplace-owned.json').read_bytes()
        catalog_path=self.catalog/'.agents/plugins/marketplace.json';catalog=json.loads(catalog_path.read_text())
        catalog['interface']['displayName']='New catalogue release';write_json(catalog_path,catalog)
        def interrupt(path,data,expected=None):
            publish(path,data,expected=expected)
            if Path(path)==setup.marketplace:raise KeyboardInterrupt()
        with patch('bootstrap.atomic_write',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        journal=setup.state/'marketplace-transaction.json'
        self.assertTrue(journal.exists(),'Catalog updates must record both old manifest and receipt before publication.')
        pending=json.loads(journal.read_text())
        self.assertEqual(pending['old_manifest_hex'],old.hex());self.assertEqual(pending['old_receipt_hex'],receipt.hex())
        self.assertEqual(pending['new_manifest_hex'],setup.marketplace.read_bytes().hex())
        self.assertEqual((setup.state/'marketplace-owned.json').read_bytes(),receipt)
        self.assertEqual(self.setup().install()['status'],'unchanged')
        self.assertEqual(json.loads((setup.state/'marketplace-owned.json').read_text())['manifest_hex'],setup.marketplace.read_bytes().hex())

    def test_interrupted_catalog_recovery_preserves_unknown_manifest_or_receipt(self):
        for target in ['manifest','receipt']:
            with self.subTest(target=target):
                isolated=self.base/target;backend=Backend(isolated)
                setup=Setup(isolated,marketplace_root=self.catalog,backend=backend,runtime_source=self.runtime,
                    policy_source=self.policy,requirements=lambda:{'status':'passed'})
                publish=bootstrap.create_owned
                def interrupt(path,data):
                    publish(path,data)
                    if Path(path)==setup.marketplace:raise KeyboardInterrupt()
                with patch('bootstrap.create_owned',side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):setup.install()
                self.assertTrue((setup.state/'marketplace-transaction.json').exists())
                path=setup.marketplace if target=='manifest' else setup.state/'marketplace-owned.json'
                path.write_text('independent user change');before=inventory(isolated)
                with self.assertRaises(Conflict):setup.install()
                self.assertEqual(inventory(isolated),before);self.assertEqual(backend.calls,[])

    def test_direct_url_superpowers_adoption_fails_before_any_mutation(self):
        self.backend.rows=[{'pluginId':'superpowers@gigma-skills','name':'superpowers','enabled':True,'version':'7.0.2'}]
        self.backend.registries=[{'name':'gigma-skills','path':str(self.catalog)}]
        before=inventory(self.base)
        for action in ['plan','install']:
            with self.subTest(action=action):
                with self.assertRaisesRegex(Conflict,'clean Codex home'):
                    getattr(self.setup(adopt_marketplace=True),action)()
                self.assertEqual(inventory(self.base),before);self.assertEqual(self.backend.calls,[])

    def test_url_superpowers_in_managed_registry_fails_before_any_mutation(self):
        setup=self.setup();setup.prepare_catalog(apply=True)
        self.backend.rows=[{'pluginId':'superpowers@gigma-skills','name':'superpowers','enabled':True,'version':'7.0.2'}]
        self.backend.registries=[{'name':'gigma-skills','path':str(self.root)}]
        before=inventory(self.base)
        with self.assertRaisesRegex(Conflict,'clean Codex home'):setup.install()
        self.assertEqual(inventory(self.base),before);self.assertEqual(self.backend.calls,[])

    def test_recovery_preserves_disabled_row_before_native_add_receipt(self):
        setup=self.setup();add=self.backend.add
        def interrupt(plugin):
            result=add(plugin)
            if plugin=='superpowers@gigma-skills':raise KeyboardInterrupt()
            return result
        with patch.object(self.backend,'add',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        row=next(x for x in self.backend.rows if x['pluginId']=='superpowers@gigma-skills');row['enabled']=False
        before=inventory(self.home)
        with self.assertRaises(Conflict):setup.recover()
        self.assertEqual(inventory(self.home),before);self.assertNotIn(('remove','superpowers@gigma-skills'),self.backend.calls)

    def test_recovery_preserves_unidentified_row_before_native_add_receipt(self):
        setup=self.setup();add=self.backend.add
        def interrupt(plugin):
            result=add(plugin)
            if plugin=='superpowers@gigma-skills':raise KeyboardInterrupt()
            return result
        with patch.object(self.backend,'add',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        row=next(x for x in self.backend.rows if x['pluginId']=='superpowers@gigma-skills')
        row.pop('source');row.pop('marketplaceSource')
        before=inventory(self.home)
        with self.assertRaises(Conflict):setup.recover()
        self.assertEqual(inventory(self.home),before);self.assertNotIn(('remove','superpowers@gigma-skills'),self.backend.calls)

    def test_registry_changed_during_trials_is_preserved_before_activation(self):
        foreign={'name':'gigma-skills','path':str(self.base/'user-selected-catalog')}
        def check(*args,**kw):
            self.backend.registries=[foreign];return {'status':'passed'}
        with self.assertRaises(Conflict):self.setup(adopt_marketplace=True,compatibility=check).install()
        self.assertEqual(self.backend.registries,[foreign]);self.assertNotIn(('add','superpowers@gigma-skills'),self.backend.calls)

    def test_direct_native_git_row_is_rejected_even_with_managed_local_catalog(self):
        self.setup().install()
        row=next(x for x in self.backend.rows if x['pluginId']=='superpowers@gigma-skills')
        row['source']={'source':'git','url':'https://github.com/fixture/superpowers.git','sha':'b'*40}
        before=inventory(self.home);calls=self.backend.calls.copy()
        with self.assertRaisesRegex(Conflict,'clean Codex home'):self.setup(adopt_marketplace=True).install()
        self.assertEqual(inventory(self.home),before);self.assertEqual(self.backend.calls,calls)

    def test_recovery_preserves_modified_cache_before_native_add_receipt(self):
        setup=self.setup();add=self.backend.add
        def interrupt(plugin):
            result=add(plugin)
            if plugin=='superpowers@gigma-skills':raise KeyboardInterrupt()
            return result
        with patch.object(self.backend,'add',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        cache=self.home/'plugins/cache/gigma-skills/superpowers/7.0.2/content.txt';cache.write_text('user cache edit')
        before=inventory(self.home)
        with self.assertRaises(Conflict):setup.recover()
        self.assertEqual(inventory(self.home),before);self.assertNotIn(('remove','superpowers@gigma-skills'),self.backend.calls)

    def test_catalog_journal_precedes_manifest_and_read_only_plan_leaves_it_pending(self):
        setup=self.setup();publish=bootstrap.create_owned
        def interrupt(path,data):
            if Path(path)==setup.marketplace:raise KeyboardInterrupt()
            publish(path,data)
        with patch('bootstrap.create_owned',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        self.assertFalse(setup.marketplace.exists());before=inventory(self.home)
        self.assertEqual(setup.plan()['status'],'planned');self.assertEqual(inventory(self.home),before)
        self.assertEqual(self.setup().install()['status'],'installed')

    def test_catalog_recovers_complete_bytes_before_final_journal_flush(self):
        setup=self.setup();publish=bootstrap.create_owned;record=setup.state/'marketplace-owned.json'
        def interrupt(path,data):
            publish(path,data)
            if Path(path)==record:raise KeyboardInterrupt()
        with patch('bootstrap.create_owned',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        journal=setup.state/'marketplace-transaction.json'
        self.assertEqual(json.loads(journal.read_text())['phase'],'prepared')
        self.assertEqual(self.setup().install()['status'],'installed')
        self.assertEqual(json.loads(journal.read_text())['phase'],'complete')

    def test_catalog_does_not_finalize_if_manifest_returns_to_known_old_bytes(self):
        self.setup().install();setup=self.setup();old=setup.marketplace.read_bytes()
        path=self.catalog/'.agents/plugins/marketplace.json';value=json.loads(path.read_text())
        value['interface']['displayName']='New catalogue release';write_json(path,value)
        publish=bootstrap.atomic_write
        def concurrent_change(path,data,expected=None):
            publish(path,data,expected=expected)
            if Path(path)==setup.state/'marketplace-owned.json':setup.marketplace.write_bytes(old)
        with exclusive_lock(setup.state/'update.lock'):
            with patch('bootstrap.atomic_write',side_effect=concurrent_change):
                with self.assertRaises(Conflict):setup.prepare_catalog(apply=True)
        self.assertEqual(setup.marketplace.read_bytes(),old)
        self.assertEqual(json.loads((setup.state/'marketplace-transaction.json').read_text())['phase'],'prepared')

    def test_unreceipted_verified_native_add_can_be_recovered(self):
        setup=self.setup();add=self.backend.add
        def interrupt(plugin):
            result=add(plugin)
            if plugin=='superpowers@gigma-skills':raise KeyboardInterrupt()
            return result
        with patch.object(self.backend,'add',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        self.assertNotIn('installed_row',json.loads(setup.journal.read_text()))
        self.assertEqual(self.setup().install()['status'],'recovered')
        self.assertIn(('remove','superpowers@gigma-skills'),self.backend.calls)

    def test_interruption_before_native_add_leaves_no_row_and_restores_pointer(self):
        setup=self.setup();add=self.backend.add
        def interrupt(plugin):
            if plugin=='superpowers@gigma-skills':raise KeyboardInterrupt()
            return add(plugin)
        with patch.object(self.backend,'add',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):setup.install()
        self.assertEqual(self.setup().install()['status'],'recovered')
        self.assertNotIn(('remove','superpowers@gigma-skills'),self.backend.calls)
        source=next(x['source'] for x in json.loads(setup.marketplace.read_text())['plugins'] if x['name']=='superpowers')
        self.assertEqual(source['source'],'url')

    def test_pending_normal_update_blocks_plan_and_install_without_mutation(self):
        for phase in ['prepared','switched','installed','recovering','recovery_required']:
            for action in ['plan','install']:
                with self.subTest(phase=phase,action=action):
                    home=self.base/(phase+'-'+action);backend=Backend(home);trials=[]
                    def check(*args,**kwargs):trials.append(True);return {'status':'passed'}
                    setup=Setup(home,marketplace_root=self.catalog,backend=backend,runtime_source=self.runtime,
                        policy_source=self.policy,requirements=lambda:{'status':'passed'},stage=self.stage,compatibility=check)
                    write_json(setup.state/'transaction.json',{'phase':phase})
                    (home/'AGENTS.md').write_text('existing user instructions')
                    before=inventory(home)
                    with self.assertRaisesRegex(Conflict,'Update-Superpowers.ps1.*-Action recover.*-CodexHome'):
                        getattr(setup,action)()
                    self.assertEqual(inventory(home),before);self.assertEqual(backend.calls,[]);self.assertEqual(trials,[])


if __name__=='__main__':unittest.main()
