# Development Handoff Contract

Use this reference when a software development task crosses agent turns, PR review cycles, merge, deploy, or dirty worktree states. Keep the handoff generic and evidence-based.

## Handoff Block

```text
HANDOFF
Workspace: <repo name or redacted local path>
Task: <one sentence>
Branch: <current branch and tracking state>
PR: <url, number, state>
Base: <base branch and latest known commit>
State: planning | coding | review | waiting-merge | merged | deployed | blocked
Last evidence:
- git:
- tests:
- checks:
- reviews:
- deploy:
Failed assumption:
- <what the previous agent believed that is now known wrong, or "none known">
Winning source of truth:
- <artifact or rule that now decides the task>
User constraints:
- <constraint that must steer the next agent>
Decision lock:
- <accepted product/API/runtime/compatibility decisions that must not change without explicit approval>
Open blockers:
- <real blocker or "none known">
Next required action:
- <one concrete action>
Do not:
- <specific things the next agent must not do>
```

## Command Recipes

### Baseline Snapshot

```bash
git status --short --branch
git branch -vv
git log --oneline --decorate -5
git remote
```

If GitHub CLI is configured:

```bash
gh pr view --json url,state,mergedAt,headRefName,baseRefName,statusCheckRollup,reviewDecision
gh pr checks --watch --interval 10
```

For a known PR:

```bash
gh pr view <number> --json url,state,mergedAt,mergeCommit,headRefName,baseRefName,statusCheckRollup,reviewDecision
gh pr diff <number> --name-only
```

Read PR comment bodies only when needed for review/fix work. Read remote URLs only when needed for local diagnostics. Do not paste raw bodies, remote URLs, absolute local paths, secrets, tokens, credentials, or long logs into chat or handoff output; summarize findings and redact sensitive details.

### Post-Merge

```bash
gh pr view <number> --json url,state,mergedAt,mergeCommit,headRefName,headRefOid,baseRefName
git fetch --all --prune
git switch <base-branch>
git pull --ff-only
git status --short --branch
git log --oneline --decorate -5
python <skill-dir>/scripts/post_merge_cleanup.py --repo <repo-path> --base <baseRefName> --merged-head <headRefName> --merged-head-oid <headRefOid>
python <skill-dir>/scripts/post_merge_cleanup.py --repo <repo-path> --base <baseRefName> --merged-head <headRefName> --merged-head-oid <headRefOid> --apply --expected-plan-sha256 <plan_sha256>
git branch -vv
```

If the worktree is dirty, classify it before switching or pulling. Tracked, staged, unknown, or product files block branch cleanup; allowlisted generated untracked artifacts may stay in place and be ignored by the cleanup helper. Run the helper relative to the loaded skill directory. Preview before applying, and pass its exact `plan_sha256`; any plan drift, including changed ignored dirty entries, requires a new preview. Never delete a remote branch, a branch with unmerged commits after the verified PR head, or a branch occupied by another worktree. Apply uses one compare-and-swap ref transaction so one stale branch blocks the whole ref cleanup without partial deletion. A `partial` or `unknown` result requires read-back and forbids blind retry.

### Fix Existing PR

```bash
git fetch --all --prune
gh pr view <number> --json url,state,headRefName,baseRefName,statusCheckRollup,reviewDecision
git switch <headRefName>
git status --short --branch
```

After patching:

```bash
git diff --check
git status --short
git add <only-current-task-files>
git commit -m "<message>"
git push
gh pr checks <number> --watch --interval 10
```

### Skill/Plugin Installability

When a skill or plugin is added, moved, renamed or removed, verify:

- plugin manifest exists for each supported runtime;
- marketplace entry exists for each supported runtime;
- plugin `version`, `description`, `skills`, interface metadata and default prompt are not placeholders;
- fallback mirror is regenerated from canonical plugin files;
- catalogue validation passes.

## Prod-Ready Checklist

Answer "ready" only when:

- current branch and PR state are known;
- local worktree does not mix unrelated changes into the task;
- CI/checks are completed or their unavailable state is explained;
- tests or equivalent validation were run and results are named;
- review comments were read after the last push;
- accepted product, API, runtime, data-compatibility and rollout decisions are preserved, or an explicit user-approved decision change is linked/named;
- deploy health was checked when deploy is in scope;
- no secrets, tokens, private paths, or credentials were printed or committed;
- handoff names the next required action.

## Decision-Lock Review

Use this check before coding, after review fixes, and before merge-ready/deploy-ready status:

```text
decision | source | must preserve | changed by this diff? | approval
```

Sources include explicit user messages, the active plan, PR body, review comments, contract docs, runbooks, and compatibility tests. Compatibility tests that assert accepted old behavior are product evidence; do not rewrite them just to match a new implementation.

Stop and request an explicit decision change before changing:

- public API, payloads, auth, permissions, runtime contract or agent permissions;
- DB/migration behavior, old records, queued jobs, rollout phase or backward compatibility;
- feature scope, ownership boundary, source of truth, or the user's accepted product behavior.

Use this format:

```text
DECISION CHANGE REQUEST
Current locked decision:
Proposed change:
Why it seems needed:
What breaks:
Options:
Recommended option:
```

Do not call an unapproved drift a "contract decision". Green CI does not approve product drift.

## Intent Map

| User phrase | Required behavior |
| --- | --- |
| `смерджил`, `merged`, `PR смержен`, contextually merge-specific `залил`, `финализация после мерджа` | Run the complete post-merge protocol; verify PR state, update base, safely remove merged local working branches, and check workflows. Do not acknowledge and stop. |
| `чини в PR`, `там же` | Reuse current PR branch; do not create a new PR. |
| `сделай монстр ревью` | Findings-first review, then fix P1/P2 if asked. |
| `продак реди?` | Run prod-ready check; answer from evidence. |
| `обнови ветки`, `origin?` | Fetch/prune and compare local vs remote without losing dirty work. |
| `деплой` | Follow deploy runbook/checks; do not drift into unrelated code. |
| `стоп`, `не туда` | Stop current workflow immediately. |
| `не то`, `wrong`, `nothing changed` | Stop the old fix path, rebuild evidence, and route through recovery before more edits. |

Negations, hypotheticals and questions such as `ещё не смерджил`, `если смерджим` and `как смержить?` are not post-merge triggers. A stop command has priority over every process trigger. The final task status must remain one of `ready`, `partial`, `blocked`, or `unknown`; verified merge evidence is what permits `ready`, not a separate `verified` status.

## Failure Patterns To Prevent

- Treating `merged` as a chat note instead of a post-merge trigger.
- Updating the base branch but leaving the verified merged local working branch behind.
- Using broad force-delete or remote branch deletion instead of exact previewed local cleanup.
- Applying a newly calculated cleanup set that was not the exact preview the user inspected.
- Creating a new PR when the user asked to fix the existing PR.
- Declaring "ready" while a review/check is still queued.
- Reopening a product decision after the user explicitly froze it.
- Blocking on allowlisted generated untracked artifacts, or mixing unrelated dirty-tree changes into the current commit.
- Relying on memory instead of reading PR comments, checks, and branch state.
- Switching domains after the user narrowed scope.
- Reporting deploy success without checking workflow or health evidence.
- Handing off a recovery task without naming the failed assumption or the winning source of truth.
- Rewriting docs or tests to ratify a behavior change that was never approved.
- Treating architectural cleanup or security hardening as permission to break an accepted compatibility or rollout decision.

## Output Style

For the user:

```text
Сделал post-merge protocol.
- PR: merged
- base branch: updated to <commit>
- deleted local branches: <list/none>
- preserved branches: <list and reason/none>
- checks: <status>
- dirty tree: <clean/dirty>
- next: <action>
```

For PR comments or long handoff notes, include the full `HANDOFF` block.
