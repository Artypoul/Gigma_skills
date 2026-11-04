from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = (Path(__file__).resolve().parents[1] / "fable-superpowers" /
          "scripts" / "profile_policy.py")
SPEC = importlib.util.spec_from_file_location("fable_superpowers_policy", SCRIPT)
assert SPEC and SPEC.loader
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "custom home with O'Brien"
        self.home.mkdir()
        self.root = self.home / "local-plugins" / "fable-superpowers"
        self.state = self.root / "updates"
        self.source = self.base / "cooperation.md"
        self.source.write_bytes(b"# Global agreements\r\n\r\nUse Fable and Superpowers.\r\n")
        self.target = self.home / "AGENTS.md"

    def install(self) -> dict:
        return policy.install_policy(self.home, self.source, self.state)

    def test_appends_managed_policy_preserving_unrelated_bytes_and_backup(self) -> None:
        original = b"\xef\xbb\xbf# My own rules\r\n\r\nKeep my settings.\r\n"
        self.target.write_bytes(original)
        result = self.install()
        self.assertTrue(result["changed"])
        self.assertEqual(result["mode"], "appended")
        self.assertTrue(self.target.read_bytes().startswith(original))
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        self.assertNotEqual(result["before_sha256"], result["after_sha256"])
        self.assertIn(policy.BEGIN_MARKER, self.target.read_bytes())
        state = json.loads((self.state / "policy-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["target"], str(self.target.resolve()))

    def test_new_home_gets_policy_without_copying_other_configuration(self) -> None:
        config = self.home / "config.toml"
        config.write_bytes(b"model = 'my-own-model'\r\n")
        result = self.install()
        self.assertEqual(result["mode"], "created")
        self.assertIsNone(result["backup"])
        self.assertEqual(config.read_bytes(), b"model = 'my-own-model'\r\n")

    def test_reapply_keeps_policy_and_state_bytes_identical(self) -> None:
        self.install()
        before = self.target.read_bytes()
        state_before = (self.state / "policy-state.json").read_bytes()
        result = self.install()
        self.assertFalse(result["changed"])
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual((self.state / "policy-state.json").read_bytes(), state_before)
        self.assertEqual(self.target.read_bytes().count(policy.BEGIN_MARKER), 1)

    def test_original_equivalent_full_policy_is_not_rewritten(self) -> None:
        original = self.source.read_bytes().replace(b"\r\n", b"\n") + b"\n"
        self.target.write_bytes(original)
        result = self.install()
        self.assertFalse(result["changed"])
        self.assertEqual(result["mode"], "existing-equivalent")
        self.assertEqual(self.target.read_bytes(), original)
        self.assertFalse(list(self.state.glob("backups/*")))
        self.assertFalse(self.install()["changed"])

    def test_exact_unmarked_fragment_is_not_duplicated(self) -> None:
        original = b"# Local rules\nRetain this.\n\n" + self.source.read_bytes() + b"\n# More\nRetain too.\n"
        self.target.write_bytes(original)
        self.assertFalse(self.install()["changed"])
        self.assertEqual(self.target.read_bytes(), original)
        self.source.write_bytes(b"# New cooperation policy\n")
        with self.assertRaises(policy.PolicyConflictError):
            self.install()
        self.assertEqual(self.target.read_bytes(), original)

    def test_source_update_changes_only_unmodified_owned_block(self) -> None:
        self.target.write_bytes(b"# Local before\r\n")
        self.install()
        first = self.target.read_bytes() + b"\r\n# Local after\r\n"
        self.target.write_bytes(first)
        before_block, _, after_block = first.partition(policy.BEGIN_MARKER)
        suffix = after_block.partition(policy.END_MARKER)[2]
        self.source.write_bytes(b"# Updated agreements\n\nUse the verified workflow.\n")
        result = self.install()
        updated = self.target.read_bytes()
        self.assertEqual(result["mode"], "updated")
        self.assertTrue(updated.startswith(before_block + policy.BEGIN_MARKER))
        self.assertTrue(updated.endswith(policy.END_MARKER + suffix))
        self.assertEqual(Path(result["backup"]).read_bytes(), first)
        self.assertIn(b"Use the verified workflow.", updated)

    def test_modified_owned_block_fails_closed_even_when_source_is_same(self) -> None:
        self.install()
        changed = self.target.read_bytes().replace(b"Use Fable", b"Use my edited Fable")
        self.target.write_bytes(changed)
        state_before = (self.state / "policy-state.json").read_bytes()
        with self.assertRaises(policy.PolicyConflictError):
            self.install()
        self.assertEqual(self.target.read_bytes(), changed)
        self.assertEqual((self.state / "policy-state.json").read_bytes(), state_before)

    def test_unowned_duplicate_and_incomplete_markers_fail_closed(self) -> None:
        block = policy.BEGIN_MARKER + b"\nOther policy\n" + policy.END_MARKER
        for original in (block, block + b"\n" + block, policy.BEGIN_MARKER + b"\n"):
            with self.subTest(original=original):
                self.target.write_bytes(original)
                with self.assertRaises(policy.PolicyConflictError):
                    self.install()
                self.assertEqual(self.target.read_bytes(), original)

    def test_corrupt_state_and_wrong_target_fail_closed(self) -> None:
        self.install()
        before = self.target.read_bytes()
        state_path = self.state / "policy-state.json"
        for value in ("broken-json", json.dumps({"schema_version": 1, "target": "another-home"})):
            with self.subTest(value=value):
                state_path.write_text(value, encoding="utf-8")
                with self.assertRaises(policy.PolicyConflictError):
                    self.install()
                self.assertEqual(self.target.read_bytes(), before)

    def test_compare_and_swap_preserves_concurrent_user_change(self) -> None:
        original = b"# Original user rules\n"
        concurrent = b"# User edited this while setup ran\n"
        self.target.write_bytes(original)
        read_optional = policy._read_optional
        target_reads = 0

        def inject_edit(path: Path) -> bytes | None:
            nonlocal target_reads
            if path == self.target.resolve():
                target_reads += 1
                if target_reads == 2:
                    path.write_bytes(concurrent)
            return read_optional(path)

        with patch.object(policy, "_read_optional", side_effect=inject_edit):
            with self.assertRaises(policy.PolicyConflictError):
                self.install()
        self.assertEqual(self.target.read_bytes(), concurrent)
        backups = list((self.state / "backups").glob("*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_backup_failure_prevents_policy_replacement(self) -> None:
        original = b"# Keep me\n"
        self.target.write_bytes(original)
        with patch.object(policy, "_backup", side_effect=OSError("backup unavailable")):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(self.target.read_bytes(), original)

    def test_failed_state_write_rolls_back_only_owned_replacement(self) -> None:
        original = b"# Original user policy\n"
        self.target.write_bytes(original)
        commit = policy._atomic_compare_and_swap

        def fail_state(path: Path, expected: bytes | None, replacement: bytes) -> None:
            if path.name == "policy-state.json":
                raise OSError("state unavailable")
            commit(path, expected, replacement)

        with patch.object(policy, "_atomic_compare_and_swap", side_effect=fail_state):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertFalse((self.state / "policy-state.json").exists())

    def test_failed_state_write_preserves_later_user_edit(self) -> None:
        self.target.write_bytes(b"# Original user policy\n")
        concurrent = b"# User's newer policy\n"
        commit = policy._atomic_compare_and_swap

        def fail_state(path: Path, expected: bytes | None, replacement: bytes) -> None:
            if path.name == "policy-state.json":
                self.target.write_bytes(concurrent)
                raise OSError("state unavailable")
            commit(path, expected, replacement)

        with patch.object(policy, "_atomic_compare_and_swap", side_effect=fail_state):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(self.target.read_bytes(), concurrent)

    def test_stale_lock_file_is_not_an_active_os_lock(self) -> None:
        self.state.mkdir(parents=True)
        lock_path = self.state / "policy-install.lock"
        lock_path.write_bytes(b"stale process receipt")
        self.assertTrue(self.install()["changed"])
        self.assertFalse(self.install()["changed"])
        self.assertTrue(lock_path.is_file())

    def test_real_os_lock_blocks_other_process_and_process_death_releases_it(self) -> None:
        self.state.mkdir(parents=True)
        helper = "\n".join((
            "import importlib.util, pathlib, sys",
            "spec = importlib.util.spec_from_file_location('policy_lock_helper', sys.argv[1])",
            "module = importlib.util.module_from_spec(spec)",
            "spec.loader.exec_module(module)",
            "with module._policy_lock(pathlib.Path(sys.argv[2])):",
            "    print('locked', flush=True)",
            "    sys.stdin.readline()",
        ))
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", helper, str(SCRIPT), str(self.state / "policy-install.lock")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(lambda: process.communicate(timeout=10))
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        self.assertEqual(process.stdout.readline().strip(), "locked")
        with self.assertRaises(policy.PolicyConflictError):
            self.install()
        self.assertFalse(self.target.exists())
        process.kill()
        process.communicate(timeout=10)
        self.assertTrue(self.install()["changed"])

    def test_crash_after_target_write_has_receipt_and_recovers_exact_new_snapshot(self) -> None:
        class SimulatedCrash(BaseException):
            pass

        self.target.write_bytes(b"# Existing local policy\n")
        commit = policy._atomic_compare_and_swap

        def crash_before_state(path: Path, expected: bytes | None, replacement: bytes) -> None:
            if path.name == "policy-state.json":
                journal = json.loads((self.state / "policy-journal.json").read_bytes())
                self.assertEqual(journal["after_sha256"], policy._sha(self.target.read_bytes()))
                raise SimulatedCrash()
            commit(path, expected, replacement)

        with patch.object(policy, "_atomic_compare_and_swap", side_effect=crash_before_state):
            with self.assertRaises(SimulatedCrash):
                self.install()
        after_crash = self.target.read_bytes()
        self.assertIn(policy.BEGIN_MARKER, after_crash)
        self.assertTrue((self.state / "policy-journal.json").is_file())
        result = self.install()
        self.assertTrue(result["recovered"])
        self.assertFalse(result["changed"])
        self.assertEqual(self.target.read_bytes(), after_crash)
        self.assertFalse((self.state / "policy-journal.json").exists())
        self.assertTrue((self.state / "policy-state.json").exists())

    def test_crash_before_target_write_recovers_exact_old_snapshot(self) -> None:
        class SimulatedCrash(BaseException):
            pass

        original = b"# Existing local policy\n"
        self.target.write_bytes(original)
        commit = policy._atomic_compare_and_swap

        def crash_before_target(path: Path, expected: bytes | None, replacement: bytes) -> None:
            if path == self.target:
                self.assertTrue((self.state / "policy-journal.json").is_file())
                raise SimulatedCrash()
            commit(path, expected, replacement)

        with patch.object(policy, "_atomic_compare_and_swap", side_effect=crash_before_target):
            with self.assertRaises(SimulatedCrash):
                self.install()
        self.assertEqual(self.target.read_bytes(), original)
        result = self.install()
        self.assertTrue(result["recovered"])
        self.assertTrue(result["changed"])

    def test_crash_recovery_rejects_unknown_body_and_retains_receipt(self) -> None:
        class SimulatedCrash(BaseException):
            pass

        commit = policy._atomic_compare_and_swap

        def crash_before_state(path: Path, expected: bytes | None, replacement: bytes) -> None:
            if path.name == "policy-state.json":
                raise SimulatedCrash()
            commit(path, expected, replacement)

        with patch.object(policy, "_atomic_compare_and_swap", side_effect=crash_before_state):
            with self.assertRaises(SimulatedCrash):
                self.install()
        unknown = self.target.read_bytes() + b"\n# User edited after the crash\n"
        self.target.write_bytes(unknown)
        journal_before = (self.state / "policy-journal.json").read_bytes()
        with self.assertRaises(policy.PolicyConflictError):
            self.install()
        self.assertEqual(self.target.read_bytes(), unknown)
        self.assertEqual((self.state / "policy-journal.json").read_bytes(), journal_before)
        self.assertFalse((self.state / "policy-state.json").exists())

    def test_crash_after_state_write_only_clears_proven_receipt(self) -> None:
        class SimulatedCrash(BaseException):
            pass

        discard = policy._discard_journal
        with patch.object(policy, "_discard_journal", side_effect=SimulatedCrash):
            with self.assertRaises(SimulatedCrash):
                self.install()
        original = self.target.read_bytes()
        original_state = (self.state / "policy-state.json").read_bytes()
        self.assertTrue((self.state / "policy-journal.json").exists())
        result = self.install()
        self.assertTrue(result["recovered"])
        self.assertFalse(result["changed"])
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual((self.state / "policy-state.json").read_bytes(), original_state)
        self.assertFalse((self.state / "policy-journal.json").exists())

    def test_crash_recovery_rejects_changed_state(self) -> None:
        class SimulatedCrash(BaseException):
            pass

        with patch.object(policy, "_discard_journal", side_effect=SimulatedCrash):
            with self.assertRaises(SimulatedCrash):
                self.install()
        original = self.target.read_bytes()
        state_path = self.state / "policy-state.json"
        state = json.loads(state_path.read_bytes())
        state["user_change"] = "preserve"
        changed_state = json.dumps(state).encode("utf-8")
        state_path.write_bytes(changed_state)
        with self.assertRaises(policy.PolicyConflictError):
            self.install()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(state_path.read_bytes(), changed_state)

    def test_symbolic_link_destination_fails_closed(self) -> None:
        other = self.base / "outside.md"
        other.write_bytes(b"# Outside\n")
        try:
            self.target.symlink_to(other)
        except OSError:
            self.skipTest("Symbolic links unavailable in this test environment")
        with self.assertRaises(policy.PolicyConflictError):
            self.install()
        self.assertEqual(other.read_bytes(), b"# Outside\n")


class AutomationTemplateTests(unittest.TestCase):
    def test_request_is_fresh_native_heartbeat_and_quotes_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            # Use a destination outside the running user's temp/home subtree.
            # No file is created: this API only returns a portable request.
            home = Path(Path(temporary).anchor) / Path(temporary).name / "O'Brien custom home"
            root = home / "local-plugins" / "fable-superpowers"
            request = policy.automation_request(home, root)
            self.assertEqual(request["kind"], "heartbeat")
            self.assertEqual(request["mode"], "create")
            self.assertEqual(request["status"], "ACTIVE")
            self.assertTrue(request["pending_native_tool"])
            self.assertIn("BYHOUR=10", request["rrule"])
            self.assertIn("BYMINUTE=0", request["rrule"])
            self.assertIn("O''Brien custom home", request["prompt"])
            self.assertIn("-Action run -CodexHome '", request["prompt"])
            self.assertIn("Update-Superpowers.ps1", request["prompt"])
            self.assertIn("automation-state.json", request["prompt"])
            self.assertIn("unchanged", request["prompt"])
            self.assertIn("busy", request["prompt"])
            self.assertIn("failure_signature", request["prompt"])
            self.assertFalse(home.exists())
            self.assertEqual(request["name"], policy.automation_request(home, root)["name"])
            self.assertNotEqual(request["name"], policy.automation_request(home / "other", root)["name"])
            for field in ("id", "targetThreadId", "thread_id", "automation_id", "projectId", "model"):
                self.assertNotIn(field, request)
            serialized = json.dumps(request)
            for old_identifier in ("C:\\\\Users\\\\Art", "01a1a583", "2026-11-04"):
                self.assertNotIn(old_identifier, serialized)

    def test_hour_is_local_and_validated(self) -> None:
        self.assertIn("BYHOUR=7", policy.automation_request(Path("destination"), Path("runtime"), hour=7)["rrule"])
        for hour in (-1, 24, True, "10"):
            with self.subTest(hour=hour):
                with self.assertRaises(ValueError):
                    policy.automation_request(Path("destination"), Path("runtime"), hour=hour)


if __name__ == "__main__":
    unittest.main()
