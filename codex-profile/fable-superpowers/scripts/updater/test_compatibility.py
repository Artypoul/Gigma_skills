from pathlib import Path
import copy
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
import hashlib
import json
import shutil
import subprocess
import sys
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


class CompatibilityFailureClassificationTests(unittest.TestCase):
    def execute(self,*,case_error=None,native_status='completed',assessment_error=None,preflight_error=None):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home=root/'home';home.mkdir();(home/'AGENTS.md').write_text('policy')
            (home/'config.toml').write_text('')
            fixture=root/'fixture';(fixture/'.codex').mkdir(parents=True);(fixture/'.codex/config.toml').write_text('')
            selected={'candidate_skills':{},'fable_skill':{},'outside_fingerprint':[]}
            with ExitStack() as stack:
                for name,kwargs in {
                    'prepare_marketplace':{'return_value':None},
                    'prepare_fixtures':{'return_value':({'approved_plan':fixture},root/'outside')},
                    'TrustLease':{'return_value':nullcontext(SimpleNamespace(record={}))},
                    'preflight':{'side_effect':preflight_error} if preflight_error else {'return_value':selected},
                    '_fixture_python':{'return_value':{'exit_code':0}},
                    '_case_run':{'side_effect':case_error} if case_error else {'return_value':{'status':native_status,'thread_id':'root'}},
                    'assess_case':{'side_effect':assessment_error} if assessment_error else {'return_value':{'passed':True}},
                    '_native_catalog':{'return_value':{'skills':[]}},
                }.items():stack.enter_context(patch.object(c,name,**kwargs))
                result=c.run_compatibility({'version':'7.0.2'},root/'run',home)
            self.assertEqual(json.loads((root/'run/compatibility.json').read_text())['retryable'],result['retryable'])
            return result

    def test_preflight_transport_failure_is_retryable(self):
        result=self.execute(preflight_error=RuntimeError('model service temporarily unavailable'))
        self.assertEqual(result['status'],'failed');self.assertTrue(result['retryable'])

    def test_preflight_timeout_and_transport_decode_failure_remain_retryable(self):
        for error in [TimeoutError('service timed out'),json.JSONDecodeError('truncated service response','',0)]:
            with self.subTest(error=type(error).__name__):
                result=self.execute(preflight_error=error)
                self.assertEqual(result['status'],'failed');self.assertTrue(result['retryable'])

    def test_invalid_candidate_structure_is_a_stable_hold_before_native_trials(self):
        from core import hold_receipt, held_receipt_applies
        for invalid in ['missing_frontmatter','duplicate_skill_name']:
            with self.subTest(invalid=invalid),tempfile.TemporaryDirectory() as td:
                root=Path(td);home=root/'home';home.mkdir();(home/'AGENTS.md').write_text('policy')
                (home/'config.toml').write_text('')
                candidate=package(root/'stage')
                skill=Path(candidate['package_path'])/'skills/brainstorming/SKILL.md'
                skill.write_text('invalid frontmatter' if invalid=='missing_frontmatter' else skill_text('writing-plans'))
                with patch.object(c,'_native_catalog') as native,patch.object(c,'_case_run') as trial,patch.object(c,'_cmd') as command:
                    result=c.run_compatibility(candidate,root/'run',home)
                native.assert_not_called();trial.assert_not_called();command.assert_not_called()
                self.assertEqual(result['status'],'failed');self.assertFalse(result['retryable'])
                self.assertEqual(result['errors'][0]['type'],'ValueError')
                receipt=hold_receipt('same-context',root/'run/compatibility.json',result)
                self.assertNotIn('retry_after_utc',receipt)
                receipt['checked_at_utc']='2000-01-01T00:00:00+00:00'
                self.assertTrue(held_receipt_applies(receipt,'same-context'))
                self.assertFalse(held_receipt_applies(receipt,'same-context',retry=True))

    def test_case_execution_exception_is_retryable(self):
        result=self.execute(case_error=RuntimeError('expired transport'))
        self.assertEqual(result['status'],'failed');self.assertTrue(result['retryable'])

    def test_failed_native_task_before_assessment_is_retryable(self):
        result=self.execute(native_status='failed')
        self.assertEqual(result['status'],'failed');self.assertTrue(result['retryable'])

    def test_assessed_behavior_rejection_is_stable(self):
        result=self.execute(assessment_error=RuntimeError('repeated unnecessary question'))
        self.assertEqual(result['status'],'failed');self.assertFalse(result['retryable'])

    def test_passing_gate_never_requests_retry(self):
        result=self.execute();self.assertEqual(result['status'],'passed');self.assertFalse(result['retryable'])


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
            root = Path(td)
            fable = root / 'FABLE.md'
            fable.write_text(skill_text('fable5-codex'))
            skill = root / 'superpowers' / 'brainstorming' / 'SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_bytes(b'abcdef')
            target = {'id': 'selected:brainstorming', 'plugin_id': 'superpowers@staged',
                      'path': str(skill), 'sha256': c.digest(skill)}
            fable_record = {'path': str(fable), 'cwd': str(root),
                            'catalog_sha256': 'f' * 64}
            def page(offset, text):
                return {'type': 'mcpToolCall', 'tool': 'read_skill', 'status': 'completed',
                        'event_line': offset + 1, 'result': {'structuredContent': {
                            'skill': {'id': target['id'], 'plugin_id': target['plugin_id'],
                                      'name': 'superpowers:brainstorming', 'path': target['path']},
                            'sha256': target['sha256'], 'offset': offset,
                            'content': text, 'total_chars': 6, 'partial': False,
                            'warning_count': 0, 'warnings': [], 'cwd': str(root),
                            'catalog_sha256': fable_record['catalog_sha256'],
                            'next_offset': offset + len(text) if offset + len(text) < 6 else None}}}
            first = page(0, 'abc')
            self.assertNotIn('brainstorming', c.observed_skill_reads(
                [first], {'brainstorming': target}, fable_record))
            loaded = c.observed_skill_reads(
                [first, page(3, 'def')], {'brainstorming': target}, fable_record)
            self.assertEqual(loaded['brainstorming']['method'], 'complete_mcp_read')
            self.assertTrue(loaded['brainstorming']['content_verified'])


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

    def test_child_snapshots_preserve_observed_review_receipts(self):
        observer=c._runner_module()
        final={'id':'review-final','type':'agentMessage','phase':'final_answer',
            'text':'Approve. Reviewed the final source diff against the approved plan and checked the exact source files. All independent tests passed and no defects remain.'}
        observed={'thread_id':'reviewer','turn_id':'review-turn','event_line':42,**final}
        activities=[{'agentThreadId':'reviewer','kind':'started','event_line':30},
            {'agentThreadId':'reviewer','kind':'completed','event_line':45}]
        for snapshot in [{'thread':{'turns':[{'items':[final]}]}},{'items':[{'item':final}]}]:
            with self.subTest(snapshot=snapshot):
                reports=observer.public_child_reports({'reviewer':snapshot},{('reviewer','review-final'):observed},{})
                report=reports['reviewer'][0]
                self.assertEqual(report.get('event_line'),42)
                self.assertEqual(report.get('thread_id'),'reviewer')
                self.assertEqual(report.get('turn_id'),'review-turn')
                self.assertTrue(c.review_evidence({'native_subagent_activity':activities,'child_reports':reports},after_event_line=25)['passed'])

    def test_snapshot_only_or_changed_review_has_no_observed_chronology(self):
        observer=c._runner_module()
        final={'id':'review-final','type':'agentMessage','phase':'final_answer',
            'text':'Approve. Reviewed the final source diff against the approved plan and checked the exact source files. All independent tests passed and no defects remain.'}
        observed={'thread_id':'reviewer','event_line':42,**final}
        activities=[{'agentThreadId':'reviewer','kind':'started','event_line':30},
            {'agentThreadId':'reviewer','kind':'completed','event_line':45}]
        for item,messages in [({**final,'event_line':42},{}),
                              ({**final,'text':final['text']+' Additional unobserved text.'},{('reviewer','review-final'):observed})]:
            with self.subTest(item=item):
                reports=observer.public_child_reports({'reviewer':{'items':[{'item':item}]}},messages,{})
                self.assertNotIn('event_line',reports['reviewer'][0])
                with self.assertRaises(RuntimeError):
                    c.review_evidence({'native_subagent_activity':activities,'child_reports':reports},after_event_line=25)

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
        fixture=Path(tempfile.gettempdir()).resolve()/'fixture'
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


class CurrentSubjectReviewRegressionTests(unittest.TestCase):
    """A3: old approvals and partial scope must never close the current gate."""

    @staticmethod
    def report(text, line, *, evidence=None):
        if evidence is not None:
            text += "\n" + "REVIEW_EVIDENCE_JSON: " + json.dumps(evidence, sort_keys=True)
        return {'phase': 'final_answer', 'event_line': line, 'text': text}

    @staticmethod
    def reviewer(child, start, end):
        return [{'agentThreadId': child, 'kind': 'started', 'event_line': start},
                {'agentThreadId': child, 'kind': 'completed', 'event_line': end}]

    @staticmethod
    def subject():
        files = {name: key * 64 for name, key in (
            ('APPROVED_PLAN.md', 'a'), ('invoice_cli.py', 'b'),
            ('invoice_helpers.py', 'c'), ('tests/test_invoice_cli.py', 'd'),
            ('tests/test_invoice_helpers.py', 'e'))}
        return {'files': files, 'criteria_sha256': 'f' * 64}

    def test_later_rejection_and_other_reviewer_blocker_remain_open(self):
        approved = self.report(
            'Verdict: Approve.\nReviewed the full approved plan, all final source files and diffs and current independent test outputs; no findings remain.', 42)
        rejected = self.report(
            'Verdict: Request changes.\nReviewed the full approved plan and implementation diff and tests; Important: invoice validation remains broken and unresolved.', 55)
        native = {'native_subagent_activity': self.reviewer('r1', 30, 45) + self.reviewer('r1', 50, 60),
                  'child_reports': {'r1': [approved, rejected]}}
        with self.assertRaises(RuntimeError):
            c.review_evidence(native, after_event_line=25)
        native = {'native_subagent_activity': self.reviewer('r1', 30, 45) + self.reviewer('r2', 31, 46),
                  'child_reports': {'r1': [rejected], 'r2': [approved]}}
        with self.assertRaises(RuntimeError):
            c.review_evidence(native, after_event_line=25)

    def test_markdown_important_heading_blocks_approval(self):
        text = ('Verdict: Approve.\nReviewed the full plan and implementation diff and verified tests.\n'
                '#### Important (Should Fix)\n- The input validation still accepts invalid currency.')
        native = {'native_subagent_activity': self.reviewer('r', 30, 45),
                  'child_reports': {'r': [self.report(text, 42)]}}
        with self.assertRaises(RuntimeError):
            c.review_evidence(native, after_event_line=25)

    def test_review_excluding_production_files_is_not_complete(self):
        subject = self.subject()
        record = {'subject': subject, 'covered_files': {'APPROVED_PLAN.md': subject['files']['APPROVED_PLAN.md']},
                  'unresolved_findings': [], 'verified_test_receipts': ['current-suite']}
        text = ('Verdict: Approve.\nScope: Reviewed the plan only; invoice_cli.py and '
                'invoice_helpers.py were not reviewed. Tests were not inspected.')
        native = {'native_subagent_activity': self.reviewer('r', 30, 45),
                  'child_reports': {'r': [self.report(text, 42, evidence=record)]}}
        with self.assertRaises(RuntimeError):
            c.review_evidence(native, after_event_line=25, expected_subject=subject)

    def test_review_snapshot_and_current_test_receipts_required(self):
        subject = self.subject()
        record = {'subject': subject, 'covered_files': subject['files'],
                  'unresolved_findings': [], 'verified_test_receipts': ['current-suite']}
        text = ('Verdict: Approve.\nScope: I reviewed the complete implementation and test diff '
                'against the approved plan and verified the recorded test command, exit and '
                'inventory. Tests were not rerun by me; no blocking findings remain.')
        native = {'native_subagent_activity': self.reviewer('r', 30, 45),
                  'child_reports': {'r': [self.report(text, 42, evidence=record)]}}
        with self.assertRaises(RuntimeError):
            c.review_evidence(native, after_event_line=25, expected_subject=subject)
        native['observed_test_receipts'] = [{
            'id': 'current-suite', 'event_line': 28, 'command': 'python -B -m unittest discover -s tests -v',
            'exit_code': 0, 'tests_run': 8, 'files': subject['files']}]
        verified = c.review_evidence(native, after_event_line=25, expected_subject=subject)
        self.assertTrue(verified['passed'])
        self.assertEqual(verified['subject'], subject)
        self.assertEqual(verified['reviewers'][0]['child_id'], 'r')
        changed = copy.deepcopy(native)
        changed['observed_test_receipts'][0]['files']['invoice_cli.py'] = '0' * 64
        with self.assertRaises(RuntimeError):
            c.review_evidence(changed, after_event_line=25, expected_subject=subject)

    def test_fresh_full_approval_can_supersede_previous_rejection(self):
        subject = self.subject()
        record = {'subject': subject, 'covered_files': subject['files'],
                  'unresolved_findings': [], 'resolved_findings': ['invalid-currency'],
                  'verified_test_receipts': ['current-suite']}
        rejected = self.report(
            'Verdict: Request changes.\nScope: the implementation and tests need a fix. Important: invalid-currency.', 42)
        approval = self.report(
            'Verdict: Approve.\nScope: all implementation and test files were reviewed. '
            'The prior invalid-currency finding is resolved. Verified current test evidence.', 55, evidence=record)
        native = {'native_subagent_activity': self.reviewer('r', 30, 45) + self.reviewer('r', 50, 60),
                  'child_reports': {'r': [rejected, approval]},
                  'observed_test_receipts': [{'id': 'current-suite', 'event_line': 49,
                      'command': 'python -B -m unittest discover -s tests -v', 'exit_code': 0,
                      'tests_run': 8, 'files': subject['files']}]}
        self.assertTrue(c.review_evidence(native, after_event_line=25, expected_subject=subject)['passed'])



class CompleteSkillReadIntegrityRegressionTests(unittest.TestCase):
    """A4: provider metadata must not replace the actual skill body."""

    def fixture(self, root, *, body='abcdef'):
        fable = root / 'fable' / 'SKILL.md'
        fable.parent.mkdir()
        fable.write_text(skill_text('fable5-codex'), encoding='utf-8')
        skill = root / 'superpowers' / 'brainstorming' / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_bytes(body.encode('utf-8'))
        target = {'id': 'catalog:brainstorming', 'plugin_id': 'superpowers@candidate',
                  'path': str(skill), 'sha256': c.digest(skill)}
        source = {'path': str(fable), 'cwd': str(root), 'catalog_sha256': 'f' * 64}
        return skill, target, source

    @staticmethod
    def page(target, source, offset, body, *, total=None, line=20, **changes):
        value = {'skill': {'id': target['id'], 'plugin_id': target['plugin_id'],
                            'name': 'superpowers:brainstorming', 'path': target['path']},
                 'sha256': target['sha256'], 'offset': offset, 'content': body,
                 'total_chars': len(body) if total is None else total, 'partial': False,
                 'warning_count': 0, 'warnings': [],
                 'cwd': source['cwd'], 'catalog_sha256': source['catalog_sha256']}
        value.update(changes)
        return {'type': 'mcpToolCall', 'tool': 'read_skill', 'status': 'completed',
                'event_line': line, 'result': {'structuredContent': value}}

    def read(self, items, target, source):
        return c.observed_skill_reads(items, {'brainstorming': target}, source)

    def test_claimed_hash_cannot_replace_actual_body(self):
        with tempfile.TemporaryDirectory() as td:
            skill, target, source = self.fixture(Path(td))
            # Exact A4 false positive: one warned byte claims the full source hash.
            forged = self.page(target, source, 0, 'x', total=1, partial=True,
                               warning_count=1, warnings=['TRUNCATED'])
            self.assertNotIn('brainstorming', self.read([forged], target, source))
            # No warning but the same claimed hash still does not prove the bytes.
            forged = self.page(target, source, 0, 'xxxxxx', total=6)
            self.assertNotIn('brainstorming', self.read([forged], target, source))

    def test_partial_or_warned_mcp_read_is_not_complete(self):
        with tempfile.TemporaryDirectory() as td:
            _, target, source = self.fixture(Path(td))
            first = self.page(target, source, 0, 'abc', total=6)
            for details in [{'partial': True}, {'warning_count': 1},
                            {'warnings': ['SOURCE_UNVERIFIED']}]:
                with self.subTest(details=details):
                    bad = self.page(target, source, 3, 'def', total=6, **details)
                    self.assertNotIn('brainstorming', self.read([first, bad], target, source))

    def test_foreign_identity_or_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _, target, source = self.fixture(Path(td))
            good = self.page(target, source, 0, 'abcdef', total=6)
            variants = [
                lambda x: x['skill'].update(id='other'),
                lambda x: x['skill'].update(plugin_id='foreign@plugin'),
                lambda x: x.update(cwd='C:/foreign-project'),
                lambda x: x.update(catalog_sha256='0' * 64)]
            for mutate in variants:
                with self.subTest(mutate=variants.index(mutate)):
                    item = copy.deepcopy(good)
                    mutate(item['result']['structuredContent'])
                    self.assertNotIn('brainstorming', self.read([item], target, source))

    def test_conflicting_pages_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _, target, source = self.fixture(Path(td))
            first = self.page(target, source, 0, 'abc', total=6)
            for second in [
                self.page(target, source, 2, 'cdef', total=6),
                self.page(target, source, 3, 'def', total=7),
                self.page(target, source, 3, 'def', total=6, sha256='0' * 64)]:
                with self.subTest(second=second):
                    self.assertNotIn('brainstorming', self.read([first, second], target, source))

    def test_late_warned_page_invalidates_earlier_complete_read(self):
        with tempfile.TemporaryDirectory() as td:
            _, target, source = self.fixture(Path(td))
            complete = self.page(target, source, 0, 'abcdef', total=6)
            warned = self.page(target, source, 0, 'x', total=1, partial=True, warning_count=1, line=21)
            self.assertNotIn('brainstorming', self.read([complete, warned], target, source))

    def test_valid_paginated_bom_crlf_read_is_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, target, source = self.fixture(root)
            skill = Path(target['path'])
            skill.write_bytes(b'\xef\xbb\xbfalpha\r\n' + 'beta\r\n'.encode('utf-8'))
            target['sha256'] = c.digest(skill)
            body = skill.read_bytes().decode('utf-8-sig')
            split = 4
            pages = [self.page(target, source, 0, body[:split], total=len(body)),
                     self.page(target, source, split, body[split:], total=len(body), line=21)]
            self.assertEqual(self.read(pages, target, source)['brainstorming']['method'],
                             'complete_mcp_read')



class TestInventoryFreshnessRegressionTests(unittest.TestCase):
    """A6: a green string is not a test receipt for the final file inventory."""

    def fixture(self, root):
        fixture = root / 'fixture'
        (fixture / 'tests').mkdir(parents=True)
        (fixture / 'tests' / 'test_discounts.py').write_text(
            "import unittest\nfrom discounts import apply_discount\n"
            "class TestDiscount(unittest.TestCase):\n"
            "    def test_discount(self): self.assertEqual(apply_discount(200,10),180)\n")
        (fixture / 'discounts.py').write_text(
            "def apply_discount(amount, percent): return amount - amount * percent / 100\n")
        return fixture

    @staticmethod
    def inventory(fixture):
        return {p.relative_to(fixture).as_posix(): c.digest(p)
                for p in sorted(fixture.rglob('*.py')) if p.is_file()}

    def items(self, fixture, *, green_output='test_discount (test_discounts.TestDiscount.test_discount) ... ok\nRan 1 test in 0.001s\n\nOK\n',
              green_command='python -B -m unittest discover -s tests -v'):
        source = self.inventory(fixture)
        def write(path, line):
            return {'type':'fileChange', 'event_line':line,
                    'changes':[{'path':str(fixture / path)}]}
        red = {'type':'commandExecution', 'event_line':2,
               'command':'python -B -m unittest discover -s tests -v',
               'exitCode':1, 'aggregatedOutput':'test_discount (test_discounts.TestDiscount.test_discount) ... FAIL\nAssertionError: 190 != 180\nRan 1 test in 0.001s\nFAILED',
               'controller_evidence': {'execution_id':'red-2', 'cwd':str(fixture),
                   'event_line':2,'tests_run':1,'test_ids':['test_discounts.TestDiscount.test_discount'],
                   'command':'python -B -m unittest discover -s tests -v','exit_code':1,
                   'source_test_inventory':{'tests/test_discounts.py':source['tests/test_discounts.py']},
                   'inventory':source}}
        green = {'type':'commandExecution', 'event_line':4, 'command':green_command,
                 'exitCode':0, 'aggregatedOutput':green_output,
                 'controller_evidence': {'execution_id':'green-4', 'cwd':str(fixture),
                     'event_line':4,'tests_run':1, 'command':green_command,'exit_code':0,
                     'test_ids':['test_discounts.TestDiscount.test_discount'],
                     'source_test_inventory':{'tests/test_discounts.py':source['tests/test_discounts.py']},
                     'inventory':source}}
        return [write('tests/test_discounts.py',1), red, write('discounts.py',3), green]

    def test_fixture_inventory_detects_additions_removals_and_changes(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            before = c.fixture_inventory(fixture, ['discounts.py', 'tests'])
            self.assertEqual(set(before), {'discounts.py','tests/test_discounts.py'})
            (fixture/'tests'/'test_new_case.py').write_text('def test_new(): pass\n')
            added = c.fixture_inventory(fixture, ['discounts.py', 'tests'])
            self.assertIn('tests/test_new_case.py', added)
            (fixture/'tests'/'test_discounts.py').unlink()
            removed = c.fixture_inventory(fixture, ['discounts.py', 'tests'])
            self.assertNotIn('tests/test_discounts.py', removed)
            self.assertNotEqual(before, added)
            self.assertNotEqual(added, removed)
            (fixture/'discounts.py').write_text('def changed(): pass\n')
            self.assertNotEqual(removed, c.fixture_inventory(fixture,['discounts.py','tests']))
            with self.assertRaises(ValueError):
                c.fixture_inventory(fixture, ['../escape.py'])

    def test_unrelated_suite_cannot_close_green(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            unrelated = fixture / 'unrelated'
            unrelated.mkdir()
            (unrelated/'test_arithmetic.py').write_text(
                'import unittest\nclass Arithmetic(unittest.TestCase):\n'
                '    def test_add(self): self.assertEqual(1+1,2)\n')
            proc = subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',
                                   'unrelated','-v'], cwd=fixture,text=True,capture_output=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn('Ran 1 test',proc.stderr)
            items = self.items(fixture,green_output=proc.stdout + proc.stderr,
                               green_command='python -B -m unittest discover -s unrelated -v')
            with self.assertRaisesRegex(RuntimeError,'GREEN|test|target|evidence|suite'):
                c.tdd_ordering('bug_fix',fixture,items)

    def test_post_green_inventory_change_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            items = self.items(fixture)
            old = c.digest(fixture/'discounts.py')
            replacement = fixture/'replacement.py'
            replacement.write_text('def apply_discount(amount, percent): return 100\n')
            shutil.copyfile(replacement,fixture/'discounts.py')
            self.assertNotEqual(old,c.digest(fixture/'discounts.py'))
            items.append({'type':'commandExecution','event_line':5,'exitCode':0,
                          'command':"shutil.copyfile('replacement.py', 'discounts.py')"})
            with self.assertRaisesRegex(RuntimeError,'GREEN|inventory|changed|stale'):
                c.tdd_ordering('bug_fix',fixture,items)

    def test_tests_only_change_invalidates_green(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            items = self.items(fixture)
            test = fixture/'tests'/'test_discounts.py'
            test.write_text(test.read_text() + '\n# modified after green\n')
            items.append({'type':'commandExecution', 'event_line':5, 'exitCode':0,
                          'command':"Path('tests/test_discounts.py').write_text('revised')"})
            with self.assertRaisesRegex(RuntimeError,'GREEN|inventory|changed|stale'):
                c.tdd_ordering('bug_fix',fixture,items)

    def test_controller_receipts_are_required_for_tdd_proof(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            items = self.items(fixture)
            items[-1].pop('controller_evidence')
            with self.assertRaisesRegex(RuntimeError,'GREEN|receipt|evidence|controller'):
                c.tdd_ordering('bug_fix',fixture,items)

    def test_read_only_hash_after_green_keeps_fresh_proof(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            items = self.items(fixture)
            items.append({'type':'commandExecution','event_line':5,'exitCode':0,
                          'command':"Get-FileHash -LiteralPath 'discounts.py'"})
            self.assertTrue(c.tdd_ordering('bug_fix',fixture,items)['passed'])

    @unittest.skipUnless(shutil.which('pwsh'), 'real PowerShell runner not installed')
    def test_copy_item_after_green_invalidates_evidence_windows(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = self.fixture(Path(td))
            items = self.items(fixture)
            (fixture/'replacement.py').write_text(
                'def apply_discount(amount,percent): return 42\n')
            result = subprocess.run(['pwsh','-NoProfile','-Command',
                "Copy-Item -LiteralPath 'replacement.py' -Destination 'discounts.py' -Force"],
                cwd=fixture, capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            items.append({'type':'commandExecution','event_line':5,'exitCode':0,
                          'command':"Copy-Item -LiteralPath 'replacement.py' -Destination 'discounts.py' -Force"})
            with self.assertRaisesRegex(RuntimeError,'GREEN|inventory|changed|stale'):
                c.tdd_ordering('bug_fix',fixture,items)


class ImmutableBaselineAcceptanceTests(unittest.TestCase):
    """Run immutable controller-owned tests against candidate implementations."""

    @staticmethod
    def local_fixture_python(arguments, cwd, codex_home, timeout=60):
        process = subprocess.run([sys.executable, *arguments], cwd=cwd,
                                 capture_output=True, text=True, timeout=timeout)
        return {'exit_code': process.returncode, 'stdout': process.stdout,
                'stderr': process.stderr}

    def make_fixture(self, root, *, broken=False):
        fixture = root / 'fixtures' / 'bug_fix'
        shutil.copytree(c.RESOURCES / 'fixtures' / 'bug_fix', fixture)
        c._prepare_baseline_snapshots(root)
        if broken:
            (fixture / 'discounts.py').write_text(
                'def apply_discount(amount, percent):\n'
                '    if percent < 0 or percent > 100:\n'
                '        raise ValueError("percent must be between 0 and 100")\n'
                '    if percent == 100:\n'
                '        return 0.0\n'
                '    return amount - percent * 2 if amount == 200 else amount\n',
                encoding='utf-8')
            (fixture / 'tests' / 'test_discounts.py').write_text(
                'import unittest\nfrom discounts import apply_discount\n'
                'class WeakenedTests(unittest.TestCase):\n'
                '    def test_only_sampled_amount(self):\n'
                '        self.assertEqual(apply_discount(200, 10), 180)\n',
                encoding='utf-8')
        else:
            (fixture / 'discounts.py').write_text(
                'def apply_discount(amount, percent):\n'
                '    if not 0 <= percent <= 100:\n'
                '        raise ValueError("invalid percentage")\n'
                '    return amount * (1 - percent / 100)\n',
                encoding='utf-8')
        return fixture

    def test_weakened_author_suite_cannot_hide_baseline_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = self.make_fixture(root, broken=True)
            with patch.object(c, '_fixture_python', side_effect=self.local_fixture_python):
                weakened = c._fixture_python(['-m', 'unittest', 'discover',
                                               '-s', 'tests', '-v'], fixture, root)
                self.assertEqual(weakened['exit_code'], 0, weakened['stderr'])
                baseline = c.run_baseline_suite('bug_fix', fixture, root)
                self.assertNotEqual(baseline['exit_code'], 0)
                self.assertIn('100 != 90', baseline['stderr'])
                loaded = {'fable5-codex': {}, **{name: {} for name in c.REQUIRED_BY_CASE['bug_fix']}}
                def fake_git(arguments, cwd, home):
                    if arguments[:2] == ['worktree', 'list']:
                        return {'exit_code': 0, 'stdout': 'worktree ' + str(fixture) + '\n'}
                    return {'exit_code': 0, 'stdout': '', 'stderr': ''}
                with patch.object(c, 'native_items', return_value=[]), \
                     patch.object(c, 'observed_skill_reads', return_value=loaded), \
                     patch.object(c, 'tdd_ordering', return_value={'passed': True, 'tasks': []}), \
                     patch.object(c, '_fixture_git', side_effect=fake_git):
                    with self.assertRaisesRegex(RuntimeError, 'baseline'):
                        c.assess_case('bug_fix', fixture,
                                      {'thread_id': 'root'}, root, {}, {},
                                      codex_home=root)

    def test_correct_discount_passes_baseline_and_new_tests(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = self.make_fixture(root)
            with patch.object(c, '_fixture_python', side_effect=self.local_fixture_python):
                result = c.run_baseline_suite('bug_fix', fixture, root)
                self.assertEqual(result['exit_code'], 0, result['stderr'])
                self.assertEqual(result['tests_run'], 5)
                self.assertEqual(len(result['baseline_sha256']), 64)
                new_tests = c._fixture_python(
                    ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], fixture, root)
                self.assertEqual(new_tests['exit_code'], 0, new_tests['stderr'])

    def test_changed_baseline_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = self.make_fixture(root)
            trusted = root / 'trusted-baseline' / 'bug_fix' / 'tests' / 'test_discounts.py'
            trusted.write_text(trusted.read_text() + '\n# unauthorized edit\n',
                               encoding='utf-8')
            with patch.object(c, '_fixture_python', side_effect=self.local_fixture_python):
                with self.assertRaisesRegex(RuntimeError, 'baseline'):
                    c.run_baseline_suite('bug_fix', fixture, root)

class HelperPackageHealthTests(unittest.TestCase):
    def fixture(self, root):
        home=root/'home';home.mkdir();(home/'AGENTS.md').write_text('policy')
        cache=home/'plugins/cache/fable-superpowers/superpowers/7.0.2';cache.mkdir(parents=True)
        (cache/'.codex-plugin').mkdir();(cache/'.codex-plugin/plugin.json').write_text(json.dumps({'name':'superpowers','version':'7.0.2','skills':'./skills'}))
        native=[];expected={};skills=[]
        for name in sorted(c.CRITICAL):
            skill=cache/'skills'/name/'SKILL.md';skill.parent.mkdir(parents=True);skill.write_text(skill_text(name))
            expected[name]={'path':str(skill),'sha256':c.digest(skill)}
            native.append({'pluginId':c.PLUGIN_ID,'name':'superpowers:'+name,'path':str(skill)})
            skills.append({'id':name,'name':name,'plugin_id':c.PLUGIN_ID,'path':str(skill)})
        froot=root/'fable';fpath=froot/'.agents/skills/fable5-codex/SKILL.md';fpath.parent.mkdir(parents=True);fpath.write_text(skill_text('fable5-codex'))
        (froot/'.mcp.json').write_text(json.dumps({'mcpServers':{'fable5_skills':{'command':'node','args':[]}}}))
        native.append({'pluginId':'fable5-codex@fable5','name':'fable5-codex','path':str(fpath)})
        inventory={p.relative_to(cache).as_posix():c.digest(p) for p in cache.rglob('*') if p.is_file()}
        return home, {'skills':native}, expected, skills, fpath, inventory

    def fake_client(self, skills, expected, mode='candidate', search_change=None, read_change=None):
        meta=({'catalog_source':'configured_cache','native_context_verified':False,'partial':True,'warning_count':1,
               'source_warning_count':0,'warnings':['NATIVE_CONTEXT_UNVERIFIED']} if mode=='candidate' else {'partial':False,'warning_count':0})
        items=copy.deepcopy(skills)
        if mode=='candidate':
            for item in items:item['enabled_in_native_context']=None
        search={**copy.deepcopy(meta),'skills':items,'total':len(items),'next_offset':None,'catalog_sha256':'a'*64}
        if search_change:search_change(search)
        selected=next(item for item in items if item['name']=='executing-plans')
        content=Path(expected['executing-plans']['path']).read_bytes().decode('utf-8')
        class Client:
            def __init__(self,*args):pass
            def send(self,*args):pass
            def close(self):pass
            def rpc(self,method,params):
                if method=='initialize':return {}
                if method=='tools/list':return {'tools':[{'name':'search_skills'},{'name':'read_skill'}]}
                if params['name']=='search_skills':return {'structuredContent':copy.deepcopy(search)}
                offset=params['arguments']['offset']; chunk=content[offset:offset+8]
                page={**copy.deepcopy(meta),'skill':copy.deepcopy(selected),'sha256':expected['executing-plans']['sha256'],
                      'offset':offset,'content':chunk,'total_chars':len(content),'next_offset':offset+len(chunk) if offset+len(chunk)<len(content) else None}
                if read_change:read_change(page,offset)
                return {'structuredContent':page}
        return Client

    def test_installed_health_accepts_candidate_context_warning_and_legacy_rollback(self):
        for mode in ('candidate','legacy'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as td:
                root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
                with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',self.fake_client(skills,expected,mode)):
                    result=c.installed_health(root/'probe','7.0.2',inventory,home)
                self.assertTrue(result['passed'],result['errors'])
                receipt=result['fable_helper'];self.assertEqual(receipt['scope'],'package_health')
                self.assertEqual(receipt['partial'],mode=='candidate')
                self.assertEqual(receipt['catalog_source'],'configured_cache' if mode=='candidate' else None)
                self.assertEqual(receipt['native_context_verified'],False if mode=='candidate' else None)

    def test_crlf_fixture_preserves_bytes_used_by_native_digest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
            file=Path(expected['executing-plans']['path'])
            file.write_bytes(file.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            expected['executing-plans']['sha256']=c.digest(file)
            inventory['skills/executing-plans/SKILL.md']=c.digest(file)
            with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',self.fake_client(skills,expected)):
                result=c.installed_health(root/'probe','7.0.2',inventory,home)
            self.assertTrue(result['passed'],result['errors'])

    def test_read_with_utf8_bom_matches_verified_native_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
            file=Path(expected['executing-plans']['path'])
            file.write_bytes(b'\xef\xbb\xbf'+file.read_bytes())
            expected['executing-plans']['sha256']=c.digest(file)
            inventory['skills/executing-plans/SKILL.md']=c.digest(file)
            base=self.fake_client(skills,expected)
            class BomClient(base):
                def rpc(self,method,params):
                    result=super().rpc(method,params)
                    if method=='tools/call' and params['name']=='read_skill':
                        data=result['structuredContent']; text=file.read_bytes().decode('utf-8-sig'); offset=params['arguments']['offset']; chunk=text[offset:offset+8]
                        data.update(content=chunk,total_chars=len(text),next_offset=offset+len(chunk) if offset+len(chunk)<len(text) else None)
                    return result
            with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',BomClient):
                result=c.installed_health(root/'probe','7.0.2',inventory,home)
            self.assertTrue(result['passed'],result['errors'])

    def test_package_health_browses_all_pages_for_short_skill_names(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
            base=self.fake_client(skills,expected)
            class PagedClient(base):
                def rpc(self,method,params):
                    result=super().rpc(method,params)
                    if method=='tools/call' and params['name']=='search_skills':
                        query=params['arguments']['query']; offset=params['arguments'].get('offset',0)
                        data=result['structuredContent']; data['catalog_sha256']='a'*64
                        if query:
                            data['skills']=[x for x in data['skills'] if query in x['name']]
                            data['total']=len(data['skills']); data['next_offset']=None
                        elif offset==0:
                            data['skills']=[{'name':'other','plugin_id':'other@other'} for _ in range(46)]+data['skills'][:4]; data['next_offset']=50; data['total']=55
                        else:
                            data['skills']=data['skills'][4:]; data['next_offset']=None; data['total']=55
                    return result
            with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',PagedClient):
                result=c.installed_health(root/'probe','7.0.2',inventory,home)
            self.assertTrue(result['passed'],result['errors'])

    def test_package_health_rejects_changed_or_incomplete_search_pages(self):
        for change in ('digest','source','total','missing','cycle'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
                root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
                base=self.fake_client(skills,expected)
                class PagedClient(base):
                    def rpc(self,method,params):
                        result=super().rpc(method,params)
                        if method=='tools/call' and params['name']=='search_skills':
                            data=result['structuredContent'];offset=params['arguments'].get('offset',0)
                            data['total']=55
                            if offset==0:
                                data['skills']=[{'name':'other','plugin_id':'other@other'} for _ in range(46)]+data['skills'][:4];data['next_offset']=50
                            else:
                                data['skills']=data['skills'][4:];data['next_offset']=None
                                if change=='digest':data['catalog_sha256']='b'*64
                                if change=='source':data['native_context_verified']=True
                                if change=='total':data['total']=56
                                if change=='missing':data['skills'].pop()
                                if change=='cycle':data['next_offset']=50
                        return result
                with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',PagedClient):
                    result=c.installed_health(root/'probe','7.0.2',inventory,home)
                self.assertFalse(result['passed'],change)

    def test_strict_probe_rejects_candidate_context_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
            with patch.object(c,'McpClient',self.fake_client(skills,expected)):
                with self.assertRaises(RuntimeError):c._helper_probe(root,{'path':str(fpath)},expected,home)

    def test_package_health_rejects_invalid_search_and_read_evidence(self):
        changes=[
          ('search extra warning',lambda p:p.update(warnings=['NATIVE_CONTEXT_UNVERIFIED','OTHER']),None),
          ('search wrong source',lambda p:p.update(catalog_source='native_subprocess'),None),
          ('search missing warning',lambda p:p.pop('warnings'),None),
          ('search skill enabled',lambda p:p['skills'][0].update(enabled_in_native_context=True),None),
          ('duplicate skill',lambda p:p['skills'].append(copy.deepcopy(p['skills'][0])),None),
          ('read warning',None,lambda p,o:p.update(source_warning_count=1) if o else None),
          ('read source',None,lambda p,o:p.update(catalog_source='unknown') if o else None),
          ('mixed legacy read',None,lambda p,o:([p.pop(k,None) for k in ('catalog_source','native_context_verified','source_warning_count','warnings')],p.update(partial=False,warning_count=0),p['skill'].pop('enabled_in_native_context',None)) if o else None),
          ('read identity',None,lambda p,o:p['skill'].update(id='wrong') if o else None),
          ('read path',None,lambda p,o:p['skill'].update(path='/wrong/SKILL.md') if o else None),
          ('read digest',None,lambda p,o:p.update(sha256='0'*64) if o else None),
          ('read offset',None,lambda p,o:p.update(offset=0) if o else None),
          ('read next offset',None,lambda p,o:p.update(next_offset=o) if o else None),
          ('read total',None,lambda p,o:p.update(total_chars=p['total_chars']+1) if o else None),
          ('read content',None,lambda p,o:p.update(content='XXXXXXXX') if o else None),
        ]
        for label,search_change,read_change in changes:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as td:
                root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
                with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',self.fake_client(skills,expected,search_change=search_change,read_change=read_change)):
                    result=c.installed_health(root/'probe','7.0.2',inventory,home)
                self.assertFalse(result['passed'],label)

    def test_installed_health_over_real_mcp_stdio_transport(self):
        import sys
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
            froot=fpath.parents[3];script=froot/'server.py'
            for skill in skills: skill['enabled_in_native_context']=None
            content=Path(expected['executing-plans']['path']).read_bytes().decode('utf-8')
            payload={'skills':skills,'content':content,'sha256':expected['executing-plans']['sha256']}
            script.write_text("""import json, sys
payload = json.loads(%r)
meta = {'catalog_source':'configured_cache','native_context_verified':False,'partial':True,'warning_count':1,'source_warning_count':0,'warnings':['NATIVE_CONTEXT_UNVERIFIED']}
for line in sys.stdin:
    request=json.loads(line)
    if 'id' not in request: continue
    method=request['method']; params=request['params']
    if method=='initialize': result={}
    elif method=='tools/list': result={'tools':[{'name':'search_skills'},{'name':'read_skill'}]}
    elif params['name']=='search_skills': result={'structuredContent':{**meta,'skills':payload['skills'],'total':len(payload['skills']),'next_offset':None,'catalog_sha256':'a'*64}}
    else:
        offset=params['arguments']['offset']; text=payload['content']; chunk=text[offset:offset+8]
        skill=next(x for x in payload['skills'] if x['name']=='executing-plans')
        result={'structuredContent':{**meta,'skill':skill,'offset':offset,'content':chunk,'sha256':payload['sha256'],'total_chars':len(text),'next_offset':offset+len(chunk) if offset+len(chunk)<len(text) else None}}
    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
""" % json.dumps(payload))
            (froot/'.mcp.json').write_text(json.dumps({'mcpServers':{'fable5_skills':{'command':sys.executable,'args':[str(script)]}}}))
            class TestClient(c.McpClient):
                def close(self):
                    super().close()
                    self.process.stdout.close()
            with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',TestClient):
                result=c.installed_health(root/'probe','7.0.2',inventory,home)
            self.assertTrue(result['passed'],result['errors'])
            self.assertGreater(result['fable_helper']['pages'],1)
            self.assertTrue(result['fable_helper']['partial'])

    def test_legacy_payload_with_provenance_is_not_a_rollback_exception(self):
        for field, value in [('catalog_source', None), ('warnings', []), ('native_context_verified', False), ('source_warning_count', 0)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as td:
                root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
                def change(payload): payload[field]=value
                with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient',self.fake_client(skills,expected,'legacy',search_change=change)):
                    result=c.installed_health(root/'probe','7.0.2',inventory,home)
                self.assertFalse(result['passed'])

    def test_inventory_failure_stops_before_helper_probe(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);home,catalog,expected,skills,fpath,inventory=self.fixture(root)
            inventory['skills/executing-plans/SKILL.md']='0'*64
            with patch.object(c,'_native_catalog',return_value=catalog),patch.object(c,'McpClient') as client:
                result=c.installed_health(root/'probe','7.0.2',inventory,home)
            self.assertFalse(result['passed'])
            client.assert_not_called()

if __name__=='__main__':
    unittest.main()
