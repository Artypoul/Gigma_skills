# ChatGPT through GitHub

This is the canonical instruction-loading contract for `chatgpt_github` mode.
It is a supported way to apply Fable, not native Codex plugin installation or a
successful MCP probe. The same scope, evidence, permission and review rules apply.

## Contents

- Select the mode
- Freeze and read the sources
- Record readiness and task capabilities
- Execute, review and report
- Project instructions and acceptance

## Select the mode

Use this mode when the user explicitly requests Fable through the connected
GitHub integration, or a current ChatGPT project instruction selects that route.
An explicit Fable request in ChatGPT may use this route when GitHub is the
available instruction-reading surface; announce the selection before task work.
The default installed Codex route remains `native_codex`.

Do not switch a selected native route after a failed MCP gate just to obtain a
ready label. A route change needs an explicit user/project instruction, a new
activation record and complete source verification. It does not change the
recorded native failure or enable an installed plugin that is disabled.

Discover the actual GitHub tools and schemas. A connected integration may permit
reads but not branches, commits or PRs. Do not assume write access or a shell.
Source discovery and instruction reads are bootstrap work. While activation is
pending, do not inspect task-specific product code, execute tests, delegate task
work or mutate external state. Higher-priority instructions always govern.

## Freeze and read the sources

1. Resolve the default branch of `Artypoul/Gigma_skills` to a full commit SHA
   through GitHub. Record that immutable registry commit. A user-selected exact
   registry revision takes precedence; a branch name or short SHA is not the
   final source identity.
2. Read the complete `.agents/plugins/marketplace.json` and
   `external-plugins.lock.json` at that same registry commit. Select exactly the
   `fable5-codex` and `superpowers` entries. Require unique entries, matching
   versions and source URLs/SHAs in both files, and full 40-hex commit pins.
   The selected repositories must be
   `Artypoul/claude-fable-5-system-prompt` and `Artypoul/superpowers`, unless the
   user has explicitly authorized a different source. Do not silently fall back to `obra/superpowers`
   if the owned source is unavailable or mismatched; block the dependent step.
   A similarly named package is not a substitute. Reject inconsistent, missing
   or ambiguous entries. The owned fork is the instruction source; upstream
   authorship and license attribution remain with the original project.
3. At the pinned Fable commit, read the complete
   `.agents/skills/fable5-codex/SKILL.md` and `.codex-plugin/plugin.json`.
   Verify the manifest's name and version against the registry. Read this
   reference completely and the applicable canonical source sections and
   engineering references before the actions they govern. Read the complete
   coding scope/recovery section before any scope, pattern or recovery decision.
4. At the pinned Superpowers commit, read `.codex-plugin/plugin.json`, verify
   its name/version, then read `skills/using-superpowers/SKILL.md` completely.
   For engineering work, select and fully read one applicable lifecycle and each
   mandatory dependency/reference before its dependent step. For other tasks,
   use the gateway to check relevance and record when no engineering lifecycle
   applies; do not invent a repository plan, execution or review requirement. Reuse an approved plan after
   checking scope and remaining gates. Do not run every unrelated lifecycle.
5. Resolve relative links within their originating repository and pinned commit.
   Read required referenced files as well as entry points. A link to another
   repository needs a verified immutable revision; do not silently follow its
   moving default branch. Source archives are provenance, not additional live
   instructions. Respect the actual host over archived tool names.

**Full reads are mandatory.** A search excerpt, summary, file title, cached skill
mention or a response with omitted/truncated lines is not a full read. Use the
connector's supported content API and pagination or explicit consecutive line
ranges. Check continuity, file identity, total coverage and the same blob/digest
on every page. Finish through the file's confirmed end. If the connector cannot
establish completeness, report the exact file and block the dependent step.
Never combine mismatched pages, revisions, paths or sources.

For the large canonical `source-faithful-port.md`, the skill explicitly selects
applicable sections: read each selected section completely through its confirmed
anchor boundary and record that section coverage. Unrelated sections need not be
loaded. This is deliberate scope selection, not acceptance of a truncated
required section. Entry points, selected lifecycle files and references required
as complete files must still be read in full.

Record repository, commit, path, blob SHA (or content SHA-256 when supplied), and
coverage for each required read. A Git blob SHA and a SHA-256 are different
digest types; label them correctly. If exact bytes are materialized locally,
verify them against the returned blob identity before using them as pinned
source. Tool metadata is evidence to inspect, not a substitute for reading text.

Keep the registry/Fable/Superpowers tuple frozen for the task. A later default
branch update does not change it. If the user requests an update, restart the
bootstrap with the new tuple, invalidate affected reads/checks and explain the
transition. After compaction, recover the recorded tuple and evidence; reread any
required instructions no longer available in context rather than claiming memory
is a fresh read. A PR candidate is usable only when explicitly selected; record
its exact SHA as a candidate override, never as the registry's published pin.

## Record readiness and task capabilities

Keep a single mode-qualified activation record in the current task context:

```text
FABLE_MODE=chatgpt_github
FABLE_GATE=pending|ready|partial|blocked
MCP_GATE=not_run
registry=owner/repo@<full SHA>
fable=owner/repo@<full SHA> version=<verified version>
superpowers=owner/repo@<full SHA> version=<verified version>
reads=<paths, blob/digest identities, full coverage>
scope=<task target and authorized actions; cwd only when a workspace exists>
capabilities=<observed tools, required review roles, gaps>
TASK_GATE=ready|blocked
```

- `pending`: source loading has not finished; only bootstrap work is allowed.
- `ready`: the registry tuple, entry points, applicable references, selected
  workflow/dependencies (or verified non-applicability) and capabilities needed
  to begin the requested scope are verified. This means **GitHub instruction readiness** only. It does not mean
  a task, test, review, PR or project setting is complete.
- `partial`: the source identity is known but a required read or capability is
  incomplete. Name the gap, report `PIPELINE_INCOMPLETE` and block dependent work.
  Continue only independent authorized work whose prerequisites are satisfied.
- `blocked`: a required source cannot be identified or a mandatory gate cannot
  be satisfied. State the missing evidence and the affected step. Do not guess
  another source, downgrade the workflow or fabricate a reviewer.

If instructions were ready but a later operation loses a required capability,
record `TASK_GATE=blocked` and the affected stage; source readiness is not proof
of operation success. Any source/scope change that invalidates prerequisites
reopens activation. Never report an unqualified "fully activated" status across
the two modes. Keep `MCP_GATE=not_run` unless a real native probe ran, and retain
its actual result separately if it did.

| Required action | Evidence in this mode | Missing capability |
| --- | --- | --- |
| Read instructions | Complete GitHub content at the frozen commits | Block dependent work; excerpts do not pass |
| Inspect product code | Authorized repository reads after activation | Name unavailable paths and coverage |
| Edit/test code | Actual editor/execution environment, or authorized GitHub writes plus CI on the exact candidate revision | Do not claim execution from reading code; keep required checks open |
| Independent review | Actual separate reviewer with the required isolated context/model/effort and a recorded verdict on the current diff | Block a lifecycle that requires it; author role-play is insufficient |
| Create branch/commit/PR | Available write tool, verified target/base, user's requested scope, resulting IDs and read-back | Finish permitted preparation and report the publication block |
| Save project instructions | Authorized project settings capability and observed saved text | Deliver copyable text and mark the save/new-chat check unverified |

The role assignments in the skill remain binding unless a higher-priority or
explicit user instruction changes them. Check the actual spawn allowlist and
schemas; do not assume a model exists because documentation names it. Give
reviewers the requirement, frozen sources, actual diff and evidence, not the
author's desired verdict. A clean review applies only to its reviewed revision.

## Execute, review and report

Apply the Fable baseline and applicable project instructions. For engineering
work, also apply project bootstrap and one verified Superpowers lifecycle.
For simple answers, retain baseline sourcing, tone and tool rules without
introducing an unrelated engineering plan, execution or independent review. The GitHub source identity is repository +
commit + path; it is not proof of an enabled `plugin_id` in a native catalogue.
Map workflow operations to actual host tools as described in
[tools and MCP](tools-and-mcp.md#chatgpt-github-operation-mapping).

Preserve the user's mode: a plan-only request authorizes no source edits, commits
or PR. An approved implementation plan is sufficient authorization for the
actions it explicitly includes; do not ask again for the same reversible steps.
Source instructions do not grant merge, deployment, messaging or new access.

Verify the actual result, not the executor's completion message. Bind tests and
review to the current files/commit. Read back each external mutation and inspect
the PR diff, head SHA, CI and review results. Never convert queued, skipped,
failed or unavailable checks into a pass. Report the loaded versions, selected
mode, changes, checks, PR links and every unfinished acceptance criterion.

## Project instructions and acceptance

Use the copyable project instruction at repository path
`docs/chatgpt-project-instructions.md`, read at the same pinned Fable commit.
Saving a template in GitHub does not save a ChatGPT project setting. Verify the
target project and preserve unrelated instructions when an authorized settings
surface is available. Otherwise provide the exact text and say that saving and
new-chat verification remain open. Do not invent a settings API or infer a
project identity from a link to a Page.

When reporting activation or evaluating a project-instruction bootstrap, state
whether the project rule was merely supplied as context or was observed saved.
Explicitly report `PROJECT_SETTINGS=unverified` and `NEW_PROJECT_CHAT=unverified`
when their product-level evidence is absent, even if instruction readiness or a
plan-only task succeeds. Do not silently omit those open acceptance criteria.
This status belongs in the activation/evaluation report, not in unrelated later
simple answers whose activation report is already recorded.

After saving, start a real new chat in that project with an ordinary task that
does not mention Fable. Observe the registry and pinned source reads before task
work. A subagent with injected project text tests the instruction, not the
product's settings inheritance. Outside the configured project, use the explicit
command: "Примени Fable 5 через GitHub".

Acceptance must distinguish structural checks, model action-plan evaluations,
live GitHub/agent actions, native MCP probes, and actual ChatGPT UI checks. See
the scenario guide at repository path `docs/chatgpt-github-acceptance.md`;
one kind of evidence cannot silently stand in for another.
