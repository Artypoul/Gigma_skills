---
name: read-code-first
description: "Read the actual code before answering any code-dependent request. Use for bug reports, route or file lookups, code review, feature work, refactors, stack traces, architecture questions, config or env questions, or any task where the answer should come from source files rather than memory. First inspect relevant files, symbols, callers, tests, or config with rg and file reads, then answer, review, plan, or edit."
---

# Read Code First

Inspect source truth before answering.

## Workflow

1. If the request is broad or ambiguous enough that the expected deliverable is unclear, ask one short question about the result or switch to the stricter `code-evidence-first` flow.
2. If the user already named the exact result, do not ask a duplicate question. Briefly lock the target in your own reasoning and continue.
3. Translate the request into likely artifacts: route, component, hook, class, function, API slice, config reader, test, build file, schema, or log parser.
4. Search first with `rg` or `rg --files`. Prefer exact symbols, paths, route fragments, error codes, and config keys over broad reads.
5. Open the minimum relevant files and read enough surrounding lines to understand control flow, data flow, and ownership.
6. Read both the definition and at least one real usage when behavior depends on context.
7. Only then answer, plan, review, or edit.
8. If the code still does not answer the question, say what was checked and what remains unknown.

## Clarify The Result

- Keep the clarification short and outcome-focused.
- Use the stricter `code-evidence-first` skill when ambiguity is material enough to change the work.
- Prefer one concrete question such as "What do you want as the result: a quick answer, a fix, or a review?"
- Avoid vague prompts like "Tell me more".
- For tiny factual lookups where the expected output is obvious, skip the clarification.

## Search Order

- For routes and navigation, search route constants, router maps, `navigate`, and page paths.
- For behavior questions, search the concrete symbol first, then its callers, then adjacent helpers.
- For runtime, env, and deploy questions, inspect config readers, env type files, runtime bootstrap, and the calling code.
- For errors and stack traces, search the exact message, code, or endpoint string first.
- For regressions, read adjacent tests before changing behavior when tests exist.
- For unfamiliar subsystems, prefer primary files over summaries or history notes.

## Rules

- Do not answer code questions from memory alone.
- Do not skip the outcome clarification when the request can reasonably mean different kinds of work.
- Prefer file-backed answers over speculative explanations.
- For simple code facts, inspect the exact file anyway.
- If the user pasted a snippet but a local codebase exists, inspect the surrounding source before concluding when feasible.
- Cite file paths and line references when they materially help the user.
- If the request is not about code, normal behavior is fine.

## Primary Sources Beyond Code

Reading the repository is not enough when the claim is about something the repository does not own.

- A provider requirement, external API contract, env variable name, database column, or CLI flag reaches a plan, an answer, or code only after you confirmed it in a primary source: provider documentation, the real `.env` or config file, the migration or schema, or actual `--help` output. "It is usually required" is not a source.
- Model the domain from the schema. Read migrations, foreign keys, and casts before stating what an entity is for or how it relates to another one. A relation inferred from service code, a sibling project, or project memory is a hypothesis, and must be labeled as one.
- When you reconstruct what happened from logs, separate observed events from inferred ones. Never present a reconstructed sequence of user actions as an established fact.
- If the user pushes back on a claim, produce the source or drop the claim. Do not defend a guess with confidence.

For architecture, data-flow, and business-logic explanations, keep three classes visibly separate:

- **Подтверждено:** directly supported by named code, schema/FK, runtime output, generated contract, or a passing test.
- **Вывод:** the best explanation derived from several facts, with the inference and missing proof named.
- **Продуктовое решение:** desired behavior or architecture that is not yet current implementation and needs owner approval when several valid options exist.

Do not smooth over a missing FK, runtime path, ownership link, or test by describing the intended architecture as the current one. If that distinction changes the user's decision, lead with it.

## Minimum Evidence

Before giving a code-dependent answer, inspect at least one of:

- the defining source file,
- the caller, route, or container that uses it,
- an adjacent test or config file when setup affects behavior,
- or the exact snippet or stack-trace location the user referenced when no wider code is available.
