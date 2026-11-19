# Windows marketplace installation

## Goal and approved scope

Implement the user's approved plan for the `Filename too long` failure when adding
`Artypoul/Gigma_skills` as a Codex marketplace on Windows. The screenshot identifies
generated GitLab CI include-cache files in the full Git checkout. Remove those
artifacts, prevent their return, and prove the fixed catalogue can be added and
refreshed by a real Windows Codex CLI with Git long-path support disabled.

The specification is the approved conversation plan; this file records its concrete
implementation and acceptance criteria. Baseline: repository commit
`7488f662dfa56ba37382b5c7277009d77a311b9a`. Work on an isolated branch and open a PR;
merging, deploying, changing the user's Windows settings, or changing an OpenAI
Codex fork is outside this implementation.

## Global Constraints

- `plugins/` remains canonical; `.codex/skills` and `.codex/reference` are generated
  only by `bash sync-codex.sh`.
- Remove only generated `.gitlab-ci-local` artifacts. Preserve ordinary GitLab CI
  examples, validator scripts, skill instructions, authorship, and licenses.
- Exclude generated caches before copying them. Deleting a copied long path after
  the copy is not sufficient. Preserve the existing Python-cache exclusion policy.
- Preserve Claude's ownership, unmanaged-file, symlink, adoption, and prune guards.
  Run Claude sync only with an explicit temporary `--dest` during validation.
- Keep the sync scripts usable with their existing Bash/core utilities; avoid a
  new package-manager or language-runtime prerequisite for normal synchronization.
- Change `devops-skills` from `0.1.1` to `0.1.2` in both plugin manifests and both
  runtime catalogue entries. Other plugin versions and external source pins stay
  unchanged.
- Do not alter the host's home, Codex profile, Git global settings, accounts, or
  credentials. Windows acceptance runs only on an ephemeral hosted CI runner.
- Use real commands and assert observed behavior. Source inspection and Linux
  checks do not constitute a passing Windows or desktop GUI test.
- Use the pinned Fable `1.4.2` / `a0d7b991d29e2cb0f18f3501fd1152335a3bb90c`
  and owned Superpowers `7.0.2` / `22f0b463e7a5e579904dd6211a520321035526f7`
  in `chatgpt_github` mode. Native MCP readiness is not claimed.

## Task 1: Remove generated cache from package and synchronization

### Scope

- `.gitignore`
- `sync-codex.sh`, `sync-claude.sh`
- `validate_plugin.py`
- A small shared cache-filter helper under `scripts/`, only if it avoids duplicated
  filtering logic in both sync scripts; no broader sync refactor.
- `plugins/devops-skills/.codex-plugin/plugin.json`
- `plugins/devops-skills/.claude-plugin/plugin.json`
- `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json`
- Four tracked files below
  `plugins/devops-skills/skills/gitlab-ci-validator/examples/.gitlab-ci-local/`
  and their four generated mirrors below
  `.codex/skills/gitlab-ci-validator/examples/.gitlab-ci-local/`.
- Focused regression tests under `tests/` and related existing sync tests.

### Implementation

1. Add behavioral regression tests first and record their expected failures.
2. Remove the generated cache from the canonical package, ignore
   `.gitlab-ci-local/` at every depth, and regenerate the mirror with the sync script.
3. Filter generated cache directories before copy in both sync paths, including
   canonical references. Align validator cache handling so a locally regenerated
   source cache is not required in the Codex mirror.
4. Preserve unmanaged Claude content and the existing explicit-adoption behavior.
   Generated caches must not make an otherwise identical canonical copy conflict,
   while ordinary extra files and unsafe symlink entries must remain protected.
5. Bump the four `devops-skills` version declarations to `0.1.2`.

### Acceptance and verification

- No `.gitlab-ci-local` files remain tracked in either canonical package or mirror.
- A test fixture regenerates nested source caches and runs the actual sync scripts;
  the caches do not reach the destination, regular examples still do, and validator
  mirror comparison succeeds. Assert filtering before copy with a meaningful
  regression (for example an unreadable generated cache or instrumented file-copy
  boundary), not only a final-directory absence assertion.
- Tests cover both skill and reference paths, preserve Python-cache behavior, and
  exercise Claude's unmanaged/adoption guards without touching a real profile.
- `python -B validate_plugin.py` passes.
- `python -B -m unittest discover -s tests -p 'test_*.py'` passes.
- `bash sync-codex.sh` is idempotent relative to the committed generated mirror.
- Inspect the final diff, commit the task, and report RED/GREEN commands and results.

## Task 2: Add real Windows marketplace acceptance and installation guidance

### Scope

- `.github/workflows/validate.yml`
- One focused Windows acceptance script under `scripts/` (PowerShell or Python),
  with small tests only for material logic that can be checked locally.
- `docs/windows-marketplace.md`
- A short discoverability link from the relevant install guidance in `AGENTS.md`
  or `codex-profile/README.md`; no unrelated profile or skill changes.

### Windows acceptance design

1. Add a separate `windows-latest` job using a complete Git history and pinned
   `@openai/codex@0.167.1`. Verify the CLI version. No account login or model calls.
2. Use the fresh default Codex profile of that disposable runner. Fail if a
   pre-existing user configuration or authentication would contaminate the test.
   Derive paths with task-specific variables; do not repurpose `HOME` or
   `CODEX_HOME` as scratch variables or change the host's profile.
3. Force `core.longpaths=false` at inherited Git command-config precedence and
   assert its effective value. Do not use sparse checkout. Preserve normal CLI
   staging so the checkout prefix is representative of the reported Windows path.
4. Create an isolated local bare Git fixture from the checked-out repository.
   Present it to Codex as a synthetic HTTPS source using an inherited Git
   `url.<file-url>.insteadOf` rewrite. This exercises Codex's real Git-source path:
   passing a local directory instead would bypass checkout. Do not publish the
   fixture or modify the real repository's remote/default branch.
5. Negative control: point the fixture's default branch at the known failing
   baseline `7488f662dfa56ba37382b5c7277009d77a311b9a`, run actual marketplace add,
   and require a nonzero exit plus `Filename too long`. Verify it did not register
   a successful marketplace. This proves the environment detects the original bug.
6. Point the same fixture default branch at the exact candidate checkout SHA;
   run `codex plugin marketplace add <synthetic-https> --ref <fixture-branch> --json`
   and `codex plugin marketplace list --json`. Assert the `gigma-skills` entry,
   installed root, Git source, exact installed HEAD, full catalogue, and absence of
   generated cache paths. Require a complete checkout rather than a sparse subset.
7. Make one test-only empty descendant commit with the candidate's identical Git
   tree in the local fixture, advance its branch, and run
   `codex plugin marketplace upgrade gigma-skills --json`. Require no errors, the
   selected marketplace, and a nonempty upgraded root. Verify the installed HEAD
   is the new fixture revision and its tree equals the exact candidate tree.
   This forces a real refresh instead of accepting an unchanged-revision no-op.
8. Log the relevant revisions, effective Git configuration, staging/path lengths,
   and concise results. Fail with useful output on any mismatch. No secrets are
   needed or printed. Keep the test isolated from other jobs and normal local use.

### Source-backed implementation notes

The pinned CLI implements `add`, `list`, and `upgrade` with `--json` in
[`marketplace_cmd.rs`](https://github.com/openai/codex/blob/rust-v0.167.1/codex-rs/cli/src/marketplace_cmd.rs).
Its full-checkout add path clones the default branch before switching `--ref`, and
its source parser rejects `file://` as a direct marketplace source. The local Git
rewrite fixture is therefore necessary for a meaningful pre-merge test. Upgrade
may return early when installed revision metadata is current, hence the test-only
descendant commit.

### Documentation and verification

- Document normal GUI fields: repository `https://github.com/Artypoul/Gigma_skills`,
  `Git ref: main`, selective paths empty for the full catalogue. `plugins/codex` is
  not a valid checkout filter for this repository.
- Explain the generated-cache root cause and the limits of this fix for arbitrary
  future paths. Include the short-term Git for Windows workaround
  `git config --global core.longpaths true`, verification of the Git executable and
  effective setting, restart/retry, and a short local clone alternative. Do not
  claim the assistant changed the user's machine.
- Explain that a PR branch passed as `Git ref` still clones the default branch
  first in the tested Codex version; until merge the workaround may still be needed.
- Cite official Git/Windows/Codex sources and name the CI CLI version. Describe CI
  as a real CLI acceptance test, not a desktop GUI end-to-end test.
- Validate script syntax and locally test only relevant portable behavior; run the
  actual Windows job after PR publication and inspect its outcome before claiming
  Windows acceptance. Existing required CI must continue to pass.
- Inspect the final diff, commit the task, and report executed checks and limits.

## Completion

Each task receives an independent spec and quality review, followed by a whole-branch
review. Publish the reviewed branch and PR through the GitHub integration, inspect
CI and connected automatic review, address real blockers, and report the exact PR
and verification evidence. If the automatic review service is unavailable, state
that explicitly and retain independent local review evidence. Do not merge the PR.
