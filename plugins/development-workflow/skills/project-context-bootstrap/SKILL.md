---
name: project-context-bootstrap
description: Build a compact read-only repository context snapshot before code changes, code review, PR/merge/deploy work, debugging, handoff, resumed agent work, or checking another agent's changes. Trigger when the next action depends on project rules, product decisions, memory/history, current git/PR state, or local skill availability; for tiny self-contained tasks, keep the snapshot internal and report only blockers.
---

# Project Context Bootstrap

Use this skill as the first pass in any repository when project truth matters. Its job is to turn scattered files, git state, and prior decisions into one compact operating snapshot.

## Rules

- Read first, edit later.
- Prefer project-local rules over global habits.
- Treat missing context as a risk, not as permission to guess.
- Do not paste secrets, raw `.env` values, private remote URLs, or long logs into chat.
- Do not change files for read-only, review, audit, check-up, консилиум, or "посмотри/оцени" tasks unless the user explicitly asks to repair confirmed findings in the same request. A review-plus-fix request is changes-requested, but still does not authorize commit, push, PR, merge, deploy, or unrelated cleanup.
- Do not create `project-memory.md` or any other context file unless the user explicitly asks to initialize project context.
- Art's standing permission for every project (2026-09-15): an existing `project-memory.md` is operational agent memory, exempt from separate document-edit approval. Update it once at task completion from verified results of authorized changes, or correct stale facts during an assigned review-and-fix task. Earlier local document bans listing this file do not require renewed permission. Keep bootstrap and report-only tasks read-only; preserve unrelated dirty changes. This exception does not authorize creating missing memory, editing other documents or skills, changing product decisions, or commit/push, merge/deploy.

## Find The Project Root

Before reading context, resolve the project root:

```bash
git rev-parse --show-toplevel
```

If git root is unavailable, inspect only the current directory and its immediate child directories for a Git checkout. When exactly one child resolves to a Git root, use that nested root and record the container-to-repository mapping in the snapshot. When several children are repositories, use an explicit user path, canonical path in project rules/memory, or remote identity; if the choice is still ambiguous, stop and ask instead of scanning broadly or guessing. Use the current working directory as a fallback only when no repository can be resolved, and mark `Missing context: repo root unknown`. In monorepos or nested workspaces, also check for the nearest applicable `AGENTS.md` between the current directory and the root.

## Context Order

From the resolved project root, read files that exist:

1. `AGENTS.md`
2. `CLAUDE.md`
3. `project-memory.md`
4. `history.md` or `HISTORY.md`
5. `README.md` and nearby architecture docs such as `docs/architecture.md`, `docs/context.md`, `docs/business-logic.md`
6. Project-local skill indexes when relevant: list `.codex/skills`, `.agents/skills`, and `.claude/skills/README.md`; read only the `SKILL.md` files for skills selected by the task or router.

Read `AGENTS.md`, `project-memory.md`, and the top of `history.md` carefully enough to capture current decisions and blockers. If another file is large, use `rg` for targeted lookups and state what was not fully read.

## Git Snapshot

When inside a git repo, collect:

```bash
git status --short --branch
git log --oneline --decorate -5
git branch -vv
```

Cross-check any branch, PR, blocker, current-focus, and next-step claims in project memory against this Git snapshot and live PR evidence when available. A contradiction is `context_stale`, not permission to follow the stale instruction. During an explicitly requested context repair, update a clean target file from verified evidence. For report-only work or a target file with unrelated/unknown dirty changes, report the drift and do not overwrite it.

For PR-backed review, handoff of an existing PR, PR fix, PR finalization, merge, deploy, or "ready to merge/deploy?" work, PR/check/review evidence is mandatory. Prefer the strongest PR identifier available: user-supplied PR URL/number, then current branch PR, then `gh pr status` discovery. A local diff/code review with no PR uses Git state and relevant local checks; record PR evidence as `not applicable`, not unknown or blocking. If PR evidence is actually required but GitHub CLI is unavailable, the repository cannot be inferred, or access is missing, mark that evidence as unknown/blocking instead of guessing.

```bash
gh pr view <pr-url-or-number> --json url,state,headRefName,baseRefName,statusCheckRollup,reviewDecision
gh pr view --json url,state,headRefName,baseRefName,statusCheckRollup,reviewDecision
gh pr status
```

When working from a fork, detached worktree, or non-default remote, pass `--repo <owner/name>` to `gh` commands after deriving it from the PR URL or `gh repo view --json nameWithOwner`.

For dirty worktrees, classify files as current-task, pre-existing, generated, or unknown. Never reset or clean unrelated files. Before edits, if any target file is already dirty and its origin is unknown or pre-existing, enter `fail_closed`: show the exact dirty paths, the intended write allowlist, and the concrete collision risk, then ask one direct question. Do not write until Art answers that blocker explicitly after seeing those facts. A message about later review, PR, merge, deploy, or the broader goal does not authorize work over the named dirty files. If the answer is indirect, remain `fail_closed` and repeat only the unresolved question.

Redact private remotes, tokens, secrets in logs/history, raw PR output, and copied snippets.

## Output

Return a short block:

```text
CONTEXT SNAPSHOT
Project:
Product/current truth:
Branch/PR:
Dirty tree:
Relevant rules:
Active decisions:
Open blockers:
Missing context:
Next safe action:
Do not:
```

For small tasks, keep this internal and mention only blockers. For handoff, review, PR, merge, deploy, or agent-error checks, show the block.

## Initializing Context

Only when the user asks to create project memory, add a `project-memory.md` using `references/project-memory-template.md`. Keep it short: current truth, active decisions, open blockers, next step. Do not copy chat transcripts into it.
