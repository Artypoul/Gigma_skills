from pathlib import Path
import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import compatibility as c


def skill_text(name):
    return f'---\nname: {name}\ndescription: Example\n---\n# {name}\n'


def package(root,version='7.0.2',extra=False):
    target=root/'package'
    (target/'.codex-plugin').mkdir(parents=True)
    (target/'.codex-plugin/plugin.json').write_text(json.dumps({'name':'superpowers','version':version,'skills':'./skills'}))
    names=set(c.CRITICAL)|({'new-legitimate-skill'} if extra else set())
    for name in names:
        file=target/'skills'/name/'SKILL.md'
        file.parent.mkdir(parents=True)
        file.write_text(skill_text(name))
    return {'package_path':str(target),'stage_path':str(root),'version':version}


class CompatibilityUnitTests(unittest.TestCase):
    def test_empty_outside_catalog_requires_explicit_first_install_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);candidate=package(root/'stage');fixture=root/'fixture'
            with patch.object(c,'_native_catalog',return_value={'skills':[]}), patch.object(c,'materialize_staging_cache',return_value={}), \
                 patch.object(c,'staging_plugin_id',return_value='superpowers@candidate'), \
                 patch.object(c,'verify_catalog',return_value=({},{})),patch.object(c,'_helper_probe',return_value={}):
                with self.assertRaisesRegex(RuntimeError,'outside staging'):
                    c.preflight(candidate,{'approved_plan':fixture},root/'outside',root/'run',root/'home')
            stage_catalog={'skills':[{'pluginId':'superpowers@candidate'}]}
            with patch.object(c,'_native_catalog',side_effect=[{'skills':[]},stage_catalog,{'skills':[]}]), \
                 patch.object(c,'materialize_staging_cache',return_value={}),patch.object(c,'staging_plugin_id',return_value='superpowers@candidate'), \
                 patch.object(c,'verify_catalog',return_value=({},{})),patch.object(c,'_helper_probe',return_value={}):
                result=c.preflight(candidate,{'approved_plan':fixture},root/'outside',root/'run',root/'home',allow_empty_outside=True)
                self.assertEqual(result['outside_fingerprint'],[]);self.assertTrue(result['outside_catalogue_unchanged'])

    def lease_fixture(self, root):
        home=root/'home'
        home.mkdir()
        original=b'\xef\xbb\xbfmodel="current"\r\n[plugins."fable5-codex@fable5"]\r\nenabled=true\r\n'
        (home/'config.toml').write_bytes(original)
        run=root/'runs'/'one-run'/'compatibility'
        fixtures=[run/'fixtures'/name for name in ['small_config','bug_fix']]
        for fixture in fixtures:fixture.mkdir(parents=True)
        journal=run/'trust-lease.json'
        return home,original,run,fixtures,journal

    def test_critical_set_allows_additional_skills(self):
        with tempfile.TemporaryDirectory() as td:
            candidate=package(Path(td),extra=True)
            self.assertIn('new-legitimate-skill',c.candidate_skills(candidate))
            self.assertGreater(len(c.candidate_skills(candidate)),len(c.CRITICAL))

    def test_missing_critical_skill_rejects_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            candidate=package(Path(td))
            (Path(candidate['package_path'])/'skills/brainstorming/SKILL.md').unlink()
            with self.assertRaisesRegex(ValueError,'critical'):
                c.candidate_skills(candidate)

    def test_staging_marketplace_cannot_be_redirected(self):
        with tempfile.TemporaryDirectory() as td:
            candidate=package(Path(td))
            path=c.prepare_marketplace(candidate)
            data=json.loads(path.read_text())
            data['plugins'][0]['source']['path']='../another-package'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'another package'):
                c.prepare_marketplace(candidate)

    def test_trust_lease_preserves_concurrent_unrelated_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            config=root/'config.toml'
            config.write_text('model="current"\n[plugins."fable5-codex@fable5"]\nenabled=true\n')
            fixture=root/'fixture'
            fixture.mkdir()
            with c.TrustLease(root,[fixture]) as lease:
                self.assertEqual(len(lease.record['added']),1)
                config.write_text(config.read_text()+'\n[projects."unrelated"]\ntrust_level="trusted"\n')
            parsed=c.tomllib.loads(config.read_text())
            self.assertEqual(parsed['model'],'current')
            self.assertTrue(parsed['plugins']['fable5-codex@fable5']['enabled'])
            self.assertEqual(set(parsed['projects']),{'unrelated'})
            self.assertTrue(lease.record['unrelated_settings_preserved'])

    def test_trust_lease_restores_exact_original_bytes_without_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            config=root/'config.toml'
            before=b'\xef\xbb\xbfmodel="current"\r\n'
            config.write_bytes(before)
            fixture=root/'fixture'
            fixture.mkdir()
            with c.TrustLease(root,[fixture]) as lease:
                self.assertIn('trusted',config.read_text(encoding='utf-8-sig'))
            self.assertEqual(config.read_bytes(),before)
            self.assertTrue(lease.record['exact_original_bytes_restored'])

    def test_durable_lease_recovers_after_enter_without_exit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            lease=c.TrustLease(home,fixtures,journal_path=journal)
            replace=lease._replace_if_unchanged
            def assert_journal_first(expected,replacement):
                self.assertTrue(journal.is_file())
                receipt=json.loads(journal.read_text())
                self.assertEqual(receipt['original_sha256'],hashlib.sha256(original).hexdigest())
                self.assertEqual((home/'config.toml').read_bytes(),original)
                return replace(expected,replacement)
            with patch.object(lease,'_replace_if_unchanged',side_effect=assert_journal_first):
                lease.__enter__()
            self.assertNotEqual((home/'config.toml').read_bytes(),original)
            del lease  # Simulate process death: no __exit__ cleanup.
            recovered=c.recover_trust_leases(root/'runs',home)
            self.assertEqual((home/'config.toml').read_bytes(),original)
            self.assertFalse(journal.exists())
            self.assertTrue(recovered['passed'])
            self.assertEqual(len(recovered['recovered']),1)
            self.assertTrue(recovered['recovered'][0]['exact_original_bytes_restored'])

    def test_recovery_preserves_concurrent_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            c.TrustLease(home,fixtures,journal_path=journal).__enter__()
            config=home/'config.toml'
            text=config.read_text(encoding='utf-8-sig').replace('model="current"','model="user-choice"')
            config.write_text(text+'\n[projects."unrelated"]\ntrust_level="trusted"\n',encoding='utf-8')
            recovered=c.recover_trust_leases(root/'runs',home)
            model=c.tomllib.loads(config.read_text(encoding='utf-8-sig'))
            self.assertEqual(model['model'],'user-choice')
            self.assertTrue(model['plugins']['fable5-codex@fable5']['enabled'])
            self.assertEqual(set(model['projects']),{'unrelated'})
            self.assertFalse(journal.exists())
            self.assertTrue(recovered['recovered'][0]['unrelated_settings_preserved'])

    def test_recovery_preserves_model_edit_when_no_other_projects_exist(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            c.TrustLease(home,fixtures,journal_path=journal).__enter__()
            config=home/'config.toml'
            text=config.read_text(encoding='utf-8-sig').replace('model="current"','model="new-choice"')
            config.write_text(text,encoding='utf-8')
            c.recover_trust_leases(root/'runs',home)
            model=c.tomllib.loads(config.read_text(encoding='utf-8-sig'))
            self.assertEqual(model['model'],'new-choice')
            self.assertFalse(model.get('projects'))
            self.assertFalse(journal.exists())

    def test_recovery_handles_comment_on_owned_header(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            c.TrustLease(home,fixtures,journal_path=journal).__enter__()
            config=home/'config.toml'
            text=config.read_text(encoding='utf-8-sig')
            text=text.replace(']\ntrust_level = "trusted"','] # formatting comment\ntrust_level = "trusted"')
            config.write_text(text,encoding='utf-8')
            c.recover_trust_leases(root/'runs',home)
            self.assertFalse(c.tomllib.loads(config.read_text(encoding='utf-8-sig')).get('projects'))
            self.assertFalse(journal.exists())

    def test_recovery_refuses_changed_owned_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            c.TrustLease(home,fixtures,journal_path=journal).__enter__()
            config=home/'config.toml'
            config.write_bytes(config.read_bytes()+b'custom="preserve-user-edit"\r\n')
            before=config.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'changed concurrently'):
                c.recover_trust_leases(root/'runs',home)
            self.assertEqual(config.read_bytes(),before)
            self.assertTrue(journal.exists())

    def test_normal_lease_cleanup_removes_durable_journal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            with c.TrustLease(home,fixtures,journal_path=journal):
                self.assertTrue(journal.exists())
            self.assertFalse(journal.exists())
            self.assertEqual((home/'config.toml').read_bytes(),original)

    def test_recovery_refuses_redirected_home_or_out_of_scope_projects(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            c.TrustLease(home,fixtures,journal_path=journal).__enter__()
            config_before=(home/'config.toml').read_bytes()
            receipt=json.loads(journal.read_text())
            receipt['config_path']=str(root/'another-config.toml')
            journal.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(RuntimeError,'scope does not match'):
                c.recover_trust_leases(root/'runs',home)
            receipt['config_path']=str(home/'config.toml')
            receipt['owned_projects']=[str(root/'user-project')]
            journal.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(RuntimeError,'outside its owned fixture scope'):
                c.recover_trust_leases(root/'runs',home)
            self.assertEqual((home/'config.toml').read_bytes(),config_before)

    def test_recovery_clears_receipt_if_crash_preceded_config_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            home,original,run,fixtures,journal=self.lease_fixture(root)
            lease=c.TrustLease(home,fixtures,journal_path=journal)
            with patch.object(lease,'_replace_if_unchanged',side_effect=RuntimeError('simulated crash before write')):
                with self.assertRaises(RuntimeError):lease.__enter__()
            self.assertTrue(journal.exists())
            self.assertEqual((home/'config.toml').read_bytes(),original)
            c.recover_trust_leases(root/'runs',home)
            self.assertFalse(journal.exists())
            self.assertEqual((home/'config.toml').read_bytes(),original)

    def test_outside_fingerprint_detects_extra_staging_alias(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'SKILL.md'
            file.write_text(skill_text('brainstorming'))
            live={'pluginId':c.PLUGIN_ID,'name':'superpowers:brainstorming','path':str(file)}
            extra={**live,'pluginId':'superpowers@unexpected-staging-alias'}
            baseline=c.catalogue_fingerprint({'skills':[live]})
            self.assertNotEqual(baseline,c.catalogue_fingerprint({'skills':[live,extra]}))

    def test_trust_cleanup_refuses_to_erase_modified_owned_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            config=root/'config.toml'
            config.write_text('model="current"\n')
            fixture=root/'fixture'
            fixture.mkdir()
            lease=c.TrustLease(root,[fixture])
            lease.__enter__()
            config.write_text(config.read_text()+'custom="preserve"\n')
            with self.assertRaisesRegex(RuntimeError,'changed concurrently'):
                lease.__exit__(None,None,None)
            self.assertIn('custom="preserve"',config.read_text())

    def test_existing_untrusted_project_is_not_silently_trusted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fixture=root/'fixture'
            fixture.mkdir()
            key=str(fixture.resolve()).casefold() if c.os.name=='nt' else str(fixture.resolve())
            config=root/'config.toml'
            text='[projects.'+json.dumps(key)+']\ntrust_level="untrusted"\n'
            config.write_text(text)
            with self.assertRaisesRegex(RuntimeError,'conflicting'):
                c.TrustLease(root,[fixture]).__enter__()
            self.assertEqual(config.read_text(),text)

    def test_announcement_does_not_prove_skill_loading(self):
        targets={'brainstorming':{'path':'C:/cache/7.0.2/brainstorming/SKILL.md','sha256':'a'*64}}
        with tempfile.TemporaryDirectory() as td:
            fable=Path(td)/'FABLE.md'
            fable.write_text(skill_text('fable5-codex'))
            self.assertEqual(c.observed_skill_reads([{'type':'agentMessage','text':'Using brainstorming'}],targets,{'path':str(fable)}),{})

    def test_old_skill_path_is_not_candidate_activation(self):
        with tempfile.TemporaryDirectory() as td:
            fable=Path(td)/'FABLE.md'
            fable.write_text(skill_text('fable5-codex'))
            source=Path(td)/'7.0.2/brainstorming/SKILL.md'
            source.parent.mkdir(parents=True)
            source.write_text(skill_text('brainstorming'))
            targets={'brainstorming':{'path':str(source),'sha256':c.digest(source)}}
            items=[{'type':'commandExecution','exitCode':0,'command':'Get-Content C:/cache/7.0.1/brainstorming/SKILL.md','aggregatedOutput':skill_text('brainstorming'),'event_line':1}]
            self.assertNotIn('brainstorming',c.observed_skill_reads(items,targets,{'path':str(fable)}))

    def test_header_only_skill_read_does_not_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fable=root/'FABLE.md'
            fable.write_text(skill_text('fable5-codex'))
            source=root/'7.0.2/brainstorming/SKILL.md'
            source.parent.mkdir(parents=True)
            source.write_text(skill_text('brainstorming')+'\nEssential workflow body.\n')
            targets={'brainstorming':{'path':str(source),'sha256':c.digest(source)}}
            item={'type':'commandExecution','exitCode':0,'command':f'Get-Content -LiteralPath "{source}" -TotalCount 2','aggregatedOutput':'---\nname: brainstorming\n','event_line':1}
            self.assertNotIn('brainstorming',c.observed_skill_reads([item],targets,{'path':str(fable)}))
            item['aggregatedOutput']=source.read_text().replace('\n','\r\r\n')
            self.assertEqual(c.observed_skill_reads([item],targets,{'path':str(fable)})['brainstorming']['method'],'complete_file_read')

    def test_complete_variable_path_read_and_later_failure_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fable=root/'FABLE.md'
            fable.write_text(skill_text('fable5-codex'))
            source=root/'7.0.2/brainstorming/SKILL.md'
            source.parent.mkdir(parents=True)
            source.write_text(skill_text('brainstorming')+'\nEssential workflow body.\n')
            targets={'brainstorming':{'path':str(source),'sha256':c.digest(source)}}
            body=source.read_text()
            commands=[f"$skillRoot = '{source.parent.parent}'; Get-Content -LiteralPath \"$skillRoot/brainstorming/SKILL.md\"",
                f"Get-Content -LiteralPath '{source}'; Get-Content -LiteralPath 'missing-reference.md'"]
            for command in commands:
                with self.subTest(command=command):
                    item={'type':'commandExecution','exitCode':1,'command':command,'aggregatedOutput':body+'\nCannot find missing-reference.md','event_line':12}
                    self.assertIn('brainstorming',c.observed_skill_reads([item],targets,{'path':str(fable)}))
            failed={'type':'commandExecution','exitCode':1,'command':commands[0],'aggregatedOutput':'Get-Content: Access to the path is denied.','event_line':13}
            self.assertNotIn('brainstorming',c.observed_skill_reads([failed],targets,{'path':str(fable)}))
            old={**failed,'command':"$skillRoot = 'C:/cache/7.0.1'; Get-Content \"$skillRoot/brainstorming/SKILL.md\"",'aggregatedOutput':body}
            self.assertNotIn('brainstorming',c.observed_skill_reads([old],targets,{'path':str(fable)}))

    def test_unattended_case_rejects_interactive_requests(self):
        native={'unexpected_client_requests':[{'method':'item/tool/requestUserInput'}]}
        for name in c.CASES:
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError,'interactive'):
                    c.assess_case(name,Path('C:/fixture'),native,Path('C:/missing'),{}, {})

    def test_complete_mcp_pagination_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            fable=Path(td)/'FABLE.md'
            fable.write_text(skill_text('fable5-codex'))
            target={'path':'C:/cache/7.0.2/brainstorming/SKILL.md','sha256':'a'*64}
            def page(offset,text):
                return {'type':'mcpToolCall','tool':'read_skill','status':'completed','event_line':offset+1,'result':{'structuredContent':{'skill':{'name':'superpowers:brainstorming','path':target['path']},'sha256':target['sha256'],'offset':offset,'content':text,'total_chars':6}}}
            first=page(0,'abc')
            self.assertNotIn('brainstorming',c.observed_skill_reads([first],{'brainstorming':target},{'path':str(fable)}))
            loaded=c.observed_skill_reads([first,page(3,'def')],{'brainstorming':target},{'path':str(fable)})
            self.assertEqual(loaded['brainstorming']['method'],'complete_mcp_read')

    def test_receipt_or_empty_wait_is_not_independent_review(self):
        with self.assertRaisesRegex(RuntimeError,'separate reviewer'):
            c.review_evidence({'child_reports':{},'native_collaboration_calls':[{'tool':'wait','receiverThreadIds':[]} ]})

    def test_real_child_lifecycle_and_substantive_verdict_pass(self):
        text='Approve. Reviewed the diff against the approved plan, checked all source files and edge cases. Independent tests pass and the implementation meets the requested scope.'
        native={'native_subagent_activity':[{'agentThreadId':'reviewer','kind':'started'},{'agentThreadId':'reviewer','kind':'completed'}],
            'child_reports':{'reviewer':[{'phase':'final_answer','text':text,'event_line':42}]}}
        self.assertTrue(c.review_evidence(native)['passed'])
        changed=copy.deepcopy(native)
        changed['native_subagent_activity'].pop()
        with self.assertRaises(RuntimeError):c.review_evidence(changed)

    def test_ready_with_explicit_no_findings_is_approval(self):
        text='Ready: no Critical, Important, or Minor findings.\nReviewed the uncommitted diff against the approved plan and verified all supplied source hashes. Independent tests pass and no files were edited.'
        native={'native_subagent_activity':[{'agentThreadId':'reviewer','kind':'started'},{'agentThreadId':'reviewer','kind':'completed'}],
            'child_reports':{'reviewer':[{'phase':'final_answer','text':text,'event_line':42}]}}
        self.assertTrue(c.review_evidence(native)['passed'])
        for verdict in ['Not ready: no Critical, Important, or Minor findings.',
                        'Ready: no Critical, Important, or Minor findings if the remaining tests pass.',
                        'Ready: no Critical, Important, or Minor findings; provided the defect is fixed.',
                        'Ready: Critical, Important, or Minor findings remain.']:
            with self.subTest(verdict=verdict):
                bad=copy.deepcopy(native)
                bad['child_reports']['reviewer'][0]['text']=verdict+'\nReviewed the diff against the approved plan and ran all independent tests. The remaining condition must be resolved before completion.'
                with self.assertRaises(RuntimeError):c.review_evidence(bad)

    def test_review_must_start_after_latest_production_change(self):
        text='Approve. Reviewed the final source diff against the approved plan and checked the exact source files. All independent tests passed and no defects remain.'
        native={'native_subagent_activity':[{'agentThreadId':'reviewer','kind':'started','event_line':30},{'agentThreadId':'reviewer','kind':'completed','event_line':45}],
            'child_reports':{'reviewer':[{'phase':'final_answer','text':text,'event_line':42}]}}
        self.assertEqual(c.review_evidence(native,after_event_line=25)['reviewers'][0]['reviewer_start_event_line'],30)
        for last_write in [30,35,43]:
            with self.subTest(last_write=last_write):
                with self.assertRaises(RuntimeError):c.review_evidence(native,after_event_line=last_write)
        missing=copy.deepcopy(native)
        del missing['child_reports']['reviewer'][0]['event_line']
        with self.assertRaises(RuntimeError):c.review_evidence(missing,after_event_line=25)
        stale=copy.deepcopy(native)
        stale['native_subagent_activity'][1]['event_line']=20
        with self.assertRaises(RuntimeError):c.review_evidence(stale,after_event_line=25)

    def test_negative_or_conditional_verdict_is_rejected(self):
        for verdict in ['Do not approve','Not approved','Approve if the failing tests are fixed','Approve when tests pass','Approve provided the defect is fixed','Approved subject to corrections','Не готово','Одобрено при условии исправлений']:
            with self.subTest(verdict=verdict):
                text=f'Verdict: {verdict}.\nReviewed the full diff against the approved plan and all source files. The independent tests exposed an unresolved condition that must be addressed.'
                native={'native_subagent_activity':[{'agentThreadId':'r','kind':'started'},{'agentThreadId':'r','kind':'completed'}],
                    'child_reports':{'r':[{'phase':'final_answer','text':text}]}}
                with self.assertRaises(RuntimeError):c.review_evidence(native)

    def test_approve_with_important_finding_is_rejected(self):
        text='Verdict: Approve.\nReviewed the complete diff against the plan and ran tests for the source files.\nImportant: Broken input validation remains unresolved.'
        native={'native_subagent_activity':[{'agentThreadId':'r','kind':'started'},{'agentThreadId':'r','kind':'completed'}],
            'child_reports':{'r':[{'phase':'final_answer','text':text}]}}
        with self.assertRaises(RuntimeError):c.review_evidence(native)

    def test_bug_red_before_production_and_green_after(self):
        fixture=Path('C:/fixture')
        def write(path,line):return {'type':'fileChange','event_line':line,'changes':[{'path':str(fixture/path)}]}
        red={'type':'commandExecution','event_line':2,'command':'python -m unittest','exitCode':1,'aggregatedOutput':'AssertionError: 190 != 180\nFAILED'}
        green={'type':'commandExecution','event_line':4,'command':'python -m unittest','exitCode':0,'aggregatedOutput':'Ran 6 tests in 0.001s\n\nOK\n'}
        items=[write('tests/test_discounts.py',1),red,write('discounts.py',3),green]
        self.assertTrue(c.tdd_ordering('bug_fix',fixture,items)['passed'])
        with self.assertRaisesRegex(RuntimeError,'RED must precede'):
            c.tdd_ordering('bug_fix',fixture,[items[2],items[0],red,green])
        with self.assertRaisesRegex(RuntimeError,'GREEN must follow'):
            c.tdd_ordering('bug_fix',fixture,[items[0],red,green,items[2]])

    def test_hash_and_diff_reads_are_not_writes_to_mentioned_source(self):
        fixture=Path('C:/fixture')
        commands=[
            "$planPath = Join-Path (Get-Location) 'APPROVED_PLAN.md'; $planText = [System.IO.File]::ReadAllText($planPath); [System.IO.File]::WriteAllText($planPath, $planText.Replace('- [ ]', '- [x]')); $reviewDir = Join-Path (Get-Location) '.superpowers/sdd/APPROVED_PLAN'; $reviewDiff = git diff -- invoice_helpers.py invoice_cli.py tests/test_invoice_helpers.py; [System.IO.File]::WriteAllLines((Join-Path $reviewDir 'review.diff'), [string[]]$reviewDiff); Get-FileHash -LiteralPath 'invoice_helpers.py','invoice_cli.py'",
            "Add-Content -LiteralPath '.superpowers/sdd/APPROVED_PLAN/progress.md' -Value 'Final review complete'; git diff --check; $reviewFiles = @('invoice_helpers.py','invoice_cli.py'); Get-FileHash -LiteralPath $reviewFiles",
        ]
        for command in commands:
            with self.subTest(command=command):
                item={'type':'commandExecution','command':command}
                self.assertFalse(c._writes_path(item,fixture,'invoice_helpers.py'))
                self.assertFalse(c._writes_path(item,fixture,'invoice_cli.py'))
                # Native command rendering escapes inner quote boundaries.
                escaped=command.replace("'","'\"'")
                self.assertFalse(c._writes_path({'type':'commandExecution','command':escaped},fixture,'invoice_helpers.py'))
        self.assertTrue(c._writes_path({'type':'commandExecution','command':commands[0]},fixture,'APPROVED_PLAN.md'))
        for command in ["Set-Content -LiteralPath 'invoice_helpers.py' -Value 'new implementation'",
                        "$source = Join-Path (Get-Location) 'invoice_helpers.py'; [System.IO.File]::WriteAllText($source, 'new implementation')",
                        "Path('invoice_helpers.py').write_text('new implementation')"]:
            with self.subTest(command=command):
                self.assertTrue(c._writes_path({'type':'commandExecution','command':command},fixture,'invoice_helpers.py'))
        mixed="Path('review.diff').write_text('receipt'); source = Path('invoice_helpers.py'); source.write_text('changed implementation')"
        self.assertTrue(c._writes_path({'type':'commandExecution','command':mixed},fixture,'invoice_helpers.py'))

    def test_production_command_write_after_green_is_rejected(self):
        fixture=Path('C:/fixture')
        items=[{'type':'fileChange','event_line':1,'changes':[{'path':str(fixture/'tests/test_discounts.py')}]},
            {'type':'commandExecution','event_line':2,'command':'python -m unittest','exitCode':1,'aggregatedOutput':'AssertionError: 190 != 180\nFAILED'},
            {'type':'fileChange','event_line':3,'changes':[{'path':str(fixture/'discounts.py')}]},
            {'type':'commandExecution','event_line':4,'command':'python -m unittest','exitCode':0,'aggregatedOutput':'Ran 6 tests in 0.001s\nOK\n'},
            {'type':'commandExecution','event_line':5,'command':"Set-Content -LiteralPath 'discounts.py' -Value 'changed after green'",'exitCode':0}]
        with self.assertRaisesRegex(RuntimeError,'GREEN must follow'):
            c.tdd_ordering('bug_fix',fixture,items)

    def test_plan_requires_each_interface_red_before_its_module(self):
        fixture=Path('C:/fixture')
        def write(path,line):return {'type':'fileChange','event_line':line,'changes':[{'path':str(fixture/path)}]}
        def red(name,line):return {'type':'commandExecution','event_line':line,'command':'python -m unittest','exitCode':1,'aggregatedOutput':f'ImportError: cannot import name {name}'}
        def green(line):return {'type':'commandExecution','event_line':line,'command':'python -m unittest','exitCode':0,'aggregatedOutput':'Ran 8 tests in 0.001s\nOK\n'}
        items=[write('tests/test_invoice_helpers.py',1),red('normalize_currency',2),write('invoice_helpers.py',3),green(4),
            write('tests/test_invoice_cli.py',5),red('format_invoice',6),write('invoice_cli.py',7),green(8)]
        self.assertTrue(c.tdd_ordering('approved_plan',fixture,items)['passed'])
        bad=items[:5]+[items[6],items[5],items[7]]
        with self.assertRaisesRegex(RuntimeError,'RED must precede'):
            c.tdd_ordering('approved_plan',fixture,bad)

    def test_inventory_rejects_traversal_and_normalizes_case(self):
        self.assertEqual(c._inventory_map([{'Path':'skills\\x\\SKILL.md','SHA256':'A'*64}]),{'skills/x/SKILL.md':'a'*64})
        with self.assertRaises(ValueError):c._inventory_map([{'path':'../escape','sha256':'a'*64}])


if __name__=='__main__':
    unittest.main()
