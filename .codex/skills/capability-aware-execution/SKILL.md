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
