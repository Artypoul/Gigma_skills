"""Run one ordinary task via the installed app-server protocol.

Current user configuration and global instructions are preserved. The runner
creates one ephemeral, workspace-write evaluation thread. Reasoning items and
encrypted fields are discarded before logging; native tool/delegation receipts
and public messages are retained for independent inspection.
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
            cleaned = safe_value(child)
            if cleaned is not OMIT:
                result[key] = cleaned
        return result
    if isinstance(value, list):
        return [cleaned for child in value if (cleaned := safe_value(child)) is not OMIT]
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
    def __init__(self, cwd: Path, out: Path, deadline: float, codex_home: Path | None = None):
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("Codex executable is unavailable on PATH")
        env = os.environ.copy()
        env.pop("CODEX_THREAD_ID", None)
        if codex_home is not None:
            env['CODEX_HOME'] = str(codex_home)
        env['FABLE5_CODEX_BIN'] = codex
        self.stderr = (out / "appserver-stderr.log").open("wb")
        self.events = (out / "appserver-events.jsonl").open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [codex, "app-server", "--stdio", "-c", "features.prefer_mxc=true",
             "-c", "sandbox_workspace_write.writable_roots=[]"], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.deadline = deadline
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
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()

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
        self.client_requests.append({"event_line": line, "method": method, "params": safe_value(message.get('params', {}))})
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
        self.stderr.close()


def public_child_reports(snapshots, messages, collab):
    reports = {}
    for child_id, snapshot in snapshots.items():
        found = {}
        for message in messages.values():
            if message.get("thread_id") == child_id:
                found[message["id"]] = message
        for turn in snapshot.get("thread", {}).get("turns", []):
            for item in turn.get("items", []):
                if item.get("type") == "agentMessage":
                    found[item["id"]] = item
        for entry in snapshot.get("items", []):
            item = entry.get("item", {})
            if item.get("type") == "agentMessage":
                found[item["id"]] = item
        for call in collab.values():
            state = call.get("agentsStates", {}).get(child_id, {})
            if state.get("message"):
                found["collab:" + call["id"]] = {
                    "text": state["message"], "status": state.get("status"),
                    "source": "native_collab_agent_state", "event_line": call["event_line"],
                }
        reports[child_id] = list(found.values())
    return reports


def run(args):
    cwd = Path(args.cwd).resolve(strict=True)
    prompt_path = Path(args.prompt_file).resolve(strict=True)
    out = Path(args.out_dir).resolve()
    if not cwd.is_dir():
        raise ValueError("--cwd must be an existing directory")
    out.mkdir(parents=True, exist_ok=False)
    prompt = prompt_path.read_text(encoding="utf-8")
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")
    home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    before = {"global_instructions": sha(home / "AGENTS.md"), "user_config": sha(home / "config.toml")}
    started = time.monotonic()
    client = None
    result = {"status": "starting", "cwd": str(cwd), "config_hashes_before": before}
    try:
        client = AppServer(cwd, out, started + args.timeout_seconds, codex_home=home)
        initialize = {
            "clientInfo": {"name": "codex_behavior_evaluation", "title": "Workflow behavior evaluation", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True, "optOutNotificationMethods": [
                "item/reasoning/summaryTextDelta", "item/reasoning/summaryPartAdded", "item/reasoning/textDelta",
            ]},
        }
        validate_known_request("v1/InitializeParams.json", initialize)
        client.rpc("initialize", initialize, timeout=60)
        client.notify("initialized", {})
        start = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "workspace-write",
                 "ephemeral": True, "experimentalRawEvents": True}
        validate_known_request("v2/ThreadStartParams.json", start)
        response = client.rpc("thread/start", start, timeout=90)
        client.root_id = response["thread"]["id"]
        result["thread_id"] = client.root_id
        result["resolved_settings"] = {k: response.get(k) for k in ["model", "reasoningEffort", "approvalPolicy", "sandbox", "instructionSources"]}
        turn = {"threadId": client.root_id, "input": [{"type": "text", "text": prompt}]}
        validate_known_request("v2/TurnStartParams.json", turn)
        response = client.rpc("turn/start", turn, timeout=90)
        client.turn_id = response["turn"]["id"]
        result["turn_id"] = client.turn_id
        while client.completed_turn is None:
            client.pump()
        result["status"] = client.completed_turn.get("status", "unknown")
        result["turn_error"] = client.completed_turn.get("error")
        snapshots = client.read_children()
        result["children"] = snapshots
        result["child_reports"] = public_child_reports(snapshots, client.public_messages, client.collab)
        result["native_subagent_activity"] = client.activities
        result["native_collaboration_calls"] = list(client.collab.values())
        result["raw_collaboration_receipts"] = client.raw_collaboration_receipts
        result["public_messages"] = list(client.public_messages.values())
        root_messages = [m for m in client.public_messages.values() if m.get("thread_id") == client.root_id]
        final_messages = [m for m in root_messages if m.get("phase") == "final_answer"] or root_messages
        final = final_messages[-1]["text"] if final_messages else ""
        if not final:
            final = next((text for (thread_id, _), text in reversed(list(client.deltas.items())) if thread_id == client.root_id), "")
        (out / "final.md").write_text(final, encoding="utf-8")
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
            client.close()
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["config_hashes_after"] = {"global_instructions": sha(home / "AGENTS.md"), "user_config": sha(home / "config.toml")}
        (out / "result.json").write_text(json.dumps(safe_value(result), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "result": str(out / "result.json"),
                      "child_report_count": len(result.get("child_reports_observed", [])),
                      "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 1


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--codex-home")
    raise SystemExit(run(parser.parse_args()))
