from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "development-handoff"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "post_merge_cleanup.py"
SPEC = importlib.util.spec_from_file_location("post_merge_cleanup", SCRIPT_PATH)
assert SPEC and SPEC.loader
cleanup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cleanup
SPEC.loader.exec_module(cleanup)


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def commit_file(repo: Path, name: str, value: str, message: str) -> str:
    (repo / name).write_text(value, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class PostMergeCleanupTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.email", "tests@example.invalid")
        git(repo, "config", "user.name", "Skill Tests")
        commit_file(repo, "base.txt", "base\n", "base")
        return repo

    def test_preview_and_apply_delete_only_proven_safe_branches(self) -> None:
        repo = self.make_repo()

        git(repo, "switch", "-c", "merged-feature")
        commit_file(repo, "merged.txt", "merged\n", "merged feature")
        git(repo, "switch", "main")
        git(repo, "merge", "--ff-only", "merged-feature")

        git(repo, "switch", "-c", "squash-feature")
        squash_oid = commit_file(repo, "squash.txt", "source\n", "squash source")
        git(repo, "switch", "main")
        git(repo, "merge", "--squash", "squash-feature")
        git(repo, "commit", "-m", "squash merge")

        git(repo, "switch", "-c", "keep-unmerged")
        commit_file(repo, "keep.txt", "keep\n", "unmerged work")
        git(repo, "switch", "main")

        for relative in (
            ".playwright-cli/session.json",
            "playwright-report/index.html",
            "test-results/.last-run.json",
            "graphify-out/cache/graph.bin",
        ):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("generated\n", encoding="utf-8")

        git(repo, "config", "branch.merged-feature.description", "remove me")
        plan = cleanup.plan_cleanup(repo, "main", "squash-feature", squash_oid)
        decisions = {item.branch: item for item in plan.decisions}

        self.assertEqual(decisions["merged-feature"].action, "delete")
        self.assertEqual(decisions["squash-feature"].action, "force-delete")
        self.assertEqual(decisions["keep-unmerged"].action, "preserve")
        self.assertEqual(decisions["main"].action, "preserve")
        self.assertEqual(len(plan.ignored_dirty_entries), 4)

        digest = cleanup.plan_sha256(plan)
        self.assertEqual(digest, cleanup.plan_sha256(plan))
        deleted = cleanup.apply_cleanup(repo, plan)

        self.assertEqual(set(deleted), {"merged-feature", "squash-feature"})
        self.assertEqual(set(git(repo, "branch", "--format=%(refname:short)").splitlines()), {"main", "keep-unmerged"})
        config_probe = subprocess.run(
            ["git", "config", "--local", "--get-regexp", "^branch\\.merged-feature\\."],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(config_probe.returncode, 1)

    def test_non_generated_dirty_entry_blocks_cleanup(self) -> None:
        repo = self.make_repo()
        (repo / "product.txt").write_text("not generated\n", encoding="utf-8")

        with self.assertRaisesRegex(cleanup.CleanupError, "blocking dirty entries"):
            cleanup.plan_cleanup(repo, "main", None, None)

    def test_changed_generated_entries_invalidate_preview(self) -> None:
        repo = self.make_repo()
        git(repo, "switch", "-c", "merged-feature")
        commit_file(repo, "merged.txt", "merged\n", "merged feature")
        git(repo, "switch", "main")
        git(repo, "merge", "--ff-only", "merged-feature")
        first = repo / "test-results" / "first.json"
        first.parent.mkdir(parents=True)
        first.write_text("one\n", encoding="utf-8")
        plan = cleanup.plan_cleanup(repo, "main", None, None)

        second = repo / ".playwright-cli" / "second.json"
        second.parent.mkdir(parents=True)
        second.write_text("two\n", encoding="utf-8")
        with self.assertRaisesRegex(cleanup.CleanupError, "changed after planning"):
            cleanup.apply_cleanup(repo, plan)

    def test_advanced_verified_head_is_preserved(self) -> None:
        repo = self.make_repo()
        git(repo, "switch", "-c", "feature")
        verified_oid = commit_file(repo, "feature.txt", "first\n", "verified head")
        commit_file(repo, "later.txt", "later\n", "later local work")
        git(repo, "switch", "main")

        plan = cleanup.plan_cleanup(repo, "main", "feature", verified_oid)
        decision = next(item for item in plan.decisions if item.branch == "feature")
        self.assertEqual(decision.action, "preserve")
        self.assertEqual(decision.reason, "local branch advanced after verified PR head")


if __name__ == "__main__":
    unittest.main()
