#!/usr/bin/env python3
"""Safely remove merged local working branches after a verified PR merge."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.dont_write_bytecode = True


class CleanupError(RuntimeError):
    """Raised when cleanup cannot be proved safe."""


class CleanupUnknownError(RuntimeError):
    """Raised when a write outcome cannot be proved safely."""


class CleanupPartialError(RuntimeError):
    """Raised when refs were deleted but related local config cleanup failed."""

    def __init__(self, message: str, deleted: list[str]) -> None:
        super().__init__(message)
        self.deleted = deleted


@dataclass(frozen=True)
class BranchDecision:
    branch: str
    oid: str
    action: str
    reason: str


@dataclass(frozen=True)
class CleanupPlan:
    base: str
    base_oid: str
    merged_head: str | None
    merged_head_oid: str | None
    ignored_dirty_entries: tuple[str, ...]
    decisions: tuple[BranchDecision, ...]


GENERATED_DIRTY_PREFIXES = (
    ".playwright-cli/",
    "playwright-report/",
    "test-results/",
    "graphify-out/",
)


def run(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "git command failed"
        raise CleanupError(detail)
    return proc.stdout.strip()


def normalize_status_path(path: str) -> str:
    normalized = path.strip().strip('"').replace("\\", "/")
    return normalized if normalized.endswith("/") else normalized + "/"


def ignored_generated_dirty_entries(repo: Path) -> tuple[str, ...]:
    output = run(repo, "status", "--porcelain=1")
    if not output:
        return ()

    ignored: list[str] = []
    blocking: list[str] = []
    for line in output.splitlines():
        if len(line) < 4:
            blocking.append(line)
            continue

        status = line[:2]
        path = line[3:]
        normalized_path = normalize_status_path(path)
        is_generated_untracked = status == "??" and any(
            normalized_path.startswith(prefix) for prefix in GENERATED_DIRTY_PREFIXES
        )
        if is_generated_untracked:
            ignored.append(line)
        else:
            blocking.append(line)

    if blocking:
        names = ", ".join(blocking[:8])
        suffix = "" if len(blocking) <= 8 else f", ... (+{len(blocking) - 8} more)"
        raise CleanupError(f"worktree has blocking dirty entries; classify before branch cleanup: {names}{suffix}")
    return tuple(sorted(ignored))


def local_branches(repo: Path) -> dict[str, str]:
    output = run(
        repo,
        "for-each-ref",
        "--format=%(refname:short)\t%(objectname)",
        "refs/heads/",
    )
    result: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            continue
        branch, oid = line.split("\t", 1)
        result[branch] = oid
    return result


def worktree_branches(repo: Path) -> set[str]:
    output = run(repo, "worktree", "list", "--porcelain")
    prefix = "branch refs/heads/"
    return {line[len(prefix) :] for line in output.splitlines() if line.startswith(prefix)}


def is_ancestor(repo: Path, branch: str, base: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, base],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if proc.returncode not in {0, 1}:
        raise CleanupError(proc.stderr.strip() or "git merge-base failed")
    return proc.returncode == 0


def plan_cleanup(
    repo: Path,
    base: str,
    merged_head: str | None,
    merged_head_oid: str | None,
) -> CleanupPlan:
    if not (repo / ".git").exists() and not run(repo, "rev-parse", "--git-dir"):
        raise CleanupError("repository is not a Git worktree")

    current = run(repo, "branch", "--show-current")
    if current != base:
        raise CleanupError(f"switch to base branch {base!r} before cleanup; current={current!r}")

    ignored_dirty = ignored_generated_dirty_entries(repo)

    branches = local_branches(repo)
    if base not in branches:
        raise CleanupError(f"base branch {base!r} does not exist locally")
    base_oid = branches[base]

    occupied = worktree_branches(repo)
    protected = {base, "main"}
    decisions: list[BranchDecision] = []

    for branch, oid in sorted(branches.items()):
        if branch in protected:
            decisions.append(BranchDecision(branch, oid, "preserve", "protected base branch"))
            continue
        if branch in occupied:
            decisions.append(
                BranchDecision(branch, oid, "preserve", "checked out in a worktree")
            )
            continue

        verified_pr_head = branch == merged_head
        if verified_pr_head and merged_head_oid and oid == merged_head_oid:
            if is_ancestor(repo, oid, base_oid):
                decisions.append(BranchDecision(branch, oid, "delete", "merged into base"))
            else:
                decisions.append(
                    BranchDecision(
                        branch,
                        oid,
                        "force-delete",
                        "exact headRefOid of verified merged PR (squash/rebase-safe)",
                    )
                )
            continue

        if verified_pr_head and merged_head_oid and oid != merged_head_oid:
            if is_ancestor(repo, oid, base_oid):
                decisions.append(
                    BranchDecision(
                        branch,
                        oid,
                        "delete",
                        "all later local commits also merged into base",
                    )
                )
            else:
                decisions.append(
                    BranchDecision(
                        branch,
                        oid,
                        "preserve",
                        "local branch advanced after verified PR head",
                    )
                )
            continue

        if is_ancestor(repo, oid, base_oid):
            decisions.append(BranchDecision(branch, oid, "delete", "merged into base"))
            continue

        decisions.append(BranchDecision(branch, oid, "preserve", "unmerged branch"))

    return CleanupPlan(
        base=base,
        base_oid=base_oid,
        merged_head=merged_head,
        merged_head_oid=merged_head_oid,
        ignored_dirty_entries=ignored_dirty,
        decisions=tuple(decisions),
    )


def plan_sha256(plan: CleanupPlan) -> str:
    payload = {
        "base": plan.base,
        "base_oid": plan.base_oid,
        "merged_head": plan.merged_head,
        "merged_head_oid": plan.merged_head_oid,
        "ignored_dirty_entries": list(plan.ignored_dirty_entries),
        "decisions": [asdict(decision) for decision in plan.decisions],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def remove_branch_configs(repo: Path, branches: list[str]) -> None:
    failures: list[str] = []
    for branch in branches:
        pattern = rf"^branch\.{re.escape(branch)}\."
        probe = subprocess.run(
            ["git", "config", "--local", "--get-regexp", pattern],
            cwd=repo,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if probe.returncode == 1:
            continue
        if probe.returncode != 0:
            failures.append(branch)
            continue
        remove = subprocess.run(
            ["git", "config", "--local", "--remove-section", f"branch.{branch}"],
            cwd=repo,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if remove.returncode != 0:
            failures.append(branch)
    if failures:
        raise CleanupPartialError(
            f"branch refs were deleted but local config cleanup failed: {', '.join(failures)}",
            branches,
        )


def apply_cleanup(repo: Path, plan: CleanupPlan) -> list[str]:
    targets = [
        decision
        for decision in plan.decisions
        if decision.action in {"delete", "force-delete"}
    ]
    if not targets:
        return []

    current_branch = run(repo, "branch", "--show-current")
    if current_branch != plan.base:
        raise CleanupError(
            f"current branch changed after planning: expected={plan.base!r}, actual={current_branch!r}"
        )
    current_ignored_dirty = ignored_generated_dirty_entries(repo)
    if current_ignored_dirty != plan.ignored_dirty_entries:
        raise CleanupError("ignored dirty entries changed after planning; inspect a new preview")

    occupied = worktree_branches(repo)
    newly_occupied = sorted(decision.branch for decision in targets if decision.branch in occupied)
    if newly_occupied:
        raise CleanupError(f"branch became occupied by a worktree: {', '.join(newly_occupied)}")

    current = local_branches(repo)
    stale = sorted(
        decision.branch
        for decision in targets
        if current.get(decision.branch) != decision.oid
    )
    if stale:
        raise CleanupError(f"branch changed after planning: {', '.join(stale)}")

    commands = [f"verify refs/heads/{plan.base} {plan.base_oid}"]
    commands.extend(
        f"delete refs/heads/{decision.branch} {decision.oid}" for decision in targets
    )
    commands.append("")
    proc = subprocess.run(
        ["git", "update-ref", "--stdin"],
        cwd=repo,
        input="\n".join(commands).encode("utf-8"),
        capture_output=True,
        check=False,
    )
    try:
        after = local_branches(repo)
    except (CleanupError, FileNotFoundError) as exc:
        raise CleanupUnknownError(f"cannot read back branch cleanup outcome: {exc}") from exc
    remaining = [decision for decision in targets if decision.branch in after]
    if proc.returncode != 0:
        raw_detail = proc.stderr.strip() or proc.stdout.strip()
        detail = raw_detail.decode("utf-8", errors="replace") or "git ref transaction failed"
        unchanged = all(after.get(decision.branch) == decision.oid for decision in targets)
        if unchanged:
            raise CleanupError(detail)
        raise CleanupUnknownError(f"branch cleanup outcome is unknown: {detail}")
    if remaining:
        names = ", ".join(sorted(decision.branch for decision in remaining))
        raise CleanupUnknownError(f"Git reported success but branches remain: {names}")
    deleted = [decision.branch for decision in targets]
    try:
        remove_branch_configs(repo, deleted)
    except CleanupPartialError:
        raise
    except (CleanupError, FileNotFoundError) as exc:
        raise CleanupPartialError(f"branch refs were deleted but config cleanup failed: {exc}", deleted) from exc
    return deleted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--merged-head")
    parser.add_argument("--merged-head-oid")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-sha256")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    try:
        plan = plan_cleanup(
            repo,
            args.base,
            args.merged_head,
            args.merged_head_oid,
        )
        digest = plan_sha256(plan)
        if args.apply:
            if not args.expected_plan_sha256:
                raise CleanupError("--apply requires --expected-plan-sha256 from preview")
            if not hmac.compare_digest(digest, args.expected_plan_sha256.lower()):
                raise CleanupError("cleanup plan changed after preview; inspect a new preview")
            deleted = apply_cleanup(repo, plan)
        else:
            if args.expected_plan_sha256:
                raise CleanupError("--expected-plan-sha256 is valid only with --apply")
            deleted = []
    except CleanupPartialError as exc:
        print(
            json.dumps(
                {
                    "status": "partial",
                    "base": plan.base,
                    "plan_sha256": digest,
                    "error": str(exc),
                    "deleted": exc.deleted,
                },
                ensure_ascii=False,
            )
        )
        return 4
    except CleanupUnknownError as exc:
        print(
            json.dumps(
                {
                    "status": "unknown",
                    "base": plan.base,
                    "plan_sha256": digest,
                    "error": str(exc),
                },
                ensure_ascii=False,
            )
        )
        return 3
    except (CleanupError, FileNotFoundError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2

    payload = {
        "status": "applied" if args.apply else "preview",
        "base": plan.base,
        "base_oid": plan.base_oid,
        "plan_sha256": digest,
        "deleted": deleted,
        "ignored_dirty_entries": list(plan.ignored_dirty_entries),
        "decisions": [asdict(decision) for decision in plan.decisions],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
