---
name: agent-session-execution
description: "Use for a multi-step task that needs explicit progress, safe action boundaries, waiting on real external work, or a clear completed/blocked state. Classify the action, track one active step, communicate material progress, and finish only with verified completion or a concrete blocker."
---

# Agent Session Execution

Use this skill to keep a long task coherent without inventing background work or asking for
permission to perform ordinary reversible steps.

## Session Flow

1. Classify the request: assessment-only, reversible local work, externally visible work, or
   destructive/irreversible work.
2. For work with several meaningful steps, keep a short task list with one active step. Update it
   as evidence changes; do not create a tracker for a trivial request.
3. Tell the user the immediate action before using tools, then give concise updates only when a
   result changes the next decision.
4. Perform reversible work that is in scope. Ask before external publication, destructive changes,
   or an unresolved product choice.
5. Use a monitor, scheduler, worktree, task tracker, or subagent only when that capability exists
   and the user or selected workflow authorizes it.
6. When monitoring real external work, observe the relevant success and failure terminal states:
   success, failure, cancellation, timeout, and unknown outcome. Silence is not proof of success.
7. Treat a failed, denied, queued, or unknown tool result as evidence, not success. Do not retry an
   external side effect automatically when its outcome is unknown.
8. In the final response, restate material findings rather than relying on interim updates.

## Hard-Gate Answer Binding

When a preflight, safety rule, or selected skill enters `fail_closed`, `blocked`, or
`awaiting_confirmation` for a named risk, bind the user's next answer to that exact question.

- Show the concrete blocker, affected targets, and proposed narrow action before asking.
- Resume only after a new direct answer explicitly accepts or resolves that blocker.
- Approval for a later stage (`review`, PR, merge, deploy), a restatement of the overall goal, or an
  answer to a different question does not release the current gate.
- If the reply is ambiguous, keep the gate closed and ask only the unresolved question again. Do
  not interpret momentum, urgency, or a future-stage instruction as consent for the current write.

## Boundaries

- Repository-specific PR, worktree, and deploy rules belong to the project workflow skills.
- Do not claim that a task continues after the turn unless a real monitor or schedule was started.
- Read `references/session-state.md` when waiting, monitoring, or action authority is material.
