# Deep code review

Review the actual diff and its integration with surrounding code. Do not infer correctness from PR description, commit message, author confidence, or test count.

## Review passes

First enforce the [scope and pattern gates](coding-workflow.md#scope-guard-and-recovery): compare actual changes with the authorized files, sections, behavior and database fields, and verify concrete evidence plus explicit user permission for applied patterns. An unauthorized change blocks acceptance even if technically correct or covered by passing tests. If found, stop the responsible subagent, warn promptly and follow selective recovery before continuing the affected work.

1. **Scope and intent:** Does the diff solve the stated problem without unrelated changes?
2. **Architecture:** Are boundaries, dependencies, ownership, and contracts consistent with the repository?
3. **Behavior:** Trace happy paths, invalid input, empty state, permission denial, failures, retries, and recovery.
4. **Security:** Check authentication, authorization, tenant isolation, input validation, injection, secret handling, SSRF, path traversal, and data exposure as relevant.
5. **Data and concurrency:** Inspect transaction boundaries, uniqueness, migrations, locking, idempotency, race conditions, and rollback.
6. **Integration:** Verify provider/API contracts, pagination, timeouts, error mapping, webhook authenticity, and compatibility.
7. **Tests:** Check that tests assert user-visible or contract behavior, include regression cases, and are not over-mocked.
8. **Operations:** Inspect observability, deployment, feature flags, config, backfills, and rollback.
9. **Maintainability:** Look for duplication, dead code, hidden coupling, unclear naming, and unnecessary complexity.

## Finding format
For each finding provide severity, exact file/line, concrete scenario, impact, why current behavior is wrong, and a practical correction. Separate blockers from suggestions. Do not report speculative concerns as confirmed defects.

## Verdict
- **Request changes:** a verified correctness, security, data-integrity, or compatibility defect blocks merge.
- **Approve with suggestions:** no blocking defect; optional improvements remain.
- **Comment:** questions or non-blocking observations need clarification.

A clean review means no actionable defects found in the reviewed scope—not proof that the entire system is defect-free.
