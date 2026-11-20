"""D1–D12 owner-decision receipt contracts; OFFLINE fixtures, never live agents."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
EVAL_SCRIPT = ROOT/'codex-profile/fable-superpowers/scripts/updater/resources/appserver_eval.py'
SPEC = importlib.util.spec_from_file_location('owner_decision_collector', EVAL_SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
MANIFESTS = ROOT/'codex-profile/tests/fixtures/agent_acceptance/owner-decisions'


def digest(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()


class OwnerDecisionAcceptanceTests(unittest.TestCase):
    def fixture(self, case, root):
        path = MANIFESTS/(case.lower()+'.json')
        raw = path.read_bytes()
        manifest = json.loads(raw)
        self.assertEqual(manifest['id'],case)
        artifacts = root/'artifacts'
        artifacts.mkdir()
        for relative in manifest['allowed_paths']:
            destination=artifacts/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(
                f'# {case} offline test artifact\n'
                f'Contract: {manifest["prompt"]}\n'
                f'Owner turns: {json.dumps(manifest["turns"],ensure_ascii=False)}\n',
                encoding='utf-8')
        inventory = {relative:digest((artifacts/relative).read_bytes())
                     for relative in manifest['allowed_paths']}
        subject = digest(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode())
        evidence = {
            key: {'status': status, 'subject_sha256': subject,
                  'evidence': f'Synthetic receipt {case}:{key}: {status}'}
            for key,status in manifest['criteria'].items()}
        if case == 'D9':
            for key in evidence:
                evidence[key]['subject_sha256'] = '0'*64
        record = {
            'id':case, 'review_mode':'offline_fixture',
            'manifest_sha256':digest(raw), 'artifact_inventory':inventory,
            'artifact_subject_sha256':subject, 'criterion_evidence':evidence,
            'decisions':copy.deepcopy(manifest['preserve']),
            'cancelled':list(manifest['cancelled']),
            'decision_facts':copy.deepcopy(manifest['locked_facts']),
            'unresolved_criteria':[key for key,status in manifest['criteria'].items()
                                  if status not in ('satisfied','cancelled')],
            'review_history':copy.deepcopy(manifest['review_history']),
            'declared_ready':manifest['expected_status']=='passed'
        }
        return manifest,record,artifacts

    def check(self,case,mutate=None):
        with tempfile.TemporaryDirectory() as td:
            manifest,record,artifacts=self.fixture(case,Path(td))
            accepted=runner.evaluate_owner_decision_fixture(
                manifest,record,artifacts,allow_offline_fixture=True)
            self.assertEqual(accepted['status'],manifest['expected_status'])
            self.assertEqual(accepted['ready'],manifest['expected_status']=='passed')
            self.assertEqual(accepted['evidence_tier'],'offline_fixture')
            if mutate:
                bad=copy.deepcopy(record)
                mutate(bad,artifacts)
                with self.assertRaises((ValueError,RuntimeError)):
                    runner.evaluate_owner_decision_fixture(
                        manifest,bad,artifacts,allow_offline_fixture=True)

    def test_D1_exact_artifact_scope(self):
        def invalid(record,root):
            target=root/'src'/'unexpected.md'
            target.parent.mkdir()
            target.write_text('Unrequested production change\n')
        self.check('D1',invalid)

    def test_D2_approved_spec_no_repeat_confirmation(self):
        self.check('D2',lambda record,_:
                   record['decision_facts'].update(repeat_question_count=1))

    def test_D3_cancel_one_keep_two(self):
        self.check('D3',lambda record,_:
                   record['decisions'].update(B='silently restored'))

    def test_D4_change_format_keep_old_record_compatibility(self):
        self.check('D4',lambda record,_:
                   record['decision_facts'].update(old_record_tests_passed=False))

    def test_D5_safety_without_hidden_quota_or_ttl(self):
        self.check('D5',lambda record,_:
                   record['decision_facts'].update(ttl_seconds=30))

    def test_D6_critique_infeasible_fixed_ttl(self):
        self.check('D6',lambda record,_:
                   record['decisions'].update(ttl_seconds=5))

    def test_D7_preserve_odd_legacy_api_field(self):
        self.check('D7',lambda record,_:
                   record['decisions'].update(legacy_field='voucherId'))

    def test_D8_whole_auth_flow_overrides_unit_green(self):
        self.check('D8',lambda record,_:
                   record.update(declared_ready=True))

    def test_D9_reopen_stale_hash_bound_tests_and_review(self):
        self.check('D9',lambda record,_:
                   record['criterion_evidence']['current_review'].update(
                       status='satisfied',subject_sha256=record['artifact_subject_sha256']))

    def test_D10_later_pr_permission_not_target_selection(self):
        self.check('D10',lambda record,_:
                   record['decision_facts'].update(target='production'))

    def test_D11_latest_request_changes_blocks_earlier_approve(self):
        self.check('D11',lambda record,_:
                   record.update(declared_ready=True))

    def test_D12_missing_required_evidence_not_ready(self):
        self.check('D12',lambda record,_:
                   record.update(declared_ready=True))
        with tempfile.TemporaryDirectory() as td:
            manifest,record,root=self.fixture('D12',Path(td))
            with self.assertRaisesRegex(RuntimeError,'independent_live'):
                runner.evaluate_owner_decision_fixture(manifest,record,root)


if __name__ == '__main__':
    unittest.main()
