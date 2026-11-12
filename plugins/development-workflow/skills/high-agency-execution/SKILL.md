---
name: high-agency-execution
description: "Use as the entry point for a complex task that may require several steps, code, research, files, tools, or a durable deliverable. Make a short plan, load the narrow relevant skills, use only real capabilities, act autonomously within safe scope, verify the result, and finish with an outcome-first handoff. Do not use for a trivial question or when a dedicated skill already owns the whole task."
---

# High-Agency Execution

Use this skill to make complex work reliable across Codex models. It is an execution harness, not
a claim that every model has the same intelligence or tools.

## Workflow

1. Lock the requested outcome, constraints, external effects, and definition of done.
2. Inspect available skills and tools before generic reasoning. Load the narrow specialist skill,
   or use `capability-aware-execution` when the capability fit is uncertain.
3. For non-trivial work, maintain a short plan with one active step. Do not add planning ceremony
   to a trivial request.
4. Read source evidence before changing code or making material factual claims. Use project-local
   workflows for repository work and `research-with-evidence` for current or sourced facts.
5. Proceed with reversible in-scope work. Pause only for destructive action, external publication,
   or a product decision the user has not made.
6. Create the requested artifact when the request calls for one. Do not replace it with an outline,
   a simulated tool result, or a promise to act later.
7. Run the proportionate proof: tests for code, source checks for research, render checks for a
   visual file, or delivery evidence for an external action.
8. End with the outcome first: what changed, proof performed, and any concrete blocker.

## Anti-Thrashing and Retry Budget

For every blocker, keep a stable blocker fingerprint and an attempt count in the active plan. After three identical confirmed repeats, mark the task `blocked` and stop; do not start a fourth identical pass. Before each retry, name the changed hypothesis or the new external fact; when neither changed, reject the retry. Classify `tool failed` separately from `hypothesis falsified`: a failed tool call is not evidence that the technical hypothesis is false and does not justify repeating the same call without new evidence.

## Boundaries

- A skill improves process discipline; it cannot add model weights, hidden context, persistence,
  connectors, or tools that are not available.
- Do not invoke unrelated skills just because they exist.
- Do not claim a background, scheduled, or external action started unless the real capability was
  called and its result was observed.
- For detailed behavioral checks, read `references/behavioral-evaluation.md`.
- For a comparison across available models or runtimes, read `references/model-evaluation.md` and
  report only observed evidence; do not infer parity from the skill text.
