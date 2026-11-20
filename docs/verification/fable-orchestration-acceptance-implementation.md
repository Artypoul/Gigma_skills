# Fable 5 orchestration acceptance — implementation evidence (2026-11-20)

## Scope, mode and immutable upstreams

Approved source: [plan PR #78](https://github.com/Artypoul/Gigma_skills/pull/78), `docs/superpowers/plans/2026-11-19-fable-orchestration-acceptance.md`.
Controller mode: `FABLE_MODE=chatgpt_github`; evidence here came from the connected GitHub integration and commit-specific GitHub Actions, **not** local Codex CLI/native live model trials.

Registry `main` at audit: `f9280206a20ccc9a47ebacff2c224833ce2889bd`.
Pinned Fable 5: `1.4.3`, full Git commit `cb76769f1fce9df196c22b2b708ba8474cbf5aa1`.
Pinned Superpowers: `7.0.2`, full Git commit `22f0b463e7a5e579904dd6211a520321035526f7`.
Pins and canonical skills were **not** changed. Therefore no new manifest version or Codex mirror modification was attempted.

## Previously completed before this execution

- [#79 / A1](https://github.com/Artypoul/Gigma_skills/pull/79) merged. Standard installation deduplication and regressions.
- [#80 / A2](https://github.com/Artypoul/Gigma_skills/pull/80) merged. Immutable baseline implementation unfortunately left the main branch with a syntax error in updater `compatibility.py`.
- [#81 / syntax recovery](https://github.com/Artypoul/Gigma_skills/pull/81) remains **open Draft** at `0a4dc2f07d53341496c1d4d030c3cad9f00892a1`, deletes 936 duplicated trailing lines. Six CI jobs passed on Actions run [44567679260](https://github.com/Artypoul/Gigma_skills/actions/runs/44567679260). No independent reviewer result was observed. The repair is **not merged into main**.

All subsequent PRs below form a **stacked chain** above #81. They must not be treated as independently mergeable into the broken main.

## New code and actual RED/GREEN

| Task | Draft PR | Final implementation commit (before this documentation) | RED observed | GREEN on same exact SHA |
| --- | --- | --- | --- | --- |
| A3 current independent review scope/chronology | [#82](https://github.com/Artypoul/Gigma_skills/pull/82) | `b7c78033463f95382d94f451f3b5e437e835dd8e` | SHA `80c8400ba759986f1472dc225fb5f1eca3dc0c49`, 136 tests, 2 failures and 3 errors | [44662845608](https://github.com/Artypoul/Gigma_skills/actions/runs/44662845608), 6/6 jobs |
| A4 actual skill bytes / provenance / pagination | [#83](https://github.com/Artypoul/Gigma_skills/pull/83) | `231f63e35bdd7e7d47d3e7dded9fcf57fa63fb27` | SHA `2e3db11411f64b8ec730e3e20e6620f73dda674d`, 142 tests, 10 failures | [44663894558](https://github.com/Artypoul/Gigma_skills/actions/runs/44663894558), 6/6 jobs |
| A6 test identity and final inventory freshness | [#84](https://github.com/Artypoul/Gigma_skills/pull/84) | `5bf4f4060370cb1983914f4cb261057d70fe08ca` | SHA `b5b5ab113b34485d55edbb4e90b8d9aa8b77fe6e`, 149 tests, 5 failures, 1 error; real Windows PowerShell Copy-Item scenario included | [44665495389](https://github.com/Artypoul/Gigma_skills/actions/runs/44665495389), 6/6 jobs |
| A5 independent semantic evidence | [#85](https://github.com/Artypoul/Gigma_skills/pull/85) | `74e7856a1ab510a2123fb837b96c177e6394bb96` | SHA `05e07ab431cce20815771861e67e5acaf4373a2d`, 155 tests, 3 failures and 5 errors | [44666365617](https://github.com/Artypoul/Gigma_skills/actions/runs/44666365617), 6/6 jobs |
| G2/G3 offline D1–D12 | [#86](https://github.com/Artypoul/Gigma_skills/pull/86) | `d724c03bdb4dd21805395fbbd8e6a08072dbc434` (prior to report) | SHA `2b8adbc75bd7c10957241868e6858c4dfa542e40`, 12 errors (missing evaluator) | [44667322612](https://github.com/Artypoul/Gigma_skills/actions/runs/44667322612), 12/12 tests passed on Ubuntu; overall workflow and Windows/full suite must be checked at final head |

### Behavior boundaries actually tested

- A3 tests a later Request changes overriding an earlier Approve, Markdown Important headings, full file SHA coverage, and fresh controller-observed test receipts. Strict review coverage is now wired into approved-plan assessment. **No actual independent human or `gpt-6.1-sol/xhigh` review has been received.**
- A4 reconstructs source text from paginated `read_skill` receipts, verifies the pinned raw file digest, exact content, provenance, offsets, warnings and `partial`; includes Windows and valid BOM/CRLF controls. These are **offline fixtures**, not a real installed skills read trial.
- A6 captures completed app-server command test identities and filesystem inventories and requires relevant RED→GREEN evidence. It also rejects unrelated arithmetic suite GREEN, changed tests/production after GREEN, and Windows `Copy-Item`. A later independent controller-run can establish current correctness; it does not retroactively create missing RED→GREEN history.
- A5 checks source/rubric/final-answer SHA binding and independent semantic criterion receipts. A wrong queue answer containing the right keywords no longer passes by those words alone. The offline positive review explicitly records `offline_fixture`; missing actual independent evaluation is **held**, not `passed`.
- G2/G3 adds 12 immutable contract JSON fixtures, separate test methods `test_D1_...` through `test_D12_...`, a hash-bound offline receipt adapter and Windows/Linux CI invocation. No live agent trials or observed in-flight cancellation were performed.

### Actual CI commands

GitHub Actions portable matrix runs:
```sh
python -B -m unittest discover -s codex-profile/tests -p "test_fable_superpowers_*.py"
python -B -m unittest discover -s codex-profile/tests -p "test_standard_profile.py" -v
python -B -m unittest discover -s codex-profile/tests -p "test_agent_acceptance_eval.py"
python -B -m unittest discover -s codex-profile/tests -p "test_owner_decision_acceptance.py" -v
# From codex-profile/fable-superpowers/scripts/updater:
python -B -m unittest -v test_core test_native test_source test_compatibility test_sandbox
```
The Linux `validate` job also executes `python validate_plugin.py`, marketplace tests, development-workflow tests, Codex mirror synchronization checks and other repository suites. Windows Standard profile test invokes real PowerShell when the runner supplies it (`REQUIRE_STANDARD_PROFILE_PWSH=1`). These are CI executions, **not** manual execution in the ChatGPT host.

## Open requirements and blockers

1. **Broken main** until #81 is independently reviewed and explicitly authorized for merge. No merge, deployment, force-push or auto-merge was done.
2. **Independent review:** required `gpt-6.1-sol/xhigh` subagent is unavailable in this connected GitHub-only host. The current PR code has not been approved by a separate actual reviewer. No self-review is represented as independent.
3. **Real installed Fable/Superpowers activation, real app-server agent trials and real semantic evaluation:** not available here. Therefore all live acceptance columns are open; synthetic D1–D12, mock review receipts and CI correctness do **not** demonstrate live agent behavior.
4. **G1 Task Acceptance delivery choice:** canonical `plugins/development-workflow/skills/agent-session-execution/SKILL.md` exists. Installer and assets were inspected but owner has not selected the delivery contract. No install, auto-switch, enabled/disabled preference mutation, dependency change or speculative route selected.
5. **G3 canonical handoff wording:** optional-risk-only `ready` clarification requires its expressly approved scope. Canonical skill, both manifests and `.codex` mirror were left unchanged; offline gates alone are not permission to rewrite them.
6. Final head, diff, comments/reviews and all CI jobs need to be checked **after** this report is committed. Green status on a prior SHA must not be attributed to the changed head.
7. In-flight steering/cancellation cannot be inferred from sequential offline fixture turns. No native steering lifecycle was observed.

**Acceptance state:** implementation PRs have substantial deterministic RED/GREEN evidence, but the overall #78 plan is **NOT READY / HELD** for independent review, live behavior and explicit owner/deployment gates.
