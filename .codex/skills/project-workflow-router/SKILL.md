---
name: project-workflow-router
description: Load project context, then route multi-step or product-sensitive repository work to the right project skills. Use for implementation, code review, PR fixes/finalization, merge/deploy/handoff, frontend/UI, data/API, website copy, prompt architecture transfer, evidence research, context repair, or skill-bundle design when more than one workflow may apply. Do not trigger for tiny self-contained questions, single-command checks, or simple context snapshots; use project-context-bootstrap alone for those.
---

# Project Workflow Router

Use this skill to decide which workflow chain to run. It is a router, not a replacement for the selected skills.

## Always Start

1. Load project context first: run `project-context-bootstrap` when available and read the project-local `AGENTS.md` and memory files. Recorded decisions, blockers and current Git/PR state must inform the question instead of being asked about.
2. Then, if the expected result is still not explicit, ask Art one concise clarifying question about what remains unresolved and wait for his answer. Do not edit, commit, push, create a PR, merge, deploy, or call external APIs until he answers. Skip the question when the request is already fully specified (outcome, scope and completion criteria are explicit with no open product choice), when the message is an answer or continuation of an already clarified task, when a single unambiguous fact is requested, when project memory already answers it, or for automated one-shot invocations that carry their own full specification (for example a review run with PR number and checklist).
3. Do not reopen a decision already captured in project memory; if it must change, say so explicitly and ask only about that change.
4. Prefer local project skills over generic global skills.
5. If a named skill is available, read its `SKILL.md` before acting.
6. If the user asked only for review, audit, check-up, консилиум, plan-only, or read-only work, end with a report. If the same request explicitly says to repair confirmed findings, use `changes-requested`: review first, fix only supported in-scope defects, rerun affected checks, and still do not commit, push, create PRs, merge, or deploy unless separately requested.
7. If Art says "сделай PR", "оформи PR", or otherwise asks for a PR without saying draft, route it as a GitHub PR that is Ready for review/non-draft. This does not mean merge or deploy.
8. After a completed task, classify a new user request as continuation, extension, or an independent scope before reusing the old workflow. For an independent feature or investigation, recommend a new Codex task once and carry forward only verified project memory/handoff facts. Do not create that task without an explicit user request. If Art continues in the same task, restate the new scope and completion criterion so the old title/history is not treated as the active contract.

## Route Matrix

| User/task signal | Skill chain |
| --- | --- |
| "сделай", "реализуй", "добавь", "измени" when the user is asking for code/product changes; multi-file feature, API/UI/data changes | `project-context-bootstrap` -> `feature` -> project plan/review skills -> implementation -> tests/checks -> code review/monster feedback -> finalization |
| Complex task with several steps, code/research/files/tools, or a requested durable deliverable | `high-agency-execution` -> narrow specialist skill -> `capability-aware-execution` or `agent-session-execution` only when needed |
| Authorized security review/test, secrets or sensitive data, access-control change, or potentially harmful external effect | `project-context-bootstrap` -> `security-sensitive-execution` -> narrow domain skill -> runtime confirmation and verification |
| "ревью", "чек ап", "ошибки агента", "посмотри PR" | `project-context-bootstrap` -> code-review stance -> local review skills -> findings-first report; when the same request explicitly includes "исправь/чини", continue with supported in-scope repairs and fresh validation |
| "смерджил", "merged", "handoff", "чини в PR", "prod ready", deploy state | `project-context-bootstrap` -> `development-handoff` when available |
| Frontend/UI/forms/responsive/cabinet changes | `project-context-bootstrap` -> local `frontend-plan` or equivalent -> local `frontend-safety-check`/`affordance-review` |
| Auth/payment/subscription/webhook/user flow | `project-context-bootstrap` -> `ddd-api-standard` when installed and the change touches API contracts, invariants, access rights, money, limits or the data schema -> local flow/data review skills -> `feature` if implementation is needed |
| Backend/API design or review: domain model, bounded contexts, aggregates, transactions, concurrency, idempotency, migrations, events/outbox | `project-context-bootstrap` -> `ddd-api-standard` when available, otherwise a project-local backend plan/review skill with the missing capability reported -> `feature` if implementation is needed |
| Website meanings, landing, offer, CTA, page copy | `project-context-bootstrap` -> project-specific context skill if present -> website/copy skill |
| Third-party system prompt, prompt leak, Fable/Claude/Gemini/Codex prompt transfer, agent instruction audit | `project-context-bootstrap` -> `prompt-architecture-port` -> implementation workflow if edits are explicitly requested |
| Current/latest/verify/research/recommendation/source-backed question | `research-with-evidence` -> current source reading -> cited answer or bounded uncertainty |
| GitHub review comments or failing checks | `project-context-bootstrap` -> GitHub comment/check skill when available -> fix same PR |
| PR creation/finalization | `project-context-bootstrap` -> local `pr-finalize` or equivalent |
| Unknown or product-sensitive choice | `project-context-bootstrap` -> ask one concrete product question before edits |

See `references/bundles.md` for reusable named bundles.

## Output

Before substantial work, state:

```text
SKILL ROUTE
Context:
Selected chain:
Why:
Mode: report-only | changes-requested
Blocked by:
Next:
```

Keep it short. Once the route is clear, execute the selected workflow instead of stopping at a plan.

## Safety

- Do not use this router to skip review gates.
- Treat hard gates as blockers when unavailable, stale, or queued: required CI, required PR approval, deploy gates, security checks, explicit user-required review, and PR evidence for PR work.
- If an optional automatic reviewer such as monster/Codex/Claude review is unavailable and project rules allow a local fallback, run a local findings-first monster review, state the limitation, and do not mark the task ready while real findings remain open.
- Do not create a new PR if the user asked to fix the existing one.
- Do not broaden product scope silently; ask when several product choices are valid.
- Do not mark a PR/merge/deploy task ready while its required CI/review/deploy evidence is unknown. For a local-only task, distinguish evidence that is genuinely unknown from PR/CI/deploy evidence that is not applicable.
