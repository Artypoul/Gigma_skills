# Capability gaps and verification

This package supplies instructions, source mappings, evaluation scenarios and
packaging tools, plus a local read-only MCP server for installed-skill search
and registered SKILL.md reading. It does not bundle an application backend,
hosted widget renderer or credentials. The upstream archive describes a provider's
environment; it does not contain the server implementations needed to reproduce
that environment. Installing this plugin is not proof those services exist.

## Before promising a capability

Inspect the actual host registry and applicable skill catalogue. Verify the
capability's schema, permission, target and availability with a harmless read
when possible. Distinguish an available service from a service that still needs
connection, implementation or credentials. On a missing capability, state the
specific gap, give a supported partial result and explain the implementation
needed. Never present a mockup or a proposed action as an executed operation.

## What the package supplies and what remains external

| Source capability | Supplied here | External requirement and acceptance check |
| --- | --- | --- |
| Baseline behaviour and skill-first routing | Instructions for simple and complex tasks | Host must actually load the skill; verify it in the live catalogue. Installation cannot force system-prompt priority or every-turn injection. Explicit invocation is available when implicit selection is uncertain. |
| ChatGPT through GitHub | A supported, version-pinned instruction-reading route in [chatgpt-github.md](chatgpt-github.md) | Connected GitHub with complete content reads, plus capabilities required by the task. Verify registry/lock agreement, manifests, all mandatory reads and actual tools. This does not install a plugin, pass the native MCP gate, save project settings or supply a reviewer. |
| Installed-skill search and reading | Bundled `search_skills` and `read_skill` MCP tools using Codex's enabled catalogue | Node.js 20+ and compatible Codex CLI on PATH. Verify tools/list, a real search and a registered-file read. Tool text is not proof of native skill activation. Other archived tool families still require their own implementations. |
| Web/image search, weather and sports | Selection, ordering and evidence rules | Host tools or authorized data providers. Verify fresh retrieval, supported leagues, game IDs, game statistics and standings separately; do not substitute scores for missing statistics. |
| Files, shell execution and file presentation | Workflow and verification rules | Actual reader/editor/shell and a supported delivery destination. Verify file creation and accessibility. |
| Connector discovery and selection | Discovery, provider-choice and consent workflow | Host directory, connection UI and authorized account integrations. Test a discovery hit, a miss, connected direct use and authentication failure. |
| Persistent application storage | Read/write/delete/list, scope, batching, error and conflict requirements | Application-owned storage adapter with real persistence and user isolation. Test save/reload across sessions, private/shared access, delete, not-found, denied access, timeout and concurrent updates. An in-memory journal is not cross-session storage. |
| AI calls inside a generated application | Integration, file-input, response handling and state-validation guidance | Explicit provider endpoint, approved authentication and application-owned client/backend. Test a real authorized request, tool continuation and invalid structured output. The agent's tools or credentials are not automatically available to the app. |
| Interactive maps/routes and place search | Place-ID, coordinate, itinerary and data-grounding rules | Places provider and map renderer; route computation when required. Test actual returned place IDs, route output and supported estimates. Text addresses or a static mockup do not prove an interactive map exists. |
| Scalable recipe widget | Ingredient, servings, scaling and timer rules | Host widget or a separately implemented UI. Test serving changes and matching ingredient references; disclose a text-only fallback. |
| Message composition and app cards | Drafting strategies and channel rules | Host compose/open/share UI where required. A text draft is valid drafting but does not prove a compose widget or delivery action. |
| Specialized document/design/authoring skills | Task-to-skill routing | Those skills and their dependencies must actually be installed. They were listed, not implemented, in the upstream prompt. Do not claim this package bundles Word/PDF/slides/spreadsheet renderers. |
| Memory/history and user context | Scope and evidence rules | Authorized host retrieval with explicit retention and account scope. Missing history is a gap, not a remembered preference. |
| Identity, safety, rendering, filesystem and network settings | Current-host inspection rules | Trusted runtime configuration. Provider identity, hidden reasoning controls, old mounts, policy and allowlists cannot be recreated by a skill. |

## Verification limits

Repository integrity checks detect source drift. Scenario checker tests reject
bad action plans such as answering before obtaining statistics or editing
before reading applicable skills. A separate model evaluation records decisions
against those scenarios. Plans do not call production APIs and do not establish
backend availability, model reliability in every conversation or universal host
compatibility. State which kind of evidence was actually collected.

## ChatGPT project settings

A repository template is not a saved project setting. Only an observed save in
the identified project and a real new project chat can establish inheritance.
Fresh isolated agents test the instruction content only. Report missing settings
access and unverified inheritance separately from GitHub source readiness.
