# Codex capability matrix

This matrix translates the *workflow intent* of the historical Fable 5 tool catalogue into capability categories. It is not an API reference. Codex tools vary by host, client, configuration, permissions, and installed connectors. Discover the current registry and inspect each selected tool's live description/schema before use.

| Archived Fable 5 capability | Codex-side capability to discover | Adaptation rule |
| --- | --- | --- |
| User preference elicitation | Conversational clarification or supported interactive input | Ask only for a material missing constraint; do not force a questionnaire |
| Shell execution | Current shell/command execution surface | Inspect environment; use bounded, reviewable commands |
| File creation and editing | Workspace/file tools or shell/editor | Verify exact paths and inspect resulting files |
| Sports data | Current sports data connector or authoritative live source | Fetch current event data; do not guess fixtures or scores |
| Image search | Current image search/retrieval capability | Use only when imagery materially helps and the request is appropriate |
| Message composition | Drafting/writing experience | Draft only; sending requires explicit authorization |
| Places search and maps | Local-business/place search and supported map/directions capability | Use structured place results; never invent locations or route metrics |
| File presentation | Supported artifact/file delivery surface | Verify created artifact and exact destination |
| Recipe presentation | Structured recipe or ordinary text output | Preserve quantities, units, timing, and food-safety context |
| App recommendations | Current plugin/connector discovery | Search available integrations; user chooses before partner actions where required |
| MCP registry | Live tool/connector discovery | Use current registry results, never archived IDs |
| Text replacement | Current patch/editing tool | Read immediately before edit; review diff after |
| File/image viewing | Current file reader or image viewer | Choose by file type; inspect scans visually when needed |
| Weather | Current weather utility/data source | Resolve requested location and current time correctly |
| Web fetch/search | Current search and page retrieval | Read sources; cite with the host's citation format |
| Provider API in generated artifacts | Documented API/SDK or connected service, if actually available | Never assume ambient credentials or hidden proxy authentication |
| Legacy citation tags | Current citation mechanism | Do not emit legacy syntax or fabricate source IDs |
| Fixed filesystem/network configuration | Environment inspection and current host docs | Never copy archived paths or allowlists into Codex |

## Stable workflow families

| Need | How to choose |
| --- | --- |
| Repository inspection/editing | Use the current workspace, shell, and patch tools actually exposed |
| Skills | Use the current skill registry and read relevant skill files |
| GitHub | Use the connected GitHub integration or authorized git workflow available in the session |
| Web research | Use the current search/fetch service and cite retrieved sources |
| Browser/computer interaction | Use only when direct UI interaction is necessary |
| Parallel work | Use collaboration/subagent tools only if the current tool registry exposes them |
| Durable artifacts | Use the supported Library, Drive, or file-delivery workflow after reading its instructions |

## Safe invocation sequence

1. Discover the capability in the live registry.
2. Read its description and schema; verify permissions and required arguments.
3. Establish facts with read-only calls.
4. Perform authorized mutations sequentially, using returned IDs/version tokens.
5. Re-read the resulting state and report observed outcomes.
6. If the tool is unavailable, state that limitation instead of inventing a substitute.

## Detailed semantic crosswalk

The original tool schemas are deliberately not copied: they describe a different provider's API. The reusable behavior behind each tool is preserved here.

| Archived tool | Transferable behavior to preserve in Codex |
| --- | --- |
| `ask_user_input_v0` | Check existing context first. Ask only for material missing preferences. Prefer one direct conversational question; use an interactive selector only if the current host exposes one and the choices genuinely help. Do not repeat a user's A/B decision back as a questionnaire. |
| `bash_tool` | Run bounded shell commands through the current execution surface. Inspect the working directory and command effects; avoid destructive operations without authorization. |
| `create_file` | Create the requested artifact at the exact intended path. Check whether it already exists before writing; do not silently overwrite. |
| `fetch_sports_data` | Prefer sports-specific tools. A live/recent (last 24 hours) game requires score then statistics using the returned ID before answering. Broad league results require scores and standings. Disclose unsupported/failed data and give a supported partial answer; never invent fixtures or stats. |
| `image_search` | Retrieve images only when visual references materially improve the answer. Skip for primarily textual, coding, or technical-support tasks. |
| `message_compose_v1` | For simple transactional writing, provide one strong draft. When goals conflict (for example, preserve relationship versus create urgency), present genuinely different strategic approaches rather than superficial tone variants. Drafting does not authorize sending. |
| `places_map_display_v0` | Search for places first. Reuse exact returned place identifiers where the current map tool supports them. Distinguish simple pins from an itinerary; use grounded coordinates, stops, notes, and travel modes. Never invent route distance or ETA. |
| `places_search` | Decompose broad location discovery into focused queries, include geographic context, deduplicate results, and show only relevant matches. |
| `present_files` | Make only completed, verified deliverables available. Link the exact output, not a folder or guessed path; keep the handoff concise. |
| `recipe_display_v0` | Preserve ingredient quantities, units, servings, ordered steps, and timers. Use a structured recipe interface only if the current host supports it; otherwise provide a clear recipe in text. |
| `recommend_claude_apps` | The provider-specific app catalogue is excluded. Preserve only the principle: recommend current tools or products when they fit the user's task, after verifying their existence and relevance. |
| `search_mcp_registry` | Discover integrations by intent as well as by named provider when personal/company data or an external action is needed. Prefer already connected authorized sources. |
| `str_replace` | Make exact, localized edits with the current patch/editor tool. Re-read after editing because prior file views may be stale; review the diff. |
| `suggest_connectors` | Preserve informed user choice for third-party services. Explain the concrete benefit, require the host's opt-in flow when applicable, and never pressure the user or withhold an answer. |
| `view` | Choose a reader by file type. Inspect directories and text directly; inspect PDF/document page images when scans, screenshots, tables, or layout affect the answer. |
| `weather_fetch` | Use a current weather source for current conditions and forecasts. Resolve the requested location and local time; do not infer exact address when city-level context suffices. |
| `web_fetch` | Retrieve exact user-supplied or search-discovered URLs using the current fetch capability. Respect authentication, robots, and connector access limits. |
| `web_search` | Search current and unfamiliar facts when warranted. Use the current search syntax and citation format; verify consequential claims against sources actually read. |

## Source semantics that are intentionally not hard-coded

- Sports league enums, provider IDs, and response schemas are not portable.
- Map JSON schemas, place IDs, and itinerary payloads belong to the active map provider.
- Recipe widget fields and UI rendering are host-specific; the semantic content is portable.
- Connector registry IDs and opt-in mechanics are host-specific; user-choice principles are portable.
- Search operators, citation indices, and fetch URL restrictions vary by tool provider.
- File paths, output directories, package versions, and network allowlists are environment-specific.
- The Anthropic API-in-Artifact pattern is not portable as an ambient Codex feature. Use a documented API/SDK and explicit credentials only when the user's project/environment provides them.
