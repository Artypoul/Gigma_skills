---
name: tauri-rust-stack
description: Use when changing Tauri commands, Rust process lifecycle, Tokio tasks, WebView windows, PTY sessions, IPC, or native configuration in Gigma Work.
---

# Tauri and Rust stack

Keep native behavior in `src-tauri/src`. The renderer talks to Rust through the typed contract. Every new command must be registered in `lib.rs` and represented in the renderer contract.

## Lifecycle rules

- Commands that create or close windows are async.
- Backend start, stop, restart, and unexpected exit must leave process state, REST state, WebSocket state, and frontend events consistent.
- Long-running work must not block the Tauri event loop. Use Tokio tasks or the existing blocking boundary for filesystem and database work.
- Child processes must be killed on every failed startup path and on application exit.
- Do not log bearer tokens, runtime keys, callback URIs, or full request bodies.

## Rust API shape

Prefer small typed structs, explicit `Result` errors, and deterministic ownership. Keep shared state in the existing `AppState` and per-channel backend map. Add a unit test for each new error branch or lifecycle invariant.

## Sources

- Official Tauri project and architecture https://github.com/tauri-apps/tauri
- Official Tauri project generator and React TypeScript templates https://github.com/tauri-apps/create-tauri-app
- Rust API Guidelines https://github.com/rust-lang/api-guidelines
- Tokio's official runtime and task documentation https://github.com/tokio-rs/tokio

Use these as design references. The local Tauri lifecycle and security rules take precedence over generic examples.
