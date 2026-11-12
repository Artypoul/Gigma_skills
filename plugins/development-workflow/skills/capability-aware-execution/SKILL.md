---
name: capability-aware-execution
description: "Use when a request may need a specialist skill, real tool, connector, file, image, visualization, external integration, or durable artifact. Inspect what is actually available, route to the narrowest matching skill or tool, and report a gap honestly instead of inventing a capability or simulated result."
---

# Capability-Aware Execution

Treat the requested outcome and the available runtime as separate facts. Instructions do not create
a tool, connector, file delivery, browser, scheduler, or storage capability.

## Routing Workflow

1. Identify the requested outcome: conversational answer, source-backed answer, code change,
   durable file, visual, external action, or ongoing monitoring.
2. Check available skills first, then actual tools/connectors that are in scope.
3. Route to the narrowest matching specialist skill. For a durable artifact, load its creation
   skill before creating files.
4. Use a real tool only when it is available and authorized. Respect its confirmation and
   permission boundary.
5. If the capability is absent, name the exact gap and map it to a plugin, connector, app, or
   runtime requirement. Do not fabricate a UI, output, delivery, or integration result.
6. Verify the final artifact or external effect is accessible to the user before calling it done.

## Write Serialization and Cleanup

When an action can mutate a local or external resource, derive a stable resource key (for example a node, core, database, parser store, file path, or remote panel object) and allow only one writer for that key at a time. Serialize writes to the same key; a second writer waits or is rejected, and read-only checks may run in parallel only when they cannot race with a write.

For a timeout, transport error, or any unknown write result, stop mutation and perform a live `read-back` before deciding what to do. Do not retry blindly. Retry only when the read-back proves that the intended state was not applied, the operation has a safe idempotency key or equivalent repeat guarantee, and the original authorization and target lock still match; otherwise leave the state `unknown` or `partial`.

Every probe or temporary action declares `created_resources[]`, `cleanup[]`, and a `finally` path before it starts. Run cleanup sequentially even on failure, then read back the target and the created-resource list. Release the resource lock in `finally` only after cleanup and read-back; if release is unknown, keep the next writer blocked and report `unknown`. An unexplained process, file, record, lock, or temporary credential is an incomplete result, not a successful verification.

## Route Lock and Environment Guard

Before invoking a tool, record `requested route`, `actual route`, target, environment, and explicit prohibitions. The actual route must equal the requested route unless a new user signal authorizes the change and the reason is recorded. If browser or screen automation is forbidden, reject browser, Playwright, CUA, and screen-capture calls before invocation. For local Docker work, reject remote and production targets; do not silently move the task to another environment.

Include both `requested route` and `actual route` in the final report, together with the evidence for any authorized change. A successful tool result does not prove that the selected route or environment was correct.

## Browser Capability Routing

Treat these as separate capabilities: an in-app Browser tool, a Playwright CLI executable, and an importable Node package. The presence of one does not prove the others exist.

1. Prefer the installed Browser or Playwright specialist skill when it matches the task.
2. Before terminal automation, probe the exact execution path the script needs. `npx playwright --version` proves the CLI can launch; it does not prove `require('playwright')` or `import 'playwright'` will resolve in Node.
3. Use a Node API script only after the package resolves in that runtime. Otherwise use the supported CLI/in-app route or report the exact missing package; do not repeatedly retry incompatible imports.
4. Keep generated browser output in already ignored project locations, or classify it explicitly before handoff. Never call a browser-based result ready while its working tree contains unexplained generated artifacts.

## Rules

- A request for a file means create a real file when the relevant capability is available; a
  request for explanation remains conversational unless the user asks for an artifact.
- Prefer a connected first-party tool for data in scope over browsing or guessing.
- Do not pressure a user to connect a service. State the benefit and the missing capability.
- Read `references/capability-routing.md` when the request spans several possible capabilities.
