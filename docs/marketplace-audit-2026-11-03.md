# Local marketplace audit — 2026-11-03

The owner requested a check of locally available skills and the addition of missing owner packages to Gigma Skills. Built-in OpenAI skills and connector packages remain external, as explicitly selected by the owner.

## Observed inventory

- The enabled Codex registry returned 89 skills across two complete pages, with no partial results or warnings.
- All 68 Gigma Skills entries already existed in the canonical catalogue and matched their installed SKILL.md files.
- All 425 tracked Gigma plugin payload files matched the installed cache after newline normalization. No unpublished cache-only changes or missing cache files were found.
- Frontmatter parsed for all 68 local skills; their static Markdown file links resolved.
- Thirteen system/OpenAI runtime skills remain provider-owned. The personal short VPS entry is an intentional compatibility alias, not another missing implementation.

Seven owner-package skills were absent from Gigma Skills:

| Package | Skills | Version | Runtime |
|---|---:|---|---|
| `fable5-codex` | 1 | 1.2.0 | Codex |
| `gigma-mcp` | 6 | 0.2.0 | Codex and Claude |

The Codex catalogue now exposes 13 plugins: 11 local plugins with 68 skills and two upstream packages with seven declared skills. The Claude catalogue contains 12 plugins; the Codex-only Fable package is not advertised there.

## Ownership and installation

Both packages are independently maintained in their original repositories. Catalogue entries reference complete Git packages with immutable commit SHAs recorded in `external-plugins.lock.json`. This preserves MCP components, references, licences and upstream ownership instead of copying only SKILL.md or creating a second code fork.

- Fable: `Artypoul/claude-fable-5-system-prompt`, commit `d9a557b102309797cf9c028d5d19fde3d9174aa8`.
- Gigma MCP: `Artypoul/gigma-mcp`, subdirectory `plugins/gigma-mcp`, commit `2d9332aa90baa51a09f4d9ef29127c4a2c71979c`.

Both SHAs matched the upstream repository HEADs during this audit. Fable's original archive retains its upstream ownership notice; its code and archive are not republished into this repository.

New installations may select `fable5-codex@gigma-skills` or `gigma-mcp@gigma-skills`. Existing installations from `@fable5` or `@gigma-mcp` remain valid. Choose one source for a package: enabling both sources can duplicate qualified skills and MCP server names. This audit does not switch existing sources, enable additional MCP servers or change account authorization.

Fable requires Node.js 20+ and a compatible Codex CLI. Gigma MCP retains the original owner callback flow and service permissions. Listing a package does not authenticate the user or provide missing host tools.

The `.codex` fallback mirror and sync scripts still cover only locally maintained plugins. Upstream plugins must be installed from the catalogue so that their complete runtime package is present.

## Verification and maintenance

The installed Codex CLI recognized both new entries, their versions and pinned Git sources through `codex plugin list --marketplace gigma-skills --available --json`. The packages were already installed from their original marketplaces; duplicate installations were deliberately not enabled. This is catalogue discovery and source verification, not a new authentication or live service test.

The catalogue validator now checks the upstream lock, full commit pins, runtime support, version/source consistency, source paths, duplicate ownership and duplicate entries while preserving strict local-path checks. Thirteen regression tests cover valid mixed catalogues and rejected drift/path escapes. They run in CI alongside existing suites.

Update an upstream SHA and version in the lock and every supported runtime entry together. Run:

```sh
python validate_plugin.py
python -m unittest discover -s tests -p "test_*.py"
```

The implementation follows the native source formats in the [Codex marketplace parser](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/marketplace.rs) and [Claude marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces#choose-a-plugin-source).
