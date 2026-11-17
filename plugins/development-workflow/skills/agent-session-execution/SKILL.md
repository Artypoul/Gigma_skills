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

## Task Acceptance

For meaningful tasks, including tasks outside a repository and without an explicit Fable invocation, record the expected outcome, exact target, boundaries, authorized actions, behavior to preserve, and observable completion criteria in the current task context. Reuse criteria from an approved plan or an existing `DoneWhen`; do not start a second tracker or orchestrator.

Resolve the requested artifact before drawing conclusions about it. Instructions explaining how to work are not a substitute for the profile, document, code, or external state the user asked to inspect. If only part of the requested target was inspected, name that gap and leave the corresponding criterion open.

Keep unresolved requirements when later messages refine the task, ask for status, or move it to another stage. Update the affected criteria and record explicitly cancelled or replaced requirements as cancelled; do not continue a goal the user has withdrawn.

Use available context and permitted sources first. If a remaining choice would materially change the outcome, target, scope, or authority, ask one concrete question before dependent work. Bind each answer to the decision it resolves: permission for a later PR does not select an unresolved target. Reuse confirmed decisions and preserve special access and hard-gate restrictions.

When delegating implementation or review, give each agent the original requirement, current applicable acceptance criteria, boundaries, and behavior to preserve. Update affected assignments when the user refines the task. The independent reviewer checks the actual result against those criteria; an executor's completion message is not acceptance evidence. Delegation remains conditional on the selected workflow and available authorization.

Before reporting `ready`, the orchestrator checks each criterion against evidence tied to the current result: the revision and tested files for code, the version for a document, or observed state for an external action. Recheck affected criteria after a material change; earlier passing evidence does not transfer automatically. If required evidence is missing, report the gap using the selected workflow's completion status. Fable activation, task acceptance, PR readiness, and installation are separate facts.

Distinguish the requested deliverable from the wider outcome it describes. A factual report can be complete while the incident's cause is unknown and the investigation remains open. In the final response, state the actual verification coverage and every unfinished part of the user's overall goal; do not invent evidence to close it.

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
