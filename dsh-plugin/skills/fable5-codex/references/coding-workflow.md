# Coding workflow

## Before editing
- Confirm the requested outcome and acceptance criteria.
- Inspect repository instructions, status, branch, tree, manifests, tests, CI, and recent changes.
- Trace the affected path end-to-end: entry point, callers, state/data flow, persistence, permissions, external calls, and failure handling.
- Identify invariants and compatibility constraints. Record non-goals.
- Inspect existing conventions and dependencies. Frameworks and abstractions require a concrete need; applying patterns also requires the evidence and permission below.

## Scope guard and recovery

This guard applies to the primary agent and every delegated task, including small fixes. Reading supporting code to understand the task does not authorize changing it.

For ordinary scope/recovery/database-field/pattern advice, read this complete section before planning, reviewing or acting, including hypothetical cases and subagent reports. An unchanged copy already read in the current context may be reused. **Priority exception for an observed ongoing violation:** the first actions are `request_stop` and `warn_user`; do not put `read_reference` or any other recovery phase before them. After that immediate containment step, read this section before any further recovery advice or action.

### Establish and check the boundary

- Record the requested outcome, allowed files, specific sections/symbols, permitted behavior changes, database fields and protected invariants in the existing task record or plan. For a small task, a concise scope statement is enough. Derive it from the user's request and approved decisions; do not expand it yourself.
- Capture the current working state before editing or dispatching a writer: tracked and untracked files, existing uncommitted changes, relevant file contents or reversible patches, and ownership of concurrent work. Git HEAD alone is not the pre-task baseline.
- Give each subagent its narrower write scope, prohibited changes, baseline and reporting requirements. A needed adjacent fix, refactor or new dependency is a proposed scope change, not automatic authorization.
- Inspect actual diffs at each coherent checkpoint, while a subagent works when observable, after it returns, before integration and after later fixes. Include generated/untracked files and schema/data effects. A changed-file list or subagent summary is insufficient: check changed sections, semantics and database fields.
- Permission to modify one function, field or behavior does not extend to neighboring code or fields in the same file/table. If the requested result requires expanding scope, present the concrete change and wait for explicit user authorization before that work. Continue only independent work already in scope.

### Database fields are explicit scope

Identify affected fields as `table.column` (or the datastore's equivalent) and the authorized before/after behavior. Inspect relevant schema, migrations, ORM models, queries, serializers and write paths. Check additions, removal, renaming, types, nullability, defaults, keys, constraints, indexes, relationships, read/write semantics, computed values and backfills. An unchanged schema does not make a change to a field's meaning or stored values in scope. Do not invent a field or migration from a design convention, and do not alter unrelated fields inside an authorized model/table. This inspection does not authorize running migrations or changing database contents.

### Evidence and permission for patterns

Apply an architectural, design or data-access pattern only when both conditions are satisfied:

1. **Evidence:** identify the actual requirement or demonstrated problem, cite inspected code/tests/contracts or measured behavior, and explain why the pattern is necessary compared with a smaller change. A pattern's popularity, a generic best practice or its presence elsewhere is not sufficient evidence.
2. **Explicit user permission:** identify the user's approval of that concrete pattern and its scope. A general feature request, "clean code", skill advice, repository usage, agent/reviewer agreement, silence or a preselected option is not approval. Existing explicit approval remains valid within its original scope; do not ask again.

This covers introducing, reusing, extending or replacing patterns, including repository/unit-of-work layers, CQRS, outbox, event-driven flows and caching strategies. Ordinary syntax and local control flow are not architectural patterns. Without either condition, do not apply the pattern: show the evidence and concrete proposal when requesting the missing permission, or continue with an authorized solution that does not require it. Record evidence and approval with the task so reviewers and subagents can verify both.

### On an out-of-scope change

Steps 1–6 are an ordered prerequisite chain, including in a hypothetical answer or brief summary. Preserve each phase explicitly: a stop request is not confirmation that all in-flight tools, processes and delegated writers stopped; database/external assessment precedes every undo or artifact deletion. If containment, assessment, authorization or attribution remains unresolved, report the blocked step, preserve evidence and do not advance to restoration. A concise answer must retain these dependencies rather than moving the database assessment after code rollback.

1. **Request stop and warn immediately:** request interruption of the responsible subagent through the actual stop capability and prevent accepting or integrating its result. Promptly report the agent, violated boundary, affected paths/symbols/fields and current containment status, including pending or unverified termination. Do not wait for termination verification or rollback before warning. For the primary agent's own violation, stop the affected work and follow the same recovery procedure.
2. **Verify containment and preserve evidence:** before restoration, verify that the offender's in-flight tools, processes and delegated writers have stopped. For an already finished subagent, confirm that no pending writers remain. If the host cannot stop or observe them, report the limitation and keep unsafe restoration blocked; do not claim they stopped. Preserve the current affected content, offending patches/artifacts and available execution evidence before changing or deleting them, regardless of how certain authorship is.
3. **Assess database and external effects first:** establish whether unauthorized migrations, backfills or external operations ran before removing artifacts needed for reconciliation or recovery. Inspect actual state through authorized access; if access is unavailable, preserve the evidence and report unresolved effects. Removing a migration file does not undo an executed migration or restore data. Do not automatically run destructive down migrations, drop fields or overwrite data. Database/external recovery needs a verified safe procedure and the required authorization.
4. **Prepare selective recovery:** compare the pre-task/pre-dispatch state with observed agent patches. Coordinate other active writers touching affected paths or use a restoration mechanism that rejects intervening changes. Re-read and revalidate affected content immediately before applying recovery; on a version/content mismatch, preserve the current state and reassess instead of applying a stale inverse patch. If changes overlap or attribution is uncertain, stop the affected work and request targeted direction instead of guessing. Unrelated writers may continue.
5. **Restore only attributable unauthorized edits:** undo only confidently attributable out-of-scope hunks and agent-created artifacts whose removal is safe after the preceding assessment. Preserve in-scope changes, pre-existing edits, other writers' work and the retained recovery evidence. Do not reset a branch/worktree, clean untracked files broadly or restore whole files from HEAD. Report what was restored, preserved or remains unresolved.
6. **Verify before resuming:** inspect the resulting diff and relevant checks against the recorded scope and baseline. Resume affected work only after containment and recovery are verified and the assignment is corrected. The corrected assignment must remain within the authorized scope; an expansion additionally requires the user's explicit approval of the concrete change. Never use a clean test run to excuse an unauthorized change.

Any recovery explanation must name both the recorded baseline and the current content when preparing selective recovery, and must distinguish unverified in-flight tools, processes and delegated writers from confirmed containment.

## Plan and implementation
1. Break work into independently verifiable changes.
2. Define behavior and edge cases before implementation. For behavior changes, write a focused test first where practical and verify it fails for the intended reason.
3. Make the smallest coherent patch. Avoid drive-by refactors.
4. Keep interfaces explicit and errors actionable.
5. Preserve backwards compatibility unless the task explicitly authorizes a breaking change.
6. Review the diff against the scope guard, including database fields and pattern evidence/permission; check for accidental files, secrets, generated output, and unrelated formatting.

## Engineering quality
- Optimize for clarity, correctness, maintainability, and operability—not line count.
- Handle null/empty/invalid input, permission failures, timeouts, partial failure, retries, and concurrent operations.
- Keep validation at trust boundaries and enforce authorization on the server.
- Make state transitions and side effects explicit.
- Prefer deterministic behavior and observable failure modes.
- Add comments for non-obvious rationale, not to narrate obvious code.

## Definition of done
The requested behavior is implemented; relevant tests and checks were run; the diff is reviewed; known limitations are documented; no unverified claim is presented as fact.

## Tooling boundary
Use the actual shell/editing/test tools available in this Codex session. Check their descriptions before use. Tool names in old examples or other runtimes are not contracts.
