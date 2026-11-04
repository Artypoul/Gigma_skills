"""Portable cooperation policy and destination-native heartbeat request.

Only AGENTS.md and the supplied policy state directory are changed by
``install_policy``. ``automation_request`` is read-only: the destination agent
must use the native automation tool to inspect/deduplicate/create its heartbeat.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid


BEGIN_MARKER = b"<!-- BEGIN GIGMA FABLE-SUPERPOWERS COOPERATION POLICY -->"
END_MARKER = b"<!-- END GIGMA FABLE-SUPERPOWERS COOPERATION POLICY -->"
_MARKER_IDENTITY = b"FABLE-SUPERPOWERS COOPERATION POLICY"
_STATE_VERSION = 1


class PolicyConflictError(RuntimeError):
    """Ownership, state or compare-and-swap could not be proved safe."""


def _sha(value: bytes | None) -> str | None:
    return hashlib.sha256(value).hexdigest() if value is not None else None


def _read_optional(path: Path) -> bytes | None:
    if path.is_symlink():
        raise PolicyConflictError(f"Refusing symbolic-link policy or state: {path}")
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _normalise(value: bytes) -> str:
    try:
        return value.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    except UnicodeDecodeError as error:
        raise PolicyConflictError("The cooperation policy and AGENTS.md must be UTF-8.") from error


def _contains_policy(existing: bytes, source: str) -> bool:
    text = _normalise(existing)
    return ("\n" + source + "\n") in ("\n" + text + "\n")


def _marker_span(existing: bytes) -> tuple[int, int] | None:
    begins, ends = existing.count(BEGIN_MARKER), existing.count(END_MARKER)
    if not begins and not ends:
        if _MARKER_IDENTITY in existing:
            raise PolicyConflictError("Conflicting cooperation policy marker; preserving AGENTS.md.")
        return None
    if begins != 1 or ends != 1 or existing.count(_MARKER_IDENTITY) != 2:
        raise PolicyConflictError("Duplicate or incomplete cooperation policy markers; preserving AGENTS.md.")
    start, end = existing.index(BEGIN_MARKER), existing.index(END_MARKER) + len(END_MARKER)
    if (end <= start or (start and existing[start - 1:start] not in (b"\n", b"\r"))
            or (end < len(existing) and existing[end:end + 1] not in (b"\n", b"\r"))):
        raise PolicyConflictError("Conflicting cooperation policy marker boundaries; preserving AGENTS.md.")
    return start, end


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_compare_and_swap(path: Path, expected: bytes | None, replacement: bytes) -> None:
    """Check the read snapshot again immediately before atomic replacement.

    This detects intervening edits, including creation of a previously absent
    file. The install lock serializes this installer's own concurrent writers.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(replacement)
            output.flush()
            os.fsync(output.fileno())
        if _read_optional(path) != expected:
            raise PolicyConflictError(f"File changed concurrently; no replacement performed: {path}")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _backup(state_dir: Path, before: bytes) -> Path:
    directory = state_dir / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / ("AGENTS." + _sha(before)[:16] + "." + uuid.uuid4().hex + ".bak")
    with backup.open("xb") as output:
        output.write(before)
        output.flush()
        os.fsync(output.fileno())
    return backup


def _load_state(raw: bytes | None, target: Path) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        if (not isinstance(value, dict) or value.get("schema_version") != _STATE_VERSION
                or value.get("target") != str(target)
                or value.get("mode") not in ("managed", "existing-equivalent")
                or not isinstance(value.get("source_sha256"), str)
                or len(value["source_sha256"]) != 64
                or (value["mode"] == "managed" and
                    (not isinstance(value.get("block_sha256"), str) or len(value["block_sha256"]) != 64))):
            raise ValueError("Invalid state shape or target")
        return value
    except (ValueError, UnicodeDecodeError) as error:
        raise PolicyConflictError("Invalid policy ownership state; preserving AGENTS.md.") from error


@contextmanager
def _policy_lock(path: Path):
    """An existing lock file is harmless; the OS releases locks on process death."""
    if path.is_symlink():
        raise PolicyConflictError(f"Refusing symbolic-link policy lock: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
            os.fsync(lock.fileno())
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            raise PolicyConflictError("Another policy installation is running.") from error
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def _discard_journal(path: Path, expected: bytes) -> None:
    if _read_optional(path) != expected:
        raise PolicyConflictError("Policy recovery receipt changed concurrently; preserving it.")
    path.unlink()


def _valid_hash(value, optional: bool = False) -> bool:
    return ((optional and value is None) or
            (isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)))


def _recover_policy_journal(target: Path, state_dir: Path) -> bool:
    """Complete only a transaction whose exact old/new snapshots are known.

    The journal is flushed before AGENTS.md is changed. It stores hashes of
    both possible target/state snapshots and the intended ownership receipt;
    no unknown document body or edited state is adopted during recovery.
    """
    journal_path = state_dir / "policy-journal.json"
    raw_journal = _read_optional(journal_path)
    if raw_journal is None:
        return False
    try:
        journal = json.loads(raw_journal)
        if (not isinstance(journal, dict) or journal.get("schema_version") != _STATE_VERSION
                or journal.get("target") != str(target)
                or not _valid_hash(journal.get("before_sha256"), optional=True)
                or not _valid_hash(journal.get("after_sha256"))
                or not _valid_hash(journal.get("state_before_sha256"), optional=True)
                or not _valid_hash(journal.get("state_after_sha256"))
                or not isinstance(journal.get("next_state"), dict)):
            raise ValueError("Invalid journal shape")
        desired_state = _json_bytes(journal["next_state"])
        _load_state(desired_state, target)
        if _sha(desired_state) != journal["state_after_sha256"]:
            raise ValueError("Journal state hash mismatch")
    except (ValueError, UnicodeDecodeError, TypeError) as error:
        raise PolicyConflictError("Invalid policy recovery receipt; preserving policy and state.") from error
    current = _read_optional(target)
    current_hash = _sha(current)
    state_path = state_dir / "policy-state.json"
    current_state = _read_optional(state_path)
    current_state_hash = _sha(current_state)
    if (current_hash not in (journal["before_sha256"], journal["after_sha256"])
            or current_state_hash not in (journal["state_before_sha256"], journal["state_after_sha256"])):
        raise PolicyConflictError("Policy or ownership state changed after interruption; preserving the recovery receipt.")
    if current_hash == journal["after_sha256"]:
        # The target is exactly the verified intended replacement. Finish only
        # its matching metadata, never an unrelated ownership-state edit.
        if current_state != desired_state:
            _atomic_compare_and_swap(state_path, current_state, desired_state)
    elif current_state_hash != journal["state_before_sha256"]:
        raise PolicyConflictError("Policy and ownership recovery snapshots disagree; preserving both.")
    # Exact old snapshots mean the target mutation never took place (or was
    # safely rolled back). Discard the receipt and retry the normal install.
    _discard_journal(journal_path, raw_journal)
    return True


def install_policy(home: Path, policy_source: Path, state_dir: Path) -> dict:
    """Append/update a bounded, owned fragment without replacing user rules.

    Exact existing unmarked policy is left in place and recorded as unowned;
    future source changes then require manual integration. A marked block can
    be updated only when its exact recorded bytes still match. Every existing
    AGENTS.md mutation has a durable backup, a recovery journal and a final
    snapshot comparison. Interrupted writes recover only exact old/new bytes.
    """
    home, state_dir = Path(home).expanduser().resolve(), Path(state_dir).expanduser().resolve()
    target = home / "AGENTS.md"
    source = _normalise(Path(policy_source).read_bytes())
    if not source.strip() or _MARKER_IDENTITY.decode() in source:
        raise PolicyConflictError("The cooperation policy source is empty or contains reserved markers.")
    source_hash = _sha(source.encode("utf-8"))
    block = BEGIN_MARKER + b"\n" + source.encode("utf-8") + b"\n" + END_MARKER
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "policy-install.lock"
    with _policy_lock(lock_path):
        recovered = _recover_policy_journal(target, state_dir)
        before = _read_optional(target)
        state_path = state_dir / "policy-state.json"
        raw_state = _read_optional(state_path)
        state = _load_state(raw_state, target)
        current = before or b""
        span = _marker_span(current)
        if span is not None:
            if state is None or state["mode"] != "managed":
                raise PolicyConflictError("Marked policy has no matching ownership record; preserving AGENTS.md.")
            start, end = span
            if _sha(current[start:end]) != state["block_sha256"]:
                raise PolicyConflictError("Managed cooperation policy was modified; preserving AGENTS.md.")
            after = current[:start] + block + current[end:]
            mode = "unchanged" if after == before else "updated"
            state_mode = "managed"
        elif state is not None and state["mode"] == "managed":
            raise PolicyConflictError("Recorded managed policy is missing; preserving AGENTS.md.")
        elif state is not None and state["source_sha256"] != source_hash:
            raise PolicyConflictError("Previously unmarked policy requires manual integration of the new source.")
        elif _contains_policy(current, source):
            after, mode, state_mode = current, "existing-equivalent", "existing-equivalent"
        elif state is not None:
            raise PolicyConflictError("Previously equivalent unmarked policy was modified; preserving AGENTS.md.")
        else:
            separator = b"" if not current else (b"\n" if current.endswith((b"\n", b"\r")) else b"\n\n")
            after = current + separator + block + b"\n"
            mode, state_mode = ("created" if before is None else "appended"), "managed"
        next_state = {"schema_version": _STATE_VERSION, "target": str(target),
                      "mode": state_mode, "source_sha256": source_hash}
        if state_mode == "managed":
            next_state["block_sha256"] = _sha(block)
        next_state_bytes = _json_bytes(next_state)
        changed = after != before
        backup = _backup(state_dir, before) if changed and before is not None else None
        if changed or next_state_bytes != raw_state:
            journal_path = state_dir / "policy-journal.json"
            journal = _json_bytes({
                "schema_version": _STATE_VERSION, "target": str(target),
                "before_sha256": _sha(before), "after_sha256": _sha(after),
                "state_before_sha256": _sha(raw_state), "state_after_sha256": _sha(next_state_bytes),
                "next_state": next_state,
            })
            _atomic_compare_and_swap(journal_path, None, journal)
            try:
                if changed:
                    _atomic_compare_and_swap(target, before, after)
                if next_state_bytes != raw_state:
                    _atomic_compare_and_swap(state_path, raw_state, next_state_bytes)
            except Exception:
                # Normal errors roll back only our proven replacement while
                # ownership state is still old. Process death/interruptions
                # leave the durable journal for exact-snapshot recovery.
                if changed and _read_optional(target) == after and _read_optional(state_path) == raw_state:
                    if before is None:
                        target.unlink()
                    else:
                        _atomic_compare_and_swap(target, after, before)
                raise
            _discard_journal(journal_path, journal)
        return {"changed": changed, "mode": mode, "path": str(target),
                "before_sha256": _sha(before), "after_sha256": _sha(after),
                "backup": str(backup) if backup is not None else None,
                "state": str(state_path), "recovered": recovered}


def _powershell_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def automation_request(home: Path, root: Path, hour: int = 10) -> dict:
    """Return a fresh, deduplicatable destination-thread heartbeat template.

    No automation IDs, thread IDs, account settings or scheduler files are
    imported. Paths are derived only from the supplied destination paths.
    """
    if type(hour) is not int or not 0 <= hour <= 23:
        raise ValueError("The local schedule hour must be an integer between 0 and 23.")
    home, root = Path(home).expanduser().resolve(), Path(root).expanduser().resolve()
    home_key = hashlib.sha256(os.path.normcase(str(home)).encode("utf-8")).hexdigest()[:12]
    name = f"Fable + Superpowers maintenance ({home_key})"
    launcher = root / "maintenance" / "Update-Superpowers.ps1"
    state_path = root / "updates" / "automation-state.json"
    command = f"& {_powershell_literal(launcher)} -Action run -CodexHome {_powershell_literal(home)}"
    prompt = (
        f"Maintain the verified Fable + Superpowers installation for Codex home {home}. "
        f"Run this PowerShell command in the destination Windows environment: {command}\n\n"
        "Wait for this one process to finish; do not start a second update while it is running. "
        "Retain the updater's verification, independent review, immutable version, rollback and crash recovery gates. "
        "Do not bypass a failed or unavailable gate, change authorization, or call models outside the updater's contract. "
        f"Read and maintain durable heartbeat evidence at {state_path}. "
        "Use fields schema_version, home, last_result, failure_signature, last_notified_signature, and evidence_paths; "
        "preserve existing unrelated fields and write updates atomically. Record the actual exit status and report paths. "
        "For a missing state file, initialize it from this run without importing state from any other machine. "
        "If the updater reports unchanged, busy, or held with new_failure=false, stay quiet. "
        "Exclude timestamps, temporary paths and run identifiers from failure signatures. For repeated failures, compare failure_signature with "
        "last_notified_signature and stay quiet after the first notice while the same failure remains. "
        "Notify only for a meaningful installation change, completion of an update, a new failure, or required user action; "
        "persist the notified signature so subsequent runs can deduplicate. Never invent a successful update or review."
    )
    return {
        "mode": "create", "kind": "heartbeat", "name": name, "prompt": prompt,
        "rrule": f"FREQ=DAILY;BYHOUR={hour};BYMINUTE=0;BYSECOND=0", "status": "ACTIVE",
        "pending_native_tool": True, "native_tool": "automation_update",
        "schedule_timezone": "destination local time", "state_path": str(state_path),
        "deduplication": {
            "home_key": home_key, "kind": "heartbeat", "name": name,
            "match_prompt_paths": [str(home), str(launcher)],
            "instruction": "Inspect destination native automations first. Preserve the existing matching heartbeat's "
                           "recurrence, timezone and ACTIVE/PAUSED state unless the user explicitly requests a change. "
                           "The template's ACTIVE status and requested recurrence apply only to a new heartbeat. Reuse/update a matching heartbeat; "
                           "create one fresh heartbeat in the destination chat only when no match exists. "
                           "Pass native heartbeat fields only; omit this template's metadata. "
                           "Do not copy another machine's automation ID, thread ID or scheduler TOML.",
        },
    }
