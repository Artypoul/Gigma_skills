---
name: development-handoff
description: "Manage development handoff between Codex agents: mandatory post-merge finalization with safe local merged-branch cleanup, same-PR fixes, monster review gates, decision-lock/product-drift checks, prod-ready checks, deploy checks, dirty worktree safety, recovery-aware handoff, and continuation from evidence. Use immediately, before an acknowledgment-only response, when the user unambiguously reports a completed merge with merged/смерджил/PR смержен or a contextually merge-specific залил; also use for post-merge/после мерджа/финализацию после мерджа/cleanup branches/почисти ветки, fix in PR/чини в PR, monster review/монстр ревью, prod ready/продак реди, update branches/обнови ветки, deploy/деплой, handoff/передай смену, decision drift/уехал от решения/свернул от решения, or when continuing an interrupted development task."
---

# Development Handoff

Use this skill to keep a development task coherent across agents, PR reviews, merge, deploy and interruptions. A handoff is not a memory dump; it is the next agent's operating state.

Golden rule: inspect repository and PR evidence before acting from memory.

When the current task is in recovery after user criticism, carry forward the failed assumption, the active source of truth, and the exact next proof step. Do not hand off only a story about what happened.

## Quick Snapshot

When inside a git repository, run the bundled read-only helper first:

Resolve bundled script paths relative to this `SKILL.md`.

```bash
python scripts/handoff_snapshot.py --repo <repo-path>
```

Default helper output redacts absolute local paths and remote URLs. Use `--show-paths` only for local diagnostics and do not paste that output into chat, docs or PR comments.

If a PR number or URL is known:

```bash
python scripts/handoff_snapshot.py --repo <repo-path> --pr 123
```

If the helper is unavailable, gather the same facts manually:

```bash
git status --short --branch
git branch -vv
git log --oneline --decorate -5
gh pr view --json url,state,mergedAt,headRefName,baseRefName,statusCheckRollup,reviewDecision
```

Read `references/handoff-contract.md` when you need the full template, exact command recipes, prod-ready checklist, or skill/plugin installability checks.

## Hard Trigger Guard

Before composing the first response to a user message, classify an unambiguous merge-completion phrase (`смерджил`, `merged`, `PR смержен`, or `залил` only when the context clearly means merge) as an execution trigger. This guard has priority over treating the message as a status update and over the generic clarification-first rule when repository/PR identity is discoverable.

On a positive trigger:

1. Load this skill and start Quick Snapshot in the same turn when repository/PR identity is discoverable from current context.
2. Do not send an acknowledgment-only final response.
3. Do not stop after saying that merge does not authorize deploy; preserve that boundary while still completing post-merge finalization.
4. Return a final response only with one globally allowed status: `ready` after a verified result, or evidence-backed `partial`, `blocked`, or `unknown`.

Do not trigger on a negation, hypothetical, or question such as `ещё не смерджил`, `если смерджим`, or `как смержить?`. A stop command still takes precedence. Read `references/evaluation-scenarios.md` when validating or changing this trigger.

## Interpret User Commands

Treat short user phrases as process triggers after applying the Hard Trigger Guard:

- `смерджил`, `merged`, `PR смержен`, contextually merge-specific `залил`, `после мерджа`, `финализация после мерджа` -> run the complete post-merge protocol in the same turn, including safe local branch cleanup; never acknowledge and stop.
- `чини в PR`, `чини там же`, `не вижу правки в PR` -> reuse the existing PR branch.
- `монстр ревью`, `monster review`, `сделай ревью` -> run findings-first review and track fixes.
- `продак реди?`, `prod ready?` -> answer only after the prod-ready evidence gate.
- `обнови ветки`, `origin?` -> fetch/prune and compare local vs remote without losing dirty work.
- `деплой` -> follow deploy checks; do not drift into unrelated work.
- `стоп`, `не туда`, `не меняй` -> stop immediately.
- `не то`, `wrong`, `off-spec`, `nothing changed`, `not from the design` -> stop the old path, rebuild the evidence snapshot, and switch to `feedback-recovery` before more edits.

Do not ask for clarification when the safe next protocol is obvious.

## Post-Merge Protocol

When the user says the PR was merged, treat that message as the trigger for this whole protocol. Do not acknowledge the merge and stop before finalization.

1. Verify live PR state and exact branch identity with `gh pr view <id> --json state,mergedAt,mergeCommit,url,headRefName,headRefOid,baseRefName`. Continue only when `state` is `MERGED` and `mergedAt` is present.
2. Run `git fetch --all --prune`.
3. Check dirty worktree before switching branches. Tracked, staged, unknown, or product files still block switching and cleanup; known generated local artifacts may be left in place when they do not affect branch refs.
4. Switch to the base branch and run `git pull --ff-only` only when safe.
5. Check `git status --short --branch` and latest commits.
6. Resolve `scripts/post_merge_cleanup.py` relative to this `SKILL.md`. Run it without `--apply` using the verified `baseRefName`, `headRefName`, and `headRefOid`; inspect every proposed deletion and preservation, then retain the returned `plan_sha256`.
7. If the preview is safe, rerun the command with `--apply --expected-plan-sha256 <plan_sha256>`. Stop and inspect a new preview if the plan changed. The user's current explicit merge statement authorizes this exact local cleanup only after steps 1–6 succeed. Do not infer authorization from stale chat, CI, or an observed merge alone.
8. Verify that the base branch remains current, deleted local branches are absent, preserved branches remain, and remote-tracking refs were not mutated by cleanup. If the helper returns `partial` or `unknown`, stop, read back the named refs/config, report the exact state, and never retry deletion blindly.
9. Check GitHub Actions or required workflows for the merge commit.
10. If the task involved deploy, check deploy workflow and runtime health using the repository runbook.
11. Return a short handoff: merged item, updated base, deleted local branches, preserved/blocking branches, checks, remaining blockers, next action.

The cleanup helper removes only:

- the exact local PR head when its tip equals the verified `headRefOid`; this also handles squash/rebase merges without deleting later local commits;
- every other local branch when Git proves its tip is an ancestor of the updated base.

It must preserve `main`, the base branch, blocking dirty worktrees, unmerged or advanced branches, branches checked out in another worktree, and all remote/remote-tracking branches. The helper may ignore only its explicit allowlist of untracked generated artifact directories; those ignored entries are included in the preview hash and any change before apply requires a fresh preview. Apply must match the exact preview hash and delete refs in one compare-and-swap transaction so plan drift or one stale branch cannot cause partial cleanup. Never replace a blocked helper result with broad `git branch -D`, `git push --delete`, a wildcard, or a cross-shell deletion command.

```bash
python <skill-dir>/scripts/post_merge_cleanup.py --repo <repo-path> --base <baseRefName> --merged-head <headRefName> --merged-head-oid <headRefOid>
python <skill-dir>/scripts/post_merge_cleanup.py --repo <repo-path> --base <baseRefName> --merged-head <headRefName> --merged-head-oid <headRefOid> --apply --expected-plan-sha256 <plan_sha256>
```

Queued or unavailable checks are not green.

## Fix Existing PR Protocol

When the user asks to fix a PR:

1. Identify the current PR and branch from git/gh evidence.
2. If the PR is open, patch that branch. Do not create a new PR.
3. Read review comments, checks and failing logs before editing.
4. Fix the cause and adjacent same-pattern issues.
5. Stage only files belonging to the current task.
6. Push to the same branch.
7. Re-check CI and review comments after the push.

If the PR is already merged or closed, explain that state and only then decide whether a follow-up PR is needed.

## Review Gate

For monster review or serious review:

1. Start with findings ordered by severity.
2. Ground each finding in file/line evidence.
3. Include risk and one-sentence fix.
4. Compare the diff against locked decisions from the plan, PR body, contract docs, review comments and user messages.
5. Treat silent drift from an accepted product or compatibility decision as a real finding, even when CI is green.
6. If P1/P2 findings are real and the user asked to fix, fix them in the same PR.
7. Re-run relevant checks and re-read review comments after push.

Do not call a PR ready while a real P1/P2 remains open.

## Decision Lock And Product Drift

Before plan -> code, review -> fix, merge-ready, deploy-ready, or any recovery after user criticism, lock the accepted decisions from evidence. Use source docs, the active plan, PR body, PR comments, explicit user messages, compatibility tests, and named contracts.

Build a tiny internal map:

```text
decision | source | must preserve | what would break it | approval status
```

Treat these as locked unless the user explicitly changes them:

- public API, payload, auth, permissions, runtime contract, DB/migration behavior, old data compatibility, feature scope, rollout phase, and agent autonomy;
- tests that prove accepted compatibility or legacy behavior;
- PR/body/source-doc statements that say a client, runner, endpoint, old record, or user flow stays compatible.

If implementation would change a locked decision, stop before editing and ask for an explicit decision change:

```text
DECISION CHANGE REQUEST
Current locked decision:
Proposed change:
Why it seems needed:
What breaks:
Options:
Recommended option:
```

Do not rewrite docs or tests to make an unapproved behavior look accepted. Do not call an unapproved change a "contract decision". If the user says the agent drifted from an accepted decision, switch to `feedback-recovery`, find the winning source of truth, and make the smallest correction that restores it.

## Prod-Ready Gate

Before answering "ready":

- repo, branch, PR and base branch are known;
- local dirty tree does not contaminate the task;
- tests or equivalent checks were run and named;
- CI/review state is known after the last push;
- deploy workflow/health is checked when deploy is in scope;
- no secrets, tokens, private paths or credentials were printed or committed;
- handoff includes the next required action.

If any item is unknown, answer "not ready yet" or "ready with this explicit risk".

## Dirty Worktree

When there are local changes:

1. Classify them as current-task, pre-existing, generated, or unknown.
2. Never reset, checkout, clean, move, or overwrite unrelated changes without direct permission.
3. Stage only current-task files.
4. If dirty files block branch update or PR continuation, report the exact blocker. Allowlisted generated untracked artifacts may be reported as ignored by cleanup, but must not be deleted unless the user separately asks for filesystem cleanup.
5. Mention left-over dirty files in the final handoff.

Broad dirty trees after a failed frontend or design transfer are a recovery smell. Do not hide that state; call it out and reduce scope before more implementation.

## Product And Scope Constraints

Explicit user decisions steer the workflow until changed:

- "only <scope>" means stay inside that scope.
- "this product decision is fixed" means do not redesign it unless asked.
- "same PR" means no new PR.
- "do not ask" means act from evidence when risk is low.

Architectural cleanup, security hardening, or "better design" does not override a locked product decision. If preserving the decision is unsafe, pause and explain the concrete risk instead of silently changing the product behavior.

If a user constraint conflicts with security, money, production data, destructive git operations, or deploy safety, pause and explain the risk.

## Skill/Plugin Work

When changing reusable skills or plugins:

1. Confirm ownership: generic workflow skills belong in a generic workflow plugin, not in a domain plugin.
2. Add or update both machine manifests required by the catalogue.
3. Update marketplace discovery entries when a plugin is added, moved or removed.
4. Run the mirror sync script.
5. Validate the skill and the catalogue.
6. Do not store private chat transcripts, secrets or product-specific incident text in the skill.

If the skill change came from a failure, encode the reusable guardrail, not the private drama of the thread.

## Final Handoff

End meaningful work with this compact block:

```text
HANDOFF
Workspace: <repo name or redacted local path>
Branch:
PR:
State:
Last evidence:
Failed assumption:
Winning source of truth:
User constraints:
Decision lock:
Open blockers:
Next required action:
Do not:
```

Keep chat output short; put long audit trails in PR comments or PR body.
