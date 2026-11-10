---
name: runtime-api-stack
description: Use when changing Gigma Runtime provider wiring, local REST or WebSocket transport, runtime credentials, API smoke tests, or session recovery.
---

# Runtime and API stack

Treat the local CLI API as the source of truth. Verify the real response shape before writing an adapter. Keep the runtime credential in a user-selected file or explicit environment path and pass it only to the child CLI process.

## Request flow

1. Confirm the provider and model in `config.toml`.
2. Confirm the credential path exists without printing its contents.
3. Start the local service and capture its loopback server token separately from the runtime credential.
4. Exercise model catalog, session creation, one read-only tool call, completion, and cancellation through the API.
5. Record structured diagnostics without secrets. A failed request must preserve its status, route, and safe error class.

## Failure handling

Use explicit states for missing credentials, expired credentials, invalid configuration, unauthorized responses, timeouts, cancellation, and unknown outcomes. Never retry an unknown external side effect automatically.

## Sources

- Tokio Axum examples for shared state, WebSocket coordination, and task cancellation https://github.com/tokio-rs/axum/tree/main/examples
- Axum state and handler guidance https://github.com/tokio-rs/axum/blob/main/axum/src/lib.rs
- Rust API Guidelines https://github.com/rust-lang/api-guidelines

The local Gigma CLI and runtime-service contracts remain authoritative over these general patterns.
