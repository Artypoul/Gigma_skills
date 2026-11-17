# Agent task acceptance verification

This change makes task acceptance explicit in the canonical session workflow and references it from both global profiles and the project router. It preserves unresolved goals through refinements, honors cancellation, binds answers to the decision they resolve, requires the requested artifact rather than a related instruction file, and invalidates stale evidence. Fable activation, task completion, PR readiness and installed behavior remain separate results.

Development workflow manifests advance together to `0.4.13`. The PR's Codex mirror content is generated from the corresponding canonical source. CI runs the repository's `bash sync-codex.sh` and rejects a resulting tracked or untracked mirror difference.

## Automated checks

- New acceptance suite: 32 tests passed locally. Cases include completed-but-wrong conclusions, missing child results, early delegation, wrong session/cwd, incomplete or conflicting activation receipts, denied writes, stale candidate/review hashes and reserved-check collisions.
- Existing updater suite: 107 tests ran successfully, one skipped.
- Development workflow suite: seven tests passed.
- Repository suite: 23 tests ran successfully, five skipped.
- Protocol self-test and whitespace validation passed.
- Local profile/bootstrap suite: 77 tests ran; 38 hit sandbox `os.link` permission errors, one skipped. This is not a green result. The existing Windows/Linux CI matrix reruns this suite on hosted runners.

The portable CI job now includes the new acceptance suite. For the exact published revision, consult that revision's GitHub Actions results; local results are not substituted for CI.

## Actual agent observations

Four separate native executor sessions applied the candidate Standard or Fable+Superpowers instructions to repository and non-development tasks. Follow-up turns checked unresolved-target clarification, reuse of decisions, preservation of conditions after steering, explicit cancellation, completed-report versus unresolved-cause distinctions, and updating conclusions after evidence changed.

One session initially inspected the session instruction file instead of the Standard profile. That unsuccessful observation was retained and motivated an explicit exact-artifact rule. A fifth executor with fresh context then received the original comparison task and found the correct Standard profile without being given its path.

These were source-instruction probes under an explicitly authorized activation exception. They were not ordinary installed-profile sessions in four different working directories. Actual normal activation-before-delegation, autonomous delegated assignment updates, installation/reinstallation and the full installed-profile matrix remain unverified. A standalone live app-server attempt failed before model execution because the sandbox could not open its existing state database.

## Independent review

A separate read-only reviewer found and verified fixes for three substantive defects: semantic criteria overwriting integrity checks, missing cwd/identity being accepted as activation evidence, and plaintext credential-header redaction gaps. A follow-up also checked conflicting discovery digests. The reviewer replayed the negative cases, checked the final tests and source hashes, and approved the local source candidate with no unresolved substantive findings.

Raw machine logs, absolute workstation paths, private conversation links and local execution receipts are intentionally excluded from this public change. Finite passing scenarios do not guarantee error-free future agent behavior or establish production readiness.
