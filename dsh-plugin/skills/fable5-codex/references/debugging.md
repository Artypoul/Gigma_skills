# Debugging and incident workflow

## Principle
Reproduce before repairing. A plausible explanation is a hypothesis until evidence distinguishes it from alternatives.

## Sequence
1. Capture the exact symptom, environment, input, timestamp, and expected behavior.
2. Reproduce with the smallest deterministic case. If production cannot be touched safely, use logs, traces, fixtures, or a staging environment.
3. Trace the failing path across boundaries: client, API, auth, database, queue, provider, cache, and deployment as relevant.
4. Form competing hypotheses and identify the observation that would falsify each.
5. Inspect logs and state with secrets and personal data redacted.
6. Write a regression test for the defect before applying the fix when the codebase permits it.
7. Fix the root cause, not only the visible symptom.
8. Run the regression test, relevant suite, and adjacent checks.
9. Verify recovery, retry behavior, idempotency, and rollback implications.

## Distributed-system failure modes
Check duplicate delivery, reordered events, stale reads, timeout-after-success, partial commit, retry storms, race conditions, lease expiry, clock skew, provider rate limits, and reconciliation gaps.

## Do not
- Guess from a single log line.
- Treat a timeout as proof that a remote mutation failed.
- Retry a non-idempotent operation blindly.
- Silence or weaken a failing test to make CI green.
- Claim a production fix without a verified deployment and observed recovery.

## Incident handoff
Record impact, affected scope, timeline, confirmed facts, hypotheses, mitigation, root cause if known, corrective actions, owner, and remaining uncertainty.
