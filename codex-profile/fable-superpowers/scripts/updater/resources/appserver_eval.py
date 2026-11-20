"""Collect ordinary tasks and assess explicit criteria through app-server.

Current user configuration and global instructions are preserved. The runner
creates one ephemeral thread (read-only unless explicitly selected otherwise).
Completion and acceptance are separate. Multi-turn inputs and exact-match answers
are synthetic test fixtures, never owner permission. Reasoning and credentials
are removed from persisted observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time


HERE = Path(__file__).resolve().parent
SCHEMA_DIR = HERE / "appserver-schema"
OMIT = object()
COLLAB_NAMES = re.compile(
    r"(?:^|[.:/])(?:spawn_agent|followup_task|send_message|wait_agent|wait|"
    r"list_agents|interrupt_agent|spawnAgent|followupTask|sendInput)$"
)
SECRET_NAMES = r'(?:authorization|proxy[_.-]?authorization|cookie|set[_.-]?cookie|password|passwd|secret|client[_.-]?secret|api[_.-]?key|access[_.-]?token|refresh[_.-]?token|id[_.-]?token|bearer[_.-]?token|x[_.-]?control[_.-]?secret|x[_.-]?amz[_.-]?(?:signature|credential)|x[_.-]?goog[_.-]?(?:signature|credential)|signature|sig|token)'
SECRET_KEY = re.compile(SECRET_NAMES, re.IGNORECASE)


def redact_text(text):
    # Decode JSON-shaped tool output before matching text; tokens often live in
    # a JSON string nested inside an otherwise structured event.
    if text.lstrip().startswith(('{', '[')):
        try:
            decoded = json.loads(text)
        except (ValueError, RecursionError):
            pass
        else:
            cleaned = safe_value(decoded)
            return json.dumps(None if cleaned is OMIT else cleaned, ensure_ascii=False)
    text = re.sub(r'(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie|x-control-secret)\s*[:=]\s*)[^\r\n]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'(?i)(\b' + SECRET_NAMES + r'''["']?\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s&;,]+)''', r'\1[REDACTED]', text)
    text = re.sub(r'(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[REDACTED PRIVATE KEY]', text)
    return text


def resolve_codex(explicit=None):
    selected = explicit or os.environ.get('FABLE5_CODEX_BIN')
    if selected:
        path = Path(selected).expanduser().resolve(strict=True)
        if not path.is_file():
            raise FileNotFoundError('Selected Codex executable is not a file')
        return str(path)
    located = shutil.which('codex')
    if located:
        return located
    resources = os.environ.get('CODEX_ELECTRON_RESOURCES_PATH')
    if resources:
        embedded = Path(resources) / ('codex.exe' if os.name == 'nt' else 'codex')
        if embedded.is_file():
            return str(embedded.resolve())
    raise FileNotFoundError('Codex executable unavailable; pass --codex-bin explicitly')


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def safe_value(value):
    """Discard private reasoning/encryption, preserving ordinary tool evidence."""
    if isinstance(value, dict):
        kind = str(value.get("type", "")).lower()
        if kind in {"reasoning", "encrypted_content"}:
            return OMIT
        result = {}
        for key, child in value.items():
            if key in {
                "encrypted_content", "encrypted_function_args",
                "internal_chat_message_metadata_passthrough",
            }:
                continue
            if SECRET_KEY.fullmatch(key):
                result[key] = '[REDACTED]'
                continue
            cleaned = safe_value(child)
            if cleaned is not OMIT:
                result[key] = cleaned
        return result
    if isinstance(value, list):
        return [cleaned for child in value if (cleaned := safe_value(child)) is not OMIT]
    if isinstance(value, str):
        return redact_text(value)
    return value


def safe_message(message: dict):
    method = message.get("method", "")
    if "reasoning" in method.lower():
        return OMIT
    item = (message.get("params") or {}).get("item", {})
    if isinstance(item, dict) and str(item.get("type", "")).lower() == "reasoning":
        return OMIT
    return safe_value(message)


def validate_known_request(schema_name: str, params: dict) -> None:
    """Reject stale top-level wire keys using this installed binary's schema."""
    path = SCHEMA_DIR / schema_name
    schema = json.loads(path.read_text(encoding="utf-8"))
    required = set(schema.get("required", []))
    properties = set(schema.get("properties", {}))
    if not required.issubset(params) or not set(params).issubset(properties):
        raise ValueError(f"Request does not match installed {schema_name} keys")


class RpcError(RuntimeError):
    pass


class AppServer:
    def __init__(self, cwd: Path, out: Path, deadline: float, codex_home: Path | None = None,
                 codex_bin=None, answers=None, watch_paths=None):
        codex = resolve_codex(codex_bin)
        env = os.environ.copy()
        env.pop("CODEX_THREAD_ID", None)
        if codex_home is not None:
            env['CODEX_HOME'] = str(codex_home)
        env['FABLE5_CODEX_BIN'] = codex
        self.stderr = (out / "appserver-stderr.log").open("w", encoding='utf-8')
        self.events = (out / "appserver-events.jsonl").open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [codex, "app-server", "--stdio", "-c", "features.prefer_mxc=true",
             "-c", "sandbox_workspace_write.writable_roots=[]"], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.deadline = deadline
        self.cwd = Path(cwd).resolve(strict=True)
        self.watch_paths = [Path(path) for path in (watch_paths or [])]
        self.last_inventory = {}
        self.observed_execution_evidence = []
        self.messages = queue.Queue()
        self.responses = {}
        self.next_id = 1
        self.event_line = 0
        self.root_id = None
        self.turn_id = None
        self.completed_turn = None
        self.public_messages = {}
        self.deltas = {}
        self.collab = {}
        self.activities = []
        self.thread_metadata = {}
        self.raw_calls = {}
        self.raw_collaboration_receipts = []
        self.child_ids = set()
        self.client_requests = []
        self.errors = []
        self.answer_fixtures = list(answers or [])
        self.answered_requests = []
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        self.stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_reader.start()

    def _read_stderr(self):
        for line in self.process.stderr:
            self.stderr.write(redact_text(line.decode('utf-8', errors='replace')))
            self.stderr.flush()

    def run_turn(self, text, effort=None):
        self.completed_turn = None
        self.turn_id = None
        params = {'threadId': self.root_id, 'input': [{'type': 'text', 'text': text}]}
        if effort:
            params['effort'] = effort
        validate_known_request('v2/TurnStartParams.json', params)
        response = self.rpc('turn/start', params, timeout=90)
        self.turn_id = response['turn']['id']
        while self.completed_turn is None:
            self.pump()
        return self.completed_turn

    def _read_stdout(self):
        try:
            for line in self.process.stdout:
                self.messages.put(line)
        finally:
            self.messages.put(None)

    def _write(self, message: dict):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        self.process.stdin.flush()

    def _record(self, message: dict, direction="server"):
        cleaned = safe_message(message)
        if cleaned is OMIT:
            return None
        self.event_line += 1
        self.events.write(json.dumps({"direction": direction, **cleaned}, ensure_ascii=False) + "\n")
        self.events.flush()
        return self.event_line

    def notify(self, method: str, params: dict):
        message = {"method": method, "params": params}
        self._record(message, "client")
        self._write(message)

    def rpc(self, method: str, params: dict, timeout=30):
        request_id = self.next_id
        self.next_id += 1
        message = {"id": request_id, "method": method, "params": params}
        self._record(message, "client")
        self._write(message)
        until = min(self.deadline, time.monotonic() + timeout)
        while request_id not in self.responses:
            self.pump(until)
        response = self.responses.pop(request_id)
        if "error" in response:
            error = response["error"]
            raise RpcError(f"{method}: {error.get('code')}: {str(error.get('message', ''))[:2000]}")
        return response.get("result")

    def pump(self, until=None):
        until = min(self.deadline, until or self.deadline)
        remaining = until - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("App-server evaluation timed out")
        try:
            line = self.messages.get(timeout=min(remaining, 1.0))
        except queue.Empty:
            if self.process.poll() is not None:
                raise RuntimeError(f"App-server exited ({self.process.returncode})")
            return
        if line is None:
            raise RuntimeError(f"App-server stdout closed ({self.process.poll()})")
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError("App-server emitted invalid JSON; inspect stderr") from error
        event_line = self._record(message)
        if "method" in message:
            if "id" in message:
                self._handle_request(message, event_line)
            else:
                self._observe(message, event_line)
        elif "id" in message:
            self.responses[message["id"]] = message

    def _handle_request(self, message, line):
        method = message["method"]
        params = message.get('params', {})
        if method == 'item/tool/requestUserInput' and self.answer_fixtures:
            fixture = self.answer_fixtures[0]
            if (params.get('threadId') == self.root_id and params.get('turnId') == self.turn_id
                    and params.get('questions') == fixture.get('questions')):
                self.answer_fixtures.pop(0)
                response = {'id': message['id'], 'result': {'answers': fixture['answers']}}
                self.answered_requests.append({'event_line': line, 'fixture': True,
                                              'questions': safe_value(params['questions'])})
                self._record(response, 'synthetic_test_answer')
                self._write(response)
                return
        self.client_requests.append({"event_line": line, "method": method, "params": safe_value(params)})
        # Never fabricate a user answer or accept an unexpected permission prompt.
        if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
            response = {"id": message["id"], "result": {"decision": "decline"}}
        else:
            response = {"id": message["id"], "error": {
                "code": -32601,
                "message": "This evaluation client cannot answer interactive requests.",
            }}
        self._record(response, "client")
        self._write(response)

    def _capture_execution(self, item, line):
        """Observe fixture bytes at the boundary of a completed native item.

        The receipt comes from the controller, never from agent answer text.
        Unknown tool/output shapes produce incomplete evidence, not a pass.
        """
        watched = {}
        root = self.cwd
        for selected in self.watch_paths:
            if not selected.exists():
                continue
            try:
                # Watch targets must stay inside the actual fixture root.
                selected.absolute().relative_to(root)
            except ValueError:
                raise ValueError('Observed test path escaped the fixture.')
            for path, value in file_inventory([str(selected)]).items():
                relative = Path(path).relative_to(root).as_posix()
                watched[relative] = value
        watched = dict(sorted(watched.items()))
        previous = self.last_inventory
        changed = sorted(p for p in set(previous) | set(watched)
                         if previous.get(p) != watched.get(p))
        self.last_inventory = watched

        output = item.get('aggregatedOutput') or ''
        count = re.search(r'\bRan\s+(\d+)\s+tests?\b', output)
        test_ids = []
        for match in re.finditer(
                r'(?m)^\s*(test_[\w]+)\s+\(([^)\n]+)\)\s+\.\.\.\s*'
                r'(?:ok|FAIL|ERROR|skipped|expected failure|unexpected success)\b', output):
            test_ids.append(match.group(2) + '.' + match.group(1))
        source_tests = {name: hashed for name, hashed in watched.items()
                        if name.startswith('tests/') and name.endswith('.py')}
        self.observed_execution_evidence.append({
            'execution_id': item.get('id'), 'event_line': line,
            'cwd': str(root), 'type': item.get('type'),
            'command': item.get('command'), 'exit_code': item.get('exitCode'),
            'tests_run': int(count.group(1)) if count else 0,
            'test_ids': test_ids, 'source_test_inventory': source_tests,
            'inventory': watched, 'changed_paths': changed,
        })

    def _observe(self, message, line):
        method = message["method"]
        params = message.get("params", {})
        thread_id = params.get("threadId")
        if method == "thread/started":
            thread = safe_value(params.get("thread", {}))
            if thread is not OMIT and thread.get("id"):
                self.thread_metadata[thread["id"]] = thread
                if self.root_id and thread.get("parentThreadId") == self.root_id:
                    self.child_ids.add(thread["id"])
        elif method in {"item/started", "item/completed"}:
            item = params.get("item", {})
            kind = item.get("type")
            if (method == "item/completed" and thread_id == self.root_id
                    and kind in {"commandExecution", "fileChange"}
                    and getattr(self, "watch_paths", None)):
                try:
                    self._capture_execution(item, line)
                except (OSError, ValueError) as error:
                    self.errors.append({"observation": "inventory_snapshot_failed",
                                        "event_line": line, "message": str(error)[:200]})
            if kind == "agentMessage" and method == "item/completed":
                self.public_messages[(thread_id, item["id"])] = {
                    "thread_id": thread_id, "turn_id": params.get("turnId"),
                    "event_line": line, **safe_value(item),
                }
            elif kind == "collabAgentToolCall":
                cleaned = safe_value(item)
                self.collab[item["id"]] = {"event_line": line, **cleaned}
                if item.get("senderThreadId") == self.root_id:
                    self.child_ids.update(item.get("receiverThreadIds", []))
            elif kind == "subAgentActivity":
                self.activities.append({"event_line": line, "thread_id": thread_id, **item})
                if thread_id == self.root_id:
                    self.child_ids.add(item["agentThreadId"])
        elif method == "item/agentMessage/delta":
            key = (thread_id, params.get("itemId"))
            self.deltas[key] = self.deltas.get(key, "") + params.get("delta", "")
        elif method == "rawResponseItem/completed":
            item = params.get("item", {})
            kind = item.get("type")
            if kind in {"function_call", "custom_tool_call"}:
                name = item.get("name", "")
                if COLLAB_NAMES.search(name):
                    self.raw_calls[item["call_id"]] = {
                        "event_line": line, "thread_id": thread_id, **safe_value(item),
                    }
            elif kind in {"function_call_output", "custom_tool_call_output"}:
                call = self.raw_calls.get(item.get("call_id"))
                if call:
                    self.raw_collaboration_receipts.append({
                        "call": call,
                        "output": {"event_line": line, "thread_id": thread_id, **safe_value(item)},
                    })
        elif method == "turn/completed" and thread_id == self.root_id:
            turn = params.get("turn", {})
            if self.turn_id is None or turn.get("id") == self.turn_id:
                self.completed_turn = safe_value(turn)
        elif method == "error":
            self.errors.append(safe_value(params))

    def read_children(self):
        snapshots = {}
        try:
            listing = self.rpc("thread/list", {
                "parentThreadId": self.root_id,
                "sourceKinds": ["subAgent", "subAgentReview", "subAgentThreadSpawn"],
                "limit": 100, "useStateDbOnly": True,
            }, timeout=20)
            for thread in listing.get("data", []):
                self.child_ids.add(thread["id"])
                self.thread_metadata[thread["id"]] = safe_value(thread)
        except (RpcError, TimeoutError) as error:
            self.errors.append({"observation": "child_listing_unavailable", "message": str(error)})
        for child_id in sorted(self.child_ids - {self.root_id}):
            snapshot = {"thread_id": child_id, "items": [], "errors": []}
            try:
                response = self.rpc("thread/read", {"threadId": child_id, "includeTurns": True}, timeout=15)
                snapshot["thread"] = safe_value(response.get("thread", {}))
            except (RpcError, TimeoutError) as error:
                snapshot["errors"].append(str(error))
            try:
                cursor = None
                for _ in range(20):
                    params = {"threadId": child_id, "sortDirection": "asc", "limit": 50}
                    if cursor is not None:
                        params["cursor"] = cursor
                    response = self.rpc("thread/items/list", params, timeout=15)
                    snapshot["items"].extend(safe_value(response.get("data", [])))
                    cursor = response.get("nextCursor")
                    if cursor is None:
                        break
                else:
                    snapshot["errors"].append("Child item history exceeded 1000 entries")
            except (RpcError, TimeoutError) as error:
                snapshot["errors"].append(str(error))
            snapshots[child_id] = snapshot
        return snapshots

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.events.close()
        self.stderr_reader.join(timeout=5)
        if self.stderr_reader.is_alive():
            raise RuntimeError('stderr reader did not stop; observation is incomplete')
        self.stderr.close()


def public_child_reports(snapshots, messages, collab):
    reports = {}
    for child_id, snapshot in snapshots.items():
        found = {}
        for message in messages.values():
            if message.get("thread_id") == child_id:
                found[message["id"]] = message
        observed = dict(found)

        def snapshot_report(item):
            # Only a streamed completion supplies chronology. A history snapshot
            # may enrich the same completed message, but cannot timestamp a new
            # or conflicting verdict with another message's receipt.
            report = {key: value for key, value in item.items() if key != "event_line"}
            live = observed.get(item["id"])
            if (live and item.get("text") == live.get("text")
                    and item.get("phase") in (None, live.get("phase"))):
                report.update(live)
            return report

        for turn in snapshot.get("thread", {}).get("turns", []):
            for item in turn.get("items", []):
                if item.get("type") == "agentMessage":
                    found[item["id"]] = snapshot_report(item)
        for entry in snapshot.get("items", []):
            item = entry.get("item", {})
            if item.get("type") == "agentMessage":
                found[item["id"]] = snapshot_report(item)
        for call in collab.values():
            state = call.get("agentsStates", {}).get(child_id, {})
            if state.get("message"):
                found["collab:" + call["id"]] = {
                    "text": state["message"], "status": state.get("status"),
                    "source": "native_collab_agent_state", "event_line": call["event_line"],
                }
        reports[child_id] = list(found.values())
    return reports


def file_inventory(paths):
    """Hash declared files/directories without following directory links."""
    result = {}
    for name in paths:
        path = Path(name).resolve(strict=True)
        files = [path] if path.is_file() else sorted(path.rglob('*'))
        for file in files:
            if file.is_symlink() or any(p.is_symlink() for p in file.parents if p != path.parent):
                raise ValueError('Evidence inventory cannot include symbolic links')
            if file.is_file():
                result[str(file)] = sha(file)
    return result


def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8-sig')) if path else default


def validate_answers(fixtures):
    if not isinstance(fixtures, list):
        raise ValueError('Answer fixtures must be a list')
    for fixture in fixtures:
        if not isinstance(fixture, dict) or set(fixture) != {'questions', 'answers'}:
            raise ValueError('Answer fixture requires exactly questions and answers')
        questions, answers = fixture['questions'], fixture['answers']
        if not isinstance(questions, list) or not questions or not isinstance(answers, dict):
            raise ValueError('Invalid question/answer fixture')
        ids = []
        for question in questions:
            if (not isinstance(question, dict) or question.get('isSecret')
                    or not all(isinstance(question.get(k), str) and question[k] for k in ('id', 'header', 'question'))):
                raise ValueError('Fixture questions must be explicit non-secret questions')
            ids.append(question['id'])
        if len(set(ids)) != len(ids) or set(answers) != set(ids):
            raise ValueError('Answers must match the unique question ids')
        for answer in answers.values():
            if (not isinstance(answer, dict) or set(answer) != {'answers'}
                    or not isinstance(answer['answers'], list) or not answer['answers']
                    or not all(isinstance(x, str) for x in answer['answers'])):
                raise ValueError('Answer must match ToolRequestUserInputResponse')
    return fixtures


def verdict(status, evidence):
    return {'status': status, 'evidence': evidence}


def event_items(events, root_id):
    return [(number, event.get('params', {}).get('item', {}))
            for number, event in enumerate(events, 1)
            if event.get('params', {}).get('threadId') == root_id
            and event.get('method') in {'item/started', 'item/completed', 'rawResponseItem/completed'}]


def payload(item):
    value = item.get('result') or {}
    if value.get('isError'):
        return {}
    if isinstance(value.get('structuredContent'), dict):
        return value['structuredContent']
    for content in value.get('content', []):
        if content.get('type') == 'text':
            try:
                decoded = json.loads(content.get('text', ''))
                if isinstance(decoded, dict):
                    return decoded
            except ValueError:
                pass
    return {}


def activation_order(native, events):
    """Verify native receipts, never an assistant's claim that Fable is ready."""
    items = event_items(events, native.get('thread_id'))
    starts, seen_calls = set(), set()
    for line, item in items:
        is_spawn = ((item.get('type') == 'subAgentActivity' and item.get('kind') == 'started')
                    or (item.get('type') == 'collabAgentToolCall' and item.get('tool') in {'spawnAgent', 'spawn_agent'})
                    or (item.get('type') in {'function_call', 'custom_tool_call'} and re.search(r'(?:^|[.:/])(?:spawn_agent|spawnAgent)$', item.get('name', ''))))
        if not is_spawn:
            continue
        # Count the earliest observed receipt for an invocation, including raw
        # calls. Missing IDs are never evidence that two events are the same.
        keys = {(key, item[key]) for key in ('id', 'call_id', 'callId')
                if isinstance(item.get(key), str) and item[key]}
        # Normalize the two spellings of call IDs.
        keys = {('call_id' if key == 'callId' else key, value) for key, value in keys}
        if not keys or not keys.intersection(seen_calls):
            starts.add(line)
        seen_calls.update(keys)
    if not starts:
        return verdict('not_checked', 'No native delegation event observed')
    def same_cwd(value):
        return (isinstance(value, str) and bool(value.strip()) and Path(value).is_absolute()
                and Path(value).resolve() == Path(native['cwd']).resolve())

    def identity(skill):
        return (isinstance(skill, dict)
                and all(isinstance(skill.get(k), str) and skill[k].strip() for k in ('id', 'name', 'path', 'plugin_id'))
                and isinstance(skill.get('sha256'), str) and re.fullmatch(r'[a-f0-9]{64}', skill['sha256']))

    searches, reads = [], []
    def complete_activation(line, state):
        selected = state.get('skills', {})
        if (not isinstance(selected, dict)
                or not all(key in selected for key in ('fable', 'using_superpowers', 'writing_plans'))
                or not all(identity(skill) for skill in selected.values())):
            return False
        complete = True
        for skill in selected.values():
            discovered = [n for n, value in searches if n < line and value.get('catalog_sha256') == state.get('catalog_sha256')
                          and any(isinstance(found, dict)
                                  and all(found.get(k) == skill.get(k) for k in ('id', 'name', 'path', 'plugin_id'))
                                  and ('sha256' not in found or found['sha256'] == skill['sha256'])
                                  for found in value.get('skills', []))]
            if not discovered:
                complete = False
                break
            pages = [value for n, value in reads if min(discovered) < n < line
                     and value.get('sha256') == skill.get('sha256')
                     and all(value.get('skill', {}).get(k) == skill.get(k) for k in ('id', 'name', 'path', 'plugin_id'))]
            end, total, pieces = 0, None, []
            for page in sorted(pages, key=lambda p: p.get('offset', -1)):
                if page.get('offset') != end or not isinstance(page.get('content'), str):
                    continue
                if total is not None and total != page.get('total_chars'):
                    break
                total = page.get('total_chars')
                pieces.append(page['content'])
                end += len(page['content'])
            digest = hashlib.sha256(''.join(pieces).encode('utf-8')).hexdigest()
            if not isinstance(total, int) or total <= 0 or end != total or digest != skill.get('sha256'):
                complete = False
                break
        if complete and re.fullmatch(r'[a-f0-9]{64}', state.get('catalog_sha256', '')):
            return True
        return False

    active = False
    selected = {}
    catalog = None

    def conflicting_skill(left, right):
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        if not left.get('id') or left.get('id') != right.get('id'):
            return False
        return any(left.get(k) is not None and right.get(k) is not None and left[k] != right[k]
                   for k in ('id', 'name', 'path', 'plugin_id', 'sha256'))
    for line, item in items:
        if line in starts:
            if not active:
                return verdict('violated', f'Delegation at event {line} lacked current complete activation evidence')
            continue
        if (events[line - 1].get('method') != 'item/completed' or item.get('type') != 'mcpToolCall'
                or item.get('tool', '').replace('-', '_') not in {'search_skills', 'read_skill', 'fable_status'}):
            continue
        if 'fable' not in item.get('server', '').lower():
            continue
        args = item.get('arguments') or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                continue
        if not isinstance(args, dict) or not same_cwd(args.get('cwd')):
            continue
        tool = item.get('tool', '').replace('-', '_')
        value = payload(item)
        if item.get('status') not in {'completed', 'success'} or value.get('partial') is not False or value.get('warning_count') != 0:
            searches, reads, active, selected, catalog = [], [], False, {}, None
            continue
        if tool == 'fable_status':
            candidate = value.get('skills', {})
            if value.get('status') != 'ready' or not same_cwd(value.get('cwd')):
                searches, reads, active, selected, catalog = [], [], False, {}, None
            elif active and candidate != selected:
                searches, reads, active, selected, catalog = [], [], False, {}, None
            else:
                active = complete_activation(line, value)
                selected = candidate if active else {}
                if not active:
                    searches, reads, catalog = [], [], None
        else:
            known = list(selected.values())
            known.extend(skill for _, receipt in searches for skill in receipt.get('skills', [])
                         if isinstance(skill, dict))
            known.extend(receipt.get('skill', {}) for _, receipt in reads)
            if tool == 'search_skills':
                found = value.get('skills', [])
                new_catalog = value.get('catalog_sha256')
                if (not isinstance(found, list) or not isinstance(new_catalog, str)
                        or not re.fullmatch(r'[a-f0-9]{64}', new_catalog)):
                    searches, reads, active, selected, catalog = [], [], False, {}, None
                    continue
                if ((catalog is not None and new_catalog != catalog)
                        or any(conflicting_skill(skill, previous) for skill in found for previous in known)):
                    searches, reads, active, selected = [], [], False, {}
                catalog = new_catalog
                searches.append((line, value))
            else:
                skill = value.get('skill', {})
                observed = {**skill, 'sha256': value.get('sha256')} if isinstance(skill, dict) else {}
                offset, content = value.get('offset'), value.get('content')
                conflict = any(conflicting_skill(observed, previous) for previous in known)
                for _, previous in reads:
                    prior_skill = previous.get('skill', {})
                    if (not isinstance(prior_skill, dict) or not isinstance(skill, dict)
                            or not all(skill.get(k) == prior_skill.get(k) for k in ('id', 'name', 'path', 'plugin_id'))):
                        continue
                    prior_offset, prior_content = previous.get('offset'), previous.get('content')
                    if (not isinstance(offset, int) or not isinstance(prior_offset, int)
                            or not isinstance(content, str) or not isinstance(prior_content, str)):
                        conflict = True
                        break
                    start = max(offset, prior_offset)
                    end = min(offset + len(content), prior_offset + len(prior_content))
                    if (value.get('total_chars') != previous.get('total_chars')
                            or (start < end and content[start - offset:end - offset]
                                != prior_content[start - prior_offset:end - prior_offset])):
                        conflict = True
                        break
                if conflict:
                    searches, reads, active, selected, catalog = [], [], False, {}, None
                reads.append((line, value))
    return verdict('satisfied', 'Complete matching activation receipts precede every delegation')


def assess_observation(native, criteria, events, semantic=None):
    """Mechanical evidence and an independently supplied semantic review stay separate."""
    if not isinstance(criteria, dict) or set(criteria) - {'mechanical', 'semantic'}:
        raise ValueError('Criteria must contain mechanical and/or semantic lists')
    mechanical = criteria.get('mechanical', [])
    semantic_ids = criteria.get('semantic', [])
    allowed = {'completed', 'read_only', 'delegation', 'activation_before_delegation'}
    reserved = allowed | {'profile_unchanged', 'candidate_unchanged', 'observation_complete', 'current_evidence'}
    if (not isinstance(mechanical, list) or not isinstance(semantic_ids, list)
            or not all(isinstance(x, str) and x for x in mechanical + semantic_ids)
            or not set(mechanical).issubset(allowed)
            or bool(set(semantic_ids) & reserved)
            or len(set(mechanical + semantic_ids)) != len(mechanical + semantic_ids)):
        raise ValueError('Unknown or duplicate acceptance criterion')
    checks = {}
    for before, after, key in [('config_hashes_before', 'config_hashes_after', 'profile_unchanged'),
                               ('candidate_before', 'candidate_after', 'candidate_unchanged')]:
        if not native.get(before) or not native.get(after):
            checks[key] = verdict('not_checked', 'Missing before/after inventory')
        else:
            checks[key] = verdict('satisfied' if native[before] == native[after] else 'violated', 'Compared before/after hashes')
    checks['observation_complete'] = verdict(
        'violated' if native.get('observation_errors') or native.get('unexpected_client_requests') or native.get('status') != 'completed'
        or any(child.get('errors') for child in native.get('children', {}).values())
        or (native.get('planned_turn_count') is not None and len(native.get('turns', [])) != native['planned_turn_count'])
        else 'satisfied', 'Native status, observation errors and unhandled client requests')
    items = event_items(events, native.get('thread_id'))
    for key in mechanical:
        if key == 'completed':
            check = verdict('satisfied' if native.get('status') == 'completed' else 'violated', 'Native turn status only; does not establish task correctness')
        elif key == 'read_only':
            # Include children and failed attempts. Hash equality alone cannot
            # establish absence of writes outside the watched fixture.
            all_items = [event.get('params', {}).get('item', {}) for event in events]
            if any(item.get('type') == 'fileChange' for item in all_items) or native.get('watched_before') != native.get('watched_after'):
                check = verdict('violated', 'A file-change attempt or changed watched file was observed')
            elif any(item.get('type') in {'commandExecution', 'mcpToolCall', 'function_call', 'custom_tool_call', 'collabAgentToolCall', 'subAgentActivity'} for item in all_items):
                check = verdict('not_checked', 'Tool effects require semantic review; a denied attempt also violates read-only')
            elif native.get('sandbox') == 'read-only' and native.get('watched_before'):
                check = verdict('satisfied', 'Read-only sandbox, unchanged watched files and no effectful tools')
            else:
                check = verdict('not_checked', 'Missing read-only sandbox or watched inventory')
        elif key == 'activation_before_delegation':
            check = activation_order(native, events)
        else:
            child_ids = {item.get('agentThreadId') for _, item in items if item.get('type') == 'subAgentActivity' and item.get('kind') == 'started'} - {None}
            completed = {item.get('agentThreadId') for _, item in items if item.get('type') == 'subAgentActivity' and item.get('kind') == 'completed'}
            reported = {cid for cid, reports in native.get('child_reports', {}).items()
                        if any(r.get('phase') == 'final_answer' and r.get('text', '').strip() for r in reports)}
            check = verdict('satisfied' if child_ids and child_ids <= completed & reported else 'not_checked', 'Requires native child start, completion and actual final report')
        checks[key] = check
    read_only_review = (semantic or {}).get('read_only', {})
    if (checks.get('read_only', {}).get('status') == 'not_checked'
            and read_only_review.get('status') in {'satisfied', 'violated'}
            and read_only_review.get('evidence')):
        checks['read_only'] = {**read_only_review, 'mechanical_status': 'not_checked',
                               'source': 'independent_semantic_review'}
    for key in semantic_ids:
        review = (semantic or {}).get(key, {})
        if review.get('status') not in {'satisfied', 'violated', 'not_checked', 'not_applicable'} or not review.get('evidence'):
            checks[key] = verdict('not_checked', 'Independent semantic evidence is missing')
        else:
            checks[key] = review
    states = [x['status'] for x in checks.values()]
    status = 'failed' if 'violated' in states else 'incomplete' if not mechanical + semantic_ids or any(s in states for s in ('not_checked', 'not_applicable')) else 'passed'
    return {'status': status, 'criteria': checks, 'scope': 'Declared criteria only; publication, installation and production acceptance are separate'}


def assess_files(result_path, review_path):
    """Bind an offline review to the exact immutable observation and criteria."""
    path = Path(result_path).resolve(strict=True)
    review = read_json(review_path)
    native = read_json(path)
    events_path = path.parent / 'appserver-events.jsonl'
    criteria_path = path.parent / 'criteria.json'
    expected = {'result_sha256': sha(path), 'events_sha256': sha(events_path), 'criteria_sha256': sha(criteria_path)}
    if not all(review.get(k) == v and v for k, v in expected.items()) or not review.get('reviewer'):
        raise ValueError('Review must identify its reviewer and match result/events/criteria hashes')
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
    assessment = assess_observation(native, read_json(criteria_path), events, review.get('criteria'))
    # Assessment is current only while candidate and profile files still match.
    recorded = {**native.get('candidate_after', {}), **native.get('profile_files_after', {})}
    try:
        current_candidate = file_inventory(native.get('candidate_roots', list(native.get('candidate_after', {}))))
    except (OSError, ValueError):
        current_candidate = None
    if (not recorded or current_candidate != native.get('candidate_after')
            or any(sha(Path(name)) != digest for name, digest in recorded.items())):
        assessment['status'] = 'failed'
        assessment['criteria']['current_evidence'] = verdict('violated', 'Candidate/profile changed since observation')
    output = path.parent / 'acceptance-reviewed.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(safe_value({**assessment, 'binding': expected, 'reviewer': review['reviewer']}), stream, ensure_ascii=False, indent=2)
    print(json.dumps({'status': assessment['status'], 'assessment': str(output)}))
    return 0 if assessment['status'] == 'passed' else 2


def run(args):
    cwd = Path(args.cwd).resolve(strict=True)
    prompt_path = Path(args.prompt_file).resolve(strict=True)
    out = Path(args.out_dir).resolve()
    if not cwd.is_dir():
        raise ValueError("--cwd must be an existing directory")
    out.mkdir(parents=True, exist_ok=False)
    prompt = prompt_path.read_text(encoding="utf-8")
    (out / "prompt.txt").write_text(redact_text(prompt), encoding="utf-8")
    criteria = read_json(args.criteria_file, {})
    assess_observation({}, criteria, [])  # Validate before starting a model.
    turns = read_json(args.turns_file, [])
    answers = validate_answers(read_json(args.answers_file, []))
    if not isinstance(turns, list) or not all(isinstance(x, str) and x.strip() for x in turns):
        raise ValueError('--turns-file must contain a JSON list of synthetic user messages')
    (out / 'criteria.json').write_text(json.dumps(safe_value(criteria), ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'synthetic-inputs.json').write_text(json.dumps(safe_value({'turns': turns, 'answers': answers}), ensure_ascii=False, indent=2), encoding='utf-8')
    home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    before = {"global_instructions": sha(home / "AGENTS.md"), "user_config": sha(home / "config.toml")}
    started = time.monotonic()
    client = None
    profile_files = [home / 'AGENTS.md', home / 'config.toml']
    result = {"status": "starting", "cwd": str(cwd), "config_hashes_before": before,
              'sandbox': args.sandbox, 'profile_label': args.profile_label,
              'candidate_roots': [str(Path(p).resolve()) for p in args.candidate_file],
              'candidate_before': file_inventory(args.candidate_file),
              'watched_before': file_inventory(args.watch), 'turns': []}
    try:
        client = AppServer(cwd, out, started + args.timeout_seconds, codex_home=home,
                           codex_bin=args.codex_bin, answers=answers, watch_paths=args.watch)
        initialize = {
            "clientInfo": {"name": "codex_behavior_evaluation", "title": "Workflow behavior evaluation", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True, "optOutNotificationMethods": [
                "item/reasoning/summaryTextDelta", "item/reasoning/summaryPartAdded", "item/reasoning/textDelta",
            ]},
        }
        validate_known_request("v1/InitializeParams.json", initialize)
        client.rpc("initialize", initialize, timeout=60)
        client.notify("initialized", {})
        start = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": args.sandbox,
                 "ephemeral": True, "experimentalRawEvents": True}
        validate_known_request("v2/ThreadStartParams.json", start)
        response = client.rpc("thread/start", start, timeout=90)
        client.root_id = response["thread"]["id"]
        result["thread_id"] = client.root_id
        result["resolved_settings"] = {k: response.get(k) for k in ["model", "reasoningEffort", "approvalPolicy", "sandbox", "instructionSources"]}
        for text in [prompt, *turns]:
            completed = client.run_turn(text)
            result['turns'].append({'id': client.turn_id, 'status': completed.get('status'), 'error': completed.get('error')})
            result['turn_id'] = client.turn_id
            result['status'] = completed.get('status', 'unknown')
            result['turn_error'] = completed.get('error')
            if result['status'] != 'completed' or client.client_requests:
                break
        result['planned_turn_count'] = 1 + len(turns)
        result['answered_requests'] = client.answered_requests
        result['unused_answer_count'] = len(client.answer_fixtures)
        if result['unused_answer_count']:
            client.errors.append({'observation': 'unused_answer_fixtures'})
        snapshots = client.read_children()
        result["children"] = snapshots
        result["child_reports"] = public_child_reports(snapshots, client.public_messages, client.collab)
        result["native_subagent_activity"] = client.activities
        result['observed_execution_evidence'] = client.observed_execution_evidence
        result["native_collaboration_calls"] = list(client.collab.values())
        result["raw_collaboration_receipts"] = client.raw_collaboration_receipts
        result["public_messages"] = list(client.public_messages.values())
        root_messages = [m for m in client.public_messages.values() if m.get("thread_id") == client.root_id]
        final_messages = [m for m in root_messages if m.get("phase") == "final_answer"] or root_messages
        final = final_messages[-1]["text"] if final_messages else ""
        if not final:
            final = next((text for (thread_id, _), text in reversed(list(client.deltas.items())) if thread_id == client.root_id), "")
        (out / "final.md").write_text(redact_text(final), encoding="utf-8")
        result["child_reports_observed"] = [child_id for child_id, reports in result["child_reports"].items() if reports]
        result["unexpected_client_requests"] = client.client_requests
        result["observation_errors"] = client.errors
    except Exception as error:
        result["status"] = "runner_error"
        result["error"] = {"type": type(error).__name__, "message": str(error)[:2000]}
        if client and client.root_id and client.completed_turn is None:
            try:
                client.rpc("turn/interrupt", {"threadId": client.root_id, "turnId": client.turn_id}, timeout=5)
            except Exception:
                pass
    finally:
        if client:
            try:
                client.close()
            except Exception as error:
                result['status'] = 'runner_error'
                result['close_error'] = str(error)
            result['observation_errors'] = client.errors
            result['unexpected_client_requests'] = client.client_requests
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["config_hashes_after"] = {"global_instructions": sha(home / "AGENTS.md"), "user_config": sha(home / "config.toml")}
        result['profile_files_after'] = {str(p): sha(p) for p in profile_files}
        try:
            result['candidate_after'] = file_inventory(args.candidate_file)
            result['watched_after'] = file_inventory(args.watch)
        except (OSError, ValueError) as error:
            result['status'] = 'runner_error'
            result['inventory_error'] = str(error)
        (out / "result.json").write_text(json.dumps(safe_value(result), ensure_ascii=False, indent=2), encoding="utf-8")
    events_path = out / 'appserver-events.jsonl'
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()] if events_path.exists() else []
    assessment = assess_observation(result, criteria, events)
    (out / 'acceptance.json').write_text(json.dumps(safe_value(assessment), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({"status": result["status"], "result": str(out / "result.json"),
                      "child_report_count": len(result.get("child_reports_observed", [])),
                      "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False))
    if args.collection_only:
        return 0 if result['status'] == 'completed' else 1
    return 0 if assessment['status'] == 'passed' else 2


def self_test():
    assert safe_message({"method": "item/reasoning/textDelta", "params": {"delta": "private"}}) is OMIT
    assert safe_message({"method": "item/completed", "params": {"item": {"type": "reasoning", "summary": ["private"]}}}) is OMIT
    assert safe_value({"encrypted_content": "private", "items": [{"type": "reasoning"}, {"type": "agentMessage", "text": "public"}]}) == {"items": [{"type": "agentMessage", "text": "public"}]}
    assert COLLAB_NAMES.search("collaboration.spawn_agent")
    assert not COLLAB_NAMES.search("exec_command")
    reports = public_child_reports({"child": {"items": [{"item": {"id": "m", "type": "agentMessage", "text": "review result"}}]}}, {}, {})
    assert reports["child"][0]["text"] == "review result"
    validate_known_request("v2/ThreadStartParams.json", {"cwd": "C:/fixture", "approvalPolicy": "never", "sandbox": "workspace-write", "ephemeral": True, "experimentalRawEvents": True})
    validate_known_request("v2/TurnStartParams.json", {"threadId": "fixture", "input": [{"type": "text", "text": "fixture"}]})
    observer = AppServer.__new__(AppServer)
    observer.root_id, observer.turn_id = "parent", "turn"
    observer.activities, observer.child_ids = [], set()
    observer.collab, observer.raw_calls, observer.public_messages = {}, {}, {}
    observer.raw_collaboration_receipts, observer.thread_metadata = [], {}
    observer._observe({"method": "item/completed", "params": {
        "threadId": "parent", "item": {"type": "subAgentActivity", "id": "activity", "kind": "started", "agentThreadId": "child", "agentPath": "/root/reviewer"},
    }}, 1)
    observer._observe({"method": "rawResponseItem/completed", "params": {
        "threadId": "parent", "item": {"type": "function_call", "name": "spawn_agent", "call_id": "call", "arguments": "{}"},
    }}, 2)
    observer._observe({"method": "rawResponseItem/completed", "params": {
        "threadId": "parent", "item": {"type": "function_call_output", "call_id": "call", "output": '{"task_name":"/root/reviewer"}'},
    }}, 3)
    assert observer.child_ids == {"child"}
    assert observer.raw_collaboration_receipts[0]["call"]["name"] == "spawn_agent"
    print("Protocol/schema and reasoning-filter checks passed; no app-server or model was started.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        raise SystemExit(0)
    if '--assess-result' in sys.argv:
        parser = argparse.ArgumentParser(description='Review exact recorded evidence without starting an agent')
        parser.add_argument('--assess-result', required=True)
        parser.add_argument('--review-file', required=True)
        opts = parser.parse_args()
        raise SystemExit(assess_files(opts.assess_result, opts.review_file))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--codex-home")
    parser.add_argument('--codex-bin')
    parser.add_argument('--sandbox', choices=['read-only', 'workspace-write'], default='read-only')
    parser.add_argument('--collection-only', action='store_true', help='Collect evidence for an external assessor; exit zero does not mean accepted')
    parser.add_argument('--criteria-file')
    parser.add_argument('--turns-file')
    parser.add_argument('--answers-file')
    parser.add_argument('--candidate-file', action='append', default=[])
    parser.add_argument('--watch', action='append', default=[])
    parser.add_argument('--profile-label', default='current (not independently verified)')
    raise SystemExit(run(parser.parse_args()))
