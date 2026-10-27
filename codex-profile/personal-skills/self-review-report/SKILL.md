---
name: self-review-report
description: Use when a final response needs an evidence, scope, permission, or status check, including саморевью and второй проход. Apply the project-selected review protocol when one exists; otherwise use the global fallback.
---

# Self Review and Repair

Before every final response, including a clarification, stopped response, or blocked result, review the current task result and draft privately. Fix in-scope issues before the user sees the response, then report the outcome concisely.

## Select the review protocol first

| Observable condition | Active protocol |
| --- | --- |
| Applicable project/user instructions define self-review, or a nearest project-local `self-review-report` exists | Follow that protocol and its report format; global steps below are inactive. |
| No project/user self-review protocol exists | Use the global fallback below. |

A project protocol may require one text-only pass before the answer. Complete that pass, reuse its verification, and finish in its required format. Do not emit the global pending line, activate a post-answer hook, start another pass, or report missing automation as a blocker. This remains true for short tasks and for explicit requests to review previous work. A direct request for an additional pass is handled within its stated scope.

The selected lifecycle (including Superpowers when selected) retains its implementation, verification, and completion stages. This skill checks evidence and the response; it does not repeat those stages or grant edits, commit/push/PR, external writes, merge, or deploy. Stop/intake rules apply before any file read or tool call.

**When a project protocol applies, finish through it here. All following sections apply only to the global fallback.**

## Global fallback

### Pre-response Review

Treat initial execution as the first pass. Before its answer, check that the draft accurately describes the request, saved result, current evidence, permissions, and limitations. This response-level check is not another execution of the whole task.

For a short task with an available trusted hook, perform the independent broad second pass after the first answer, using the post-answer operation below. Do not also run that broad pass before the first answer. If automatic continuation is unavailable, perform one private broad pass before answering and report that this fallback did not demonstrate post-answer automation. When the human explicitly requests review of previous work, that requested review itself is the second pass; do not schedule a third pass after reporting it.

For intermediate answers in a long workflow, review the current response, status, scope, and evidence without repeating the whole workflow. At its final milestone, perform the applicable completion checks; do not add a post-answer task replay.

At the start of an independent second pass, derive a private, task-specific checklist from the latest user request, explicit completion criteria, exclusions, and applicable instructions. Check every item against the actual result without expanding scope.

In that independent pass, actively look for a counterexample, missed requirement, unsupported claim, stale check, unsafe scope expansion, or mismatch between the reported and actual state. Select evidence by task type:

- For reasoning, calculations, or transformations, re-derive the material result independently when practical.
- For factual answers, challenge every material claim. Verify time-sensitive, uncertain, niche, or high-stakes claims with the sources required by the applicable instructions instead of relying on memory.
- For artifacts or code, inspect the latest saved result or diff and run the affected validators after the most recent material change.
- For external actions, inspect the read-back state and identifiers. Never repeat a send, payment, deploy, merge, deletion, or other write merely to verify it. If the outcome remains uncertain, report `unknown` and stop.
- For a clarification, review only the question and known context; do not inspect files or call tools when another instruction requires clarification first.
- If the user says stop, pause, or equivalent, stop task work immediately. Perform only a response-level review and do not use tools or resume the task.

### Required Loop

Use the full loop for an independent second pass or explicitly requested review. The ordinary check of an intermediate response in a long workflow does not start another broad review-and-repair loop. Required evidence, permissions, stop rules, and honest status reporting still apply to every answer.

1. Re-read the latest user request and applicable instructions. Confirm the result answers the current request and satisfies its completion criteria.
2. Check the task result and draft response for correctness, completeness, request alignment, scope, safety, clarity, and consistency.
3. Check factual and completion claims against available evidence. For tool-based work, inspect the latest state and run the smallest relevant validator after the latest material change. For each claim such as "works", "matches", or "ready", identify what was checked, by which method, and what that evidence does not cover. Fragment measurements do not establish whole-screen parity; mocked API responses do not establish live integration; a passing test count does not establish the requested user outcome. Narrow the claim to the evidence, and use a non-ready status when a required part remains unverified. Never claim an action succeeded without direct evidence.
4. List actionable issues privately and immediately repair every issue that is within the authorized scope:
   - Revise the draft when the answer itself is wrong, incomplete, unclear, or misleading.
   - Edit the artifact or implementation when the completed work is defective, then rerun every affected validator.
   - Do not expand scope or perform an action requiring new authorization. When a repair cannot be made safely, name it as a limitation or blocker.
5. Run one broad review-and-repair pass. If repairs were made, perform one focused re-check of the repaired areas and affected claims. If that re-check finds another in-scope issue, repair it and run the smallest affected validator, but do not restart the broad review. Report remaining uncertainty with a non-ready status.
6. Identify unresolved risks, assumptions, skipped checks, or blockers. Do not hide them behind a positive summary.
7. Choose exactly one final status. When definitions overlap, `unknown` takes precedence; otherwise use the first matching definition in this order:
   - `unknown`: a material action's outcome or the result's correctness cannot be established safely from available evidence.
   - `ready`: the requested result is complete and sufficiently verified.
   - `partial`: a usable requested subset is delivered, but a named requested part remains.
   - `blocked`: no usable requested result can be completed until user input, authorization, access, or an external state change is available.

Do not reveal private reasoning or hidden chain-of-thought. Report only conclusions, checks performed, evidence, repairs made, and limitations.

Do not send an unreviewed final response. The report does not replace repair or validation.

The pre-response review remains instruction-only. The optional post-answer operation below was explicitly requested by Art. Do not introduce other controllers, persisted state, background workers, or configuration changes under that authorization.

### Второй проход короткой задачи — Post-answer Operation

Art approved this operation on 2026-10-10: after the first answer to a short task, automatically continue the same conversation once, re-check the actual task result, repair authorized defects, and report what changed. This is distinct from the private pre-response review. Do not pretend that the pre-response review proves a post-answer continuation happened.

#### Select the scope

- Apply to a completed, bounded task with one concrete outcome: a direct answer, calculation, small review, document edit, or small fix. Size is determined by the work and its workflow, not the answer's word count.
- Do not request the extra continuation during a long chain, including plan → implementation → CI → external review → PR/merge, prolonged investigations/browser runs, or ongoing multi-stage work. A short status reply inside that chain does not make the chain a short task. Keep the ordinary pre-response review.
- For a clarification, review only the question and known context. The continuation must not start work that is waiting for an answer or permission.
- For stop, pause, cancellation, an interrupted task, or a request to avoid extra passes, never request automatic continuation. Review only the response, without tools or resuming work.
- An explicit human request to review or rewrite the preceding work/answer is already a requested second pass. Complete it and report its changes without emitting the pending line again.
- Never replay an external action to check it: sending, payment, merge, deploy, deletion, and other writes are verified by read-back within the original permissions.

#### First answer and activation

When the short-task operation applies, include the normal evidence-based Саморевью report, then end the first answer with this exact visible line:

`Второй проход: запланирован (короткая задача).`

This line declares a pending pass, not a completed one. Omit it for long workflows, stopped tasks, or an answer that is already the second-pass result. If the hook is not yet trusted/available, do not promise automatic execution; report the activation limitation instead.

The Windows helper is [scripts/short-task-stop.ps1](scripts/short-task-stop.ps1), registered only as a synchronous user-level `Stop` command in `~/.codex/hooks.json`. It consumes documented hook input, requires the pending line at the end of `last_assistant_message`, and skips `stop_hook_active: true`. It reads no transcript or state files, starts no process, calls no API, and changes no permissions. It returns a fixed `decision: block` continuation prompt; Codex performs the next model turn. It does not create another chat, agent, scheduled automation, or repeated original operation.

Codex requires native review and trust of the exact hook definition. Do not set trust hashes, use a trust-bypass flag, re-enable old quality controllers, or claim end-to-end activation from syntax checks. Use `/hooks` to review/trust the new entry. Official contract: [Codex Hooks](https://learn.chatgpt.com/docs/hooks), especially Stop and Review and trust hooks.

#### Continuation and report

The continuation is part of the original human task, not a fresh grant of authority. Re-read that task and the actual first-pass result, apply the Required Loop to the authorized result, and independently check its material claims. Do not merely rewrite the first answer. Do not broaden scope, obtain new permissions implicitly, run unrequested tests, or resume a stopped task. If the first answer was a clarification, perform response-only review and leave the question pending.

Run this broad post-answer pass once. A repair may receive one focused re-check using the smallest permitted validator. Do not restart the broad pass or emit the pending line again.

In the second answer, use this compact combined report, avoiding a duplicate boilerplate report:

```text
Саморевью — второй проход
- Статус: ready | partial | blocked | unknown
- Проверено: конкретный результат и доказательство
- Изменено при втором проходе: точные исправления | изменений нет
- Ограничения: отсутствуют | что осталось непроверенным
```

Keep the report proportionate. State the corrected result clearly when the first answer was wrong; do not bury a correction in the report. If runtime evidence is absent, report that the hook was prepared but its real continuation has not been confirmed.

When auditing or updating this skill, read [evaluation scenarios](references/evaluation-scenarios.md) and check every case. Do not load that reference during ordinary task execution.

### Report

End every final response with a visible self-review report. For a `ready` direct answer that uses no tools and creates no artifact, use one compact line:

`Саморевью: ready — проверено: конкретные пункты запроса и логика ответа; исправлено: нет | краткое описание; ограничения: отсутствуют.`

For tool use, multi-step work, artifacts, changes, or any non-ready result, end with a compact report:

```text
Саморевью
- Статус: ready | partial | blocked | unknown
- Результат: что фактически получено
- Проверено: конкретные проверки или источники доказательств
- Исправлено: нет | какие недочёты устранены до ответа
- Ограничения: отсутствуют | что осталось непроверенным
- Следующий шаг: только если он действительно нужен
```

Keep the report proportional to the task and do not expose the private issue list. Omit `Следующий шаг` when the work is ready and no action is useful. Never use `ready` when required validation failed, was skipped, is stale, or does not cover the latest result.

Name actual evidence. For tool-based work or artifacts, generic phrases such as "checked the request and logic" are insufficient; report the validator, read-back, diff, source, or saved result that was actually inspected. Do not claim that this report proves a private second pass occurred; it records the observable checks and outcome.
