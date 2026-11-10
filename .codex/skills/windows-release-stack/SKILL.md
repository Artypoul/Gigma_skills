---
name: windows-release-stack
description: Use when changing Windows packaging, embedded CLI archives, NSIS/MSI installers, portable ZIPs, GitHub Actions, or release metadata.
---

# Windows release stack

The single supported Windows entry point is `npm run build:windows`. It rebuilds `vendor/gigma-cli`, refreshes the pinned archive and checksums, runs the renderer build, invokes Tauri, and verifies the packaged Desktop executable.

## Release invariants

- The Desktop EXE contains the CLI and required license files.
- The package contains no adjacent CLI dependency.
- Archive and per-file checksums match `src/distribution.json`.
- Installer paths with spaces are tested.
- CI failures caused by external account or runner state are reported separately from code failures.
- A deploy claim requires a fresh artifact or deployment hash check after merge.

## Sources

- Official Tauri project and bundler guidance https://github.com/tauri-apps/tauri
- Official Tauri GitHub Action https://github.com/tauri-apps/tauri-action
- Official Tauri project generator https://github.com/tauri-apps/create-tauri-app

Keep the local `scripts/build-vendored-cli.mjs`, `scripts/prepare-bundled-cli.mjs`, and `scripts/package-windows-build.ps1` contracts aligned with this flow.
