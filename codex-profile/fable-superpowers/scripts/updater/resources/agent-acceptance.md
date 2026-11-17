# Task acceptance observations

`appserver_eval.py` collects public native events from one ephemeral thread. It does not change the active global profile. `--profile-label` is descriptive metadata, not proof that a profile was installed. Before/after configuration hashes and `resolved_settings` identify the actual observed environment.

Default execution is read-only. Use `--sandbox workspace-write` only for an authorized disposable fixture. A failed write attempt is still a read-only violation. The mechanical checker deliberately leaves shell and external tool effects unverified; reviewing those effects is required before calling the read-only scenario accepted.

Example (paths are local fixture paths):

```text
python -B appserver_eval.py --cwd FIXTURE --prompt-file task.txt --out-dir NEW_RUN_DIRECTORY --criteria-file criteria.json --candidate-file SKILL.md --candidate-file PROFILE.md --watch FIXTURE
```

The binary can be provided with `--codex-bin`. Discovery checks `FABLE5_CODEX_BIN`, PATH, then the application's embedded executable. An invalid explicit selection fails instead of silently choosing another binary.

`--turns-file` accepts a JSON list of subsequent synthetic user messages. Each starts after the preceding turn completes, in the same thread. An unhandled interactive request or unsuccessful turn stops the script. Inputs represent a test scenario, not actual owner permission. Expected conclusions and acceptance criteria are never included in the agent's prompt automatically.

`--answers-file` accepts exact-match non-secret question fixtures using the native response shape:

```json
[{"questions":[{"id":"target","header":"Target","question":"Which fixture?"}],"answers":{"target":{"answers":["A"]}}}]
```

All question fields must equal the received request in the current thread and turn. Unknown questions are recorded as unhandled; tool approval requests are never granted. Unused answers make the observation unsuccessful.

Criteria are separate from the agent's inputs:

```json
{"mechanical":["completed","delegation","activation_before_delegation"],"semantic":["correct_target","preserved_goal","fresh_evidence","honest_final"]}
```

Supported mechanical criteria: `completed`, `delegation`, `activation_before_delegation`, `read_only`. Unknown/duplicate criteria are errors. `completed` proves only a native turn ended; it cannot establish a correct conclusion. Mandatory criteria have four possible states: `satisfied`, `violated`, `not_checked`, `not_applicable`. Missing evidence and an inapplicable mandatory criterion leave acceptance `incomplete`. Any violation makes it `failed`. Only all satisfied criteria produce `passed`.

The activation check requires same-root, same-cwd native Fable discovery/read/status receipts before the first observed delegation, matching catalogue/identity/content hashes and complete skill bodies. Unsupported event shapes leave evidence unverified; assistant prose never establishes readiness. A native child start, completion and final report establish delegation, not correctness of the child's work.

After collection, an independent reviewer evaluates semantics and supplies a JSON file with `reviewer`, `result_sha256`, `events_sha256`, `criteria_sha256`, and `criteria` (mapping semantic IDs to `{ "status": "satisfied|violated|not_checked|not_applicable", "evidence": "specific public evidence" }`). Hashes bind this review to that exact run. Use:

```text
python -B appserver_eval.py --assess-result RUN/result.json --review-file review.json
```

The command checks the current candidate/profile hashes and creates `acceptance-reviewed.json` without overwriting earlier evidence. This is an audit binding, not authentication of the reviewer; preserve the actual reviewer/session receipt alongside it. Changed candidate or profile files invalidate acceptance. Re-run affected scenarios after material changes. A reviewer may resolve an unverified `read_only` criterion with explicit tool-effect evidence; the assessment retains its mechanical `not_checked` status and labels the semantic decision separately. A mechanical violation can never be overridden.

`result.json` remains the native observation, `acceptance.json` the initial mechanical assessment. Default exit zero means declared criteria passed; exit 2 means not accepted. `--collection-only` preserves legacy collection behavior (zero for native completion); its exit status explicitly makes no acceptance claim. The updater compatibility workflow uses this mode because it has its own assessor.

Public events, errors, synthetic inputs and final answers are retained, including failed runs. Reasoning/encrypted content is excluded and common credential fields/headers/signed query values are redacted. This is defense in depth: fixtures must not contain real credentials or private production data.

Local candidate acceptance, normal installed-profile acceptance, Fable activation, publication, installation/reinstallation and production readiness are separate results. Do not infer any of the latter from fixture tests or this collector's exit code.
