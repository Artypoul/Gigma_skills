# Testing, CI, and release verification

## Test strategy
Choose tests by risk and behavior:
- Unit tests for deterministic domain rules and edge cases.
- Integration tests for database, queues, provider adapters, auth, and transaction boundaries.
- Contract tests for APIs, schemas, webhooks, and provider behavior.
- End-to-end tests for critical user journeys across real boundaries.
- Regression tests for each fixed defect.
- Security tests for authorization, tenant isolation, and trust-boundary assumptions.

## Test quality
- Assert outcomes and observable side effects, not merely mock calls.
- Use realistic fixtures and representative failure responses.
- Avoid broad snapshots when focused assertions are clearer.
- Test duplicate, retry, timeout, partial failure, concurrency, and invalid-state cases where relevant.
- Keep tests deterministic; isolate time, randomness, network, and shared state.

## CI workflow
1. Inspect repository CI definitions and required status checks.
2. Run the smallest relevant test first.
3. Run lint, formatting, type checking, migrations/schema validation, and build as applicable.
4. Run the full required suite before claiming the change is ready.
5. Inspect the actual CI run for the exact PR head SHA.
6. Distinguish not run, queued, in progress, skipped, cancelled, failed, and passed.
7. For failures, read the failing job logs and fix root causes; do not assume flakiness without evidence.

## Release and deployment
Verify target environment, migration order, configuration/secrets, health checks, rollback path, feature flag behavior, and post-deploy signals. A merged PR is not proof of a successful deployment. A successful deployment job is not proof that the user journey works.
