# Product engineering

## Start from the user journey
Identify the user, their intent, entry point, prerequisites, expected result, and what happens when each step fails. Map the journey across UI, API, auth, persistence, integrations, and support.

## Product contract
For each feature define:
- Actors and ownership.
- Permissions and tenant boundaries.
- Inputs, outputs, validation, and state transitions.
- Limits, billing/subscription rules, and entitlement checks.
- Loading, empty, success, error, retry, and recovery states.
- Idempotency and concurrency expectations.
- Auditability and support/debuggability.
- Backwards compatibility and migration behavior.

## UX and product quality
Prefer understandable defaults, progressive disclosure, useful errors, accessible interactions, responsive layouts, and recovery over dead ends. Do not expose internal implementation details unless they help the user make a decision.

## Business logic
Find the source of truth in code, database, configuration, or approved product requirements. Do not invent a policy. Avoid hard-coded limits when the product already supports configuration or entitlements. Enforce critical limits server-side, not only in the UI.

## Acceptance
Write acceptance criteria as observable user outcomes, including at least one negative or recovery path. Verify the whole flow, not just the component or endpoint that was edited.
