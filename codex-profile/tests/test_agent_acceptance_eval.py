"""Behavioral checks for the observation collector and its acceptance boundary."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'codex-profile/fable-superpowers/scripts/updater/resources/appserver_eval.py'
SPEC = importlib.util.spec_from_file_location('acceptance_runner', SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RedactionTests(unittest.TestCase):
    def test_tokens_in_nested_json_tool_output_are_removed(self):
        marker = 'synthetic-sensitive-value'
        value = {'output': json.dumps({'access_token': marker, 'status': 'ready'})}
        cleaned = runner.safe_value(value)
        self.assertNotIn(marker, json.dumps(cleaned))
        self.assertIn('ready', json.dumps(cleaned))

    def test_text_headers_and_signed_urls_are_removed(self):
        cleaned = runner.safe_value('Authorization: Bearer synthetic-credential\nhttps://example.test/a?X-Amz-Signature=private-signature&ok=1')
        self.assertNotIn('synthetic-credential', cleaned)
        self.assertNotIn('private-signature', cleaned)

    def test_reasoning_and_encrypted_fields_remain_excluded(self):
        cleaned = runner.safe_value({'items': [{'type': 'reasoning', 'text': 'private'}, {'type': 'agentMessage', 'text': 'visible'}], 'encrypted_content': 'secret'})
        self.assertEqual(cleaned, {'items': [{'type': 'agentMessage', 'text': 'visible'}]})

    def test_common_header_and_key_spellings_are_redacted_in_all_forms(self):
        marker = 'SYNTHETIC_PRIVATE_MARKER'
        for name in ['X-Control-Secret', 'Cookie', 'Set-Cookie', 'api-key', 'api_key',
                     'client-secret', 'client_secret', 'clientSecret', 'accessToken']:
            for value in [{name: marker}, name + ': ' + marker,
                          name + '=' + marker, "prefix '" + name + "': '" + marker + "'"]:
                with self.subTest(value=value):
                    self.assertNotIn(marker, json.dumps(runner.safe_value(value)))


class ExecutableTests(unittest.TestCase):
    def test_explicit_executable_works_without_path(self):
        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / 'codex.exe'
            executable.write_bytes(b'fixture')
            with patch.object(runner.shutil, 'which', return_value=None):
                self.assertEqual(runner.resolve_codex(str(executable)), str(executable.resolve()))

    def test_invalid_explicit_executable_does_not_fall_back(self):
        with self.assertRaises(FileNotFoundError):
            runner.resolve_codex('missing-explicit-codex.exe')


class AcceptanceTests(unittest.TestCase):
    def observation(self):
        return {'status': 'completed', 'thread_id': 'parent', 'cwd': str(ROOT),
                'config_hashes_before': {'config': 'same'}, 'config_hashes_after': {'config': 'same'},
                'candidate_before': {'skill': 'same'}, 'candidate_after': {'skill': 'same'},
                'watched_before': {'fixture': 'same'}, 'watched_after': {'fixture': 'same'},
                'observation_errors': [], 'unexpected_client_requests': [], 'child_reports': {}}

    def test_completed_without_acceptance_criteria_is_not_success(self):
        result = runner.assess_observation(self.observation(), {}, [])
        self.assertEqual(result['status'], 'incomplete')

    def test_missing_semantic_review_is_not_success(self):
        result = runner.assess_observation(self.observation(), {'mechanical': ['completed'], 'semantic': ['correct_conclusion']}, [])
        self.assertEqual(result['status'], 'incomplete')

    def test_changed_candidate_invalidates_prior_success(self):
        native = self.observation()
        native['candidate_after']['skill'] = 'changed'
        result = runner.assess_observation(native, {'mechanical': ['completed']}, [])
        self.assertEqual(result['status'], 'failed')

    def test_missing_child_result_is_not_accepted(self):
        result = runner.assess_observation(self.observation(), {'mechanical': ['delegation']}, [])
        self.assertNotEqual(result['status'], 'passed')

    def test_write_attempt_fails_read_only_even_when_unchanged(self):
        events = [{'method': 'item/completed', 'params': {'threadId': 'parent', 'item': {'type': 'fileChange', 'status': 'failed', 'changes': [{'path': 'fixture'}]}}}]
        result = runner.assess_observation(self.observation(), {'mechanical': ['read_only']}, events)
        self.assertEqual(result['status'], 'failed')

    def test_review_can_resolve_unknown_tool_effects_but_not_a_write(self):
        events = [{'method': 'item/completed', 'params': {'threadId': 'parent', 'item': {
            'type': 'commandExecution', 'command': 'read-only fixture command', 'exitCode': 0}}}]
        semantic = {'read_only': {'status': 'satisfied', 'evidence': 'Reviewer checked exact command, output, and fixture hashes'}}
        result = runner.assess_observation(self.observation(), {'mechanical': ['read_only']}, events, semantic)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['criteria']['read_only']['mechanical_status'], 'not_checked')
        events[0]['params']['item']['type'] = 'fileChange'
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['read_only']}, events, semantic)['status'], 'failed')

    def test_unknown_mechanical_criterion_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.assess_observation(self.observation(), {'mechanical': ['anything']}, [])

    def test_wrong_session_activation_cannot_be_accepted(self):
        events = [{'method': 'item/completed', 'params': {'threadId': 'other', 'item': {'type': 'mcpToolCall', 'tool': 'fable_status', 'arguments': {'cwd': str(ROOT)}, 'result': {'structuredContent': {'status': 'ready'}}}}}]
        result = runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)
        self.assertNotEqual(result['status'], 'passed')

    def test_semantic_failure_rejects_a_completed_turn(self):
        result = runner.assess_observation(self.observation(), {'mechanical': ['completed'], 'semantic': ['correct_conclusion']}, [], {'correct_conclusion': {'status': 'violated', 'evidence': 'final answer contradicts fixture'}})
        self.assertEqual(result['status'], 'failed')

    def test_required_not_applicable_does_not_pass(self):
        result = runner.assess_observation(self.observation(), {'semantic': ['target']}, [], {'target': {'status': 'not_applicable', 'evidence': 'not evaluated'}})
        self.assertEqual(result['status'], 'incomplete')

    def test_semantics_cannot_replace_integrity_failures(self):
        for name in ['candidate_unchanged', 'profile_unchanged', 'observation_complete', 'current_evidence']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                runner.assess_observation(self.observation(), {'semantic': [name]}, [],
                                         {name: {'status': 'satisfied', 'evidence': 'reviewer claim'}})

    def test_missing_cwd_and_identity_are_not_activation(self):
        events = self.activation_events()
        for event in events:
            item = event['params']['item']
            if item.get('type') != 'mcpToolCall': continue
            item['arguments'].pop('cwd')
            value = item['result']['structuredContent']
            value.pop('cwd', None)
            for key in ('id', 'name', 'path', 'plugin_id'):
                if 'skill' in value: value['skill'].pop(key, None)
                for found in value.get('skills', []):
                    if isinstance(found, dict): found.pop(key, None)
                if isinstance(value.get('skills'), dict):
                    for found in value['skills'].values(): found.pop(key, None)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_missing_planned_turn_rejects_last_completed_turn(self):
        native = self.observation()
        native.update(planned_turn_count=2, turns=[{'id': 'first', 'status': 'completed'}])
        self.assertEqual(runner.assess_observation(native, {'mechanical': ['completed']}, [])['status'], 'failed')

    def activation_events(self):
        selected, events = {}, []
        def event(tool, value):
            return {'method': 'item/completed', 'params': {'threadId': 'parent', 'item': {
                'type': 'mcpToolCall', 'server': 'fable5_skills', 'tool': tool,
                'status': 'completed', 'arguments': {'cwd': str(ROOT)},
                'result': {'structuredContent': {'partial': False, 'warning_count': 0, **value}}}}}
        for name in ['fable', 'using_superpowers', 'writing_plans']:
            content = 'Complete fixture skill ' + name
            skill = {'id': name, 'name': name, 'path': '/skills/' + name,
                     'plugin_id': 'fixture', 'sha256': hashlib.sha256(content.encode()).hexdigest()}
            selected[name] = skill
            events.append(event('search_skills', {'skills': [skill], 'catalog_sha256': 'a' * 64}))
            events.append(event('read_skill', {'skill': skill, 'sha256': skill['sha256'], 'offset': 0,
                                               'content': content, 'total_chars': len(content), 'next_offset': None}))
        events.append(event('fable_status', {'status': 'ready', 'cwd': str(ROOT), 'catalog_sha256': 'a' * 64, 'skills': selected}))
        events.append({'method': 'item/started', 'params': {'threadId': 'parent', 'item': {
            'type': 'subAgentActivity', 'kind': 'started', 'agentThreadId': 'child'}}})
        return events

    def test_complete_activation_order_requires_real_matching_receipts(self):
        result = runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, self.activation_events())
        self.assertEqual(result['status'], 'passed')

    def test_blocked_status_invalidates_prior_activation(self):
        import copy
        events = self.activation_events()
        blocked = copy.deepcopy(events[-2])
        blocked['params']['item']['result']['structuredContent']['status'] = 'blocked'
        events.insert(-1, blocked)
        result = runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)
        self.assertEqual(result['status'], 'failed')
        self.assertNotEqual(result['criteria']['activation_before_delegation']['status'], 'satisfied')

    def test_later_invalid_receipts_invalidate_activation(self):
        import copy
        for mutation in ['partial', 'warning', 'error', 'failed', 'cwd', 'identity']:
            with self.subTest(mutation=mutation):
                events = self.activation_events()
                receipt = copy.deepcopy(events[-2])
                item = receipt['params']['item']
                value = item['result']['structuredContent']
                if mutation == 'partial': value['partial'] = True
                elif mutation == 'warning': value['warning_count'] = 1
                elif mutation == 'error': item['result']['isError'] = True
                elif mutation == 'failed': item['status'] = 'failed'
                elif mutation == 'cwd': value['cwd'] = str(ROOT.parent)
                else: value['skills']['fable']['plugin_id'] = 'different'
                events.insert(-1, receipt)
                result = runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)
                self.assertEqual(result['status'], 'failed')

    def test_later_conflicting_read_invalidates_activation(self):
        import copy
        events = self.activation_events()
        receipt = copy.deepcopy(events[1])
        receipt['params']['item']['result']['structuredContent']['skill']['plugin_id'] = 'different'
        events.insert(-1, receipt)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_changed_content_with_same_digest_invalidates_activation(self):
        import copy
        events = self.activation_events()
        read = copy.deepcopy(events[1])
        value = read['params']['item']['result']['structuredContent']
        value['content'] = 'X' + value['content'][1:]
        events.insert(-1, read)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_compatible_discovery_after_ready_preserves_activation(self):
        import copy
        events = self.activation_events()
        events.insert(-1, copy.deepcopy(events[0]))
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'passed')

    def test_unrelated_skill_read_after_ready_preserves_activation(self):
        import copy
        events = self.activation_events()
        read = copy.deepcopy(events[1])
        value = read['params']['item']['result']['structuredContent']
        content = 'unrelated complete skill'
        digest = hashlib.sha256(content.encode()).hexdigest()
        value.update(skill={'id': 'subagent-driven-development', 'name': 'subagent-driven-development',
                            'path': '/skills/subagent-driven-development', 'plugin_id': 'fixture', 'sha256': digest},
                     sha256=digest, content=content, total_chars=len(content))
        events.insert(-1, read)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'passed')

    def test_catalog_change_during_collection_invalidates_old_chain(self):
        import copy
        events = self.activation_events()
        changed = copy.deepcopy(events[0])
        changed['params']['item']['result']['structuredContent']['catalog_sha256'] = 'b' * 64
        events.insert(-2, changed)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_complete_fresh_chain_after_catalog_change_is_accepted(self):
        import copy
        events = self.activation_events()
        changed = copy.deepcopy(events[0])
        changed['params']['item']['result']['structuredContent']['catalog_sha256'] = 'b' * 64
        events = events[:-2] + [changed] + self.activation_events()
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'passed')

    def test_conflicting_discovery_during_collection_invalidates_old_chain(self):
        import copy
        events = self.activation_events()
        changed = copy.deepcopy(events[0])
        changed['params']['item']['result']['structuredContent']['skills'][0]['plugin_id'] = 'different'
        events.insert(-2, changed)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_started_tool_event_does_not_invalidate_activation(self):
        import copy
        events = self.activation_events()
        started = copy.deepcopy(events[-2])
        started['method'] = 'item/started'
        started['params']['item'].pop('result')
        started['params']['item']['status'] = 'inProgress'
        events.insert(-1, started)
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'passed')

    def test_invalidation_between_delegations_fails(self):
        import copy
        events = self.activation_events()
        blocked = copy.deepcopy(events[-2])
        blocked['params']['item']['result']['structuredContent']['status'] = 'blocked'
        events.extend([blocked, copy.deepcopy(events[-1])])
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_fresh_complete_activation_after_blocked_is_accepted(self):
        import copy
        events = self.activation_events()
        blocked = copy.deepcopy(events[-2])
        blocked['params']['item']['result']['structuredContent']['status'] = 'blocked'
        events = events[:-1] + [blocked] + self.activation_events()
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'passed')

    def test_other_cwd_or_thread_does_not_invalidate_activation(self):
        import copy
        for context in ['cwd', 'thread']:
            with self.subTest(context=context):
                events = self.activation_events()
                blocked = copy.deepcopy(events[-2])
                blocked['params']['item']['result']['structuredContent']['status'] = 'blocked'
                if context == 'cwd': blocked['params']['item']['arguments']['cwd'] = str(ROOT.parent)
                else: blocked['params']['threadId'] = 'other'
                events.insert(-1, blocked)
                self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'passed')

    def test_early_delegation_cannot_be_fixed_by_later_activation(self):
        events = self.activation_events()
        events.insert(0, events.pop())
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_early_raw_spawn_alias_cannot_hide_behind_later_activity(self):
        events = self.activation_events()
        events.insert(0, {'method': 'rawResponseItem/completed', 'params': {'threadId': 'parent',
            'item': {'type': 'function_call', 'name': 'spawnAgent'}}})
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_conflicting_discovery_digest_is_not_ignored_when_supplied(self):
        import copy
        events = self.activation_events()
        events[0] = copy.deepcopy(events[0])
        events[0]['params']['item']['result']['structuredContent']['skills'][0]['sha256'] = 'b' * 64
        self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')

    def test_wrong_cwd_and_failed_or_incomplete_reads_are_not_activation(self):
        import copy
        for mutation in ['cwd', 'failure', 'partial', 'digest', 'missing_page']:
            with self.subTest(mutation=mutation):
                events = copy.deepcopy(self.activation_events())
                item = events[1]['params']['item']
                value = item['result']['structuredContent']
                if mutation == 'cwd': item['arguments']['cwd'] = str(ROOT.parent)
                elif mutation == 'failure': item['status'] = 'failed'
                elif mutation == 'partial': value['partial'] = True
                elif mutation == 'digest': value['sha256'] = 'b' * 64
                else: value['content'] = value['content'][:-1]
                self.assertEqual(runner.assess_observation(self.observation(), {'mechanical': ['activation_before_delegation']}, events)['status'], 'failed')


class InteractiveFixtureTests(unittest.TestCase):
    def client(self):
        client = runner.AppServer.__new__(runner.AppServer)
        client.root_id, client.turn_id = 'parent', 'turn'
        client.client_requests, client.answered_requests = [], []
        self.question = {'id': 'target', 'header': 'Target', 'question': 'Which fixture?'}
        client.answer_fixtures = runner.validate_answers([{'questions': [self.question], 'answers': {'target': {'answers': ['A']}}}])
        self.sent = []
        client._write = self.sent.append
        client._record = lambda *args: None
        return client

    def test_exact_question_in_current_turn_gets_fixture_answer(self):
        client = self.client()
        client._handle_request({'id': 1, 'method': 'item/tool/requestUserInput', 'params': {
            'threadId': 'parent', 'turnId': 'turn', 'questions': [self.question]}}, 10)
        self.assertEqual(self.sent, [{'id': 1, 'result': {'answers': {'target': {'answers': ['A']}}}}])
        self.assertEqual(len(client.answer_fixtures), 0)

    def test_changed_question_or_permission_prompt_is_never_answered(self):
        for method in ['item/tool/requestUserInput', 'item/commandExecution/requestApproval']:
            client = self.client()
            client._handle_request({'id': 1, 'method': method, 'params': {
                'threadId': 'parent', 'turnId': 'turn', 'questions': [{**self.question, 'question': 'Approve publication?'}]}}, 10)
            self.assertEqual(len(client.answer_fixtures), 1)
            self.assertEqual(len(client.client_requests), 1)
            self.assertNotIn('answers', self.sent[0].get('result', {}))

    def test_wrong_session_cannot_consume_an_answer(self):
        client = self.client()
        client._handle_request({'id': 1, 'method': 'item/tool/requestUserInput', 'params': {
            'threadId': 'other', 'turnId': 'turn', 'questions': [self.question]}}, 10)
        self.assertEqual(len(client.answer_fixtures), 1)

    def test_malformed_answers_fail_before_agent_start(self):
        with self.assertRaises(ValueError):
            runner.validate_answers([{'questions': [{'id': 'x', 'header': 'X', 'question': 'X?'}], 'answers': {'x': ['wrong wire shape']}}])


class OfflineReviewTests(unittest.TestCase):
    def test_current_candidate_change_invalidates_bound_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / 'candidate.md'
            candidate.write_text('tested content', encoding='utf-8')
            native = AcceptanceTests().observation()
            native['candidate_roots'] = [str(candidate)]
            native['candidate_before'] = native['candidate_after'] = runner.file_inventory([candidate])
            result = root / 'result.json'
            result.write_text(json.dumps(native), encoding='utf-8')
            events = root / 'appserver-events.jsonl'
            events.write_text('', encoding='utf-8')
            criteria = root / 'criteria.json'
            criteria.write_text(json.dumps({'mechanical': ['completed'], 'semantic': ['correct_target']}), encoding='utf-8')
            review = root / 'review.json'
            review.write_text(json.dumps({'reviewer': 'test-fixture-reviewer', 'result_sha256': runner.sha(result),
                'events_sha256': runner.sha(events), 'criteria_sha256': runner.sha(criteria),
                'criteria': {'correct_target': {'status': 'satisfied', 'evidence': 'fixture'}}}), encoding='utf-8')
            candidate.write_text('changed after testing', encoding='utf-8')
            self.assertEqual(runner.assess_files(result, review), 2)
            self.assertEqual(json.loads((root / 'acceptance-reviewed.json').read_text())['status'], 'failed')

    def test_review_cannot_be_reused_after_observation_changed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'result.json'
            path.write_text('{}', encoding='utf-8')
            review = Path(td) / 'review.json'
            review.write_text(json.dumps({'reviewer': 'independent', 'result_sha256': 'old'}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hashes'):
                runner.assess_files(path, review)

    def test_inventory_detects_file_additions_and_changes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'fixture.txt'
            p.write_text('before', encoding='utf-8')
            before = runner.file_inventory([td])
            p.write_text('after', encoding='utf-8')
            (Path(td) / 'added.txt').write_text('added', encoding='utf-8')
            after = runner.file_inventory([td])
            self.assertNotEqual(before[str(p.resolve())], after[str(p.resolve())])
            self.assertEqual(len(after), 2)


class ConversationTests(unittest.TestCase):
    def test_two_turns_use_same_thread_and_wait_each_time(self):
        client = runner.AppServer.__new__(runner.AppServer)
        client.root_id = 'same-thread'
        client.public_messages = {}
        client.completed_turn = {'id': 'old', 'status': 'completed'}
        calls = []
        def rpc(method, params, timeout=0):
            self.assertIsNone(client.completed_turn)
            calls.append((method, params))
            return {'turn': {'id': 't' + str(len(calls))}}
        def pump():
            client.completed_turn = {'id': client.turn_id, 'status': 'completed'}
        client.rpc, client.pump = rpc, pump
        results = [client.run_turn(text) for text in ['initial request', 'user refinement']]
        self.assertEqual([x['id'] for x in results], ['t1', 't2'])
        self.assertEqual([p['threadId'] for _, p in calls], ['same-thread', 'same-thread'])


if __name__ == '__main__':
    unittest.main()
