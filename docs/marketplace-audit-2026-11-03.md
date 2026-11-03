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

## Follow-up: Fable 1.3.0 catalogue pin

At the owner's explicit request, the Fable entry and external lock now select version `1.3.0` at commit `fb941d7a10c816a77a8a67efd4c6abcec209542d` of the original repository. The initial audit figures and 1.2.0 source above describe the earlier snapshot. The updated pin includes the complete 1.3.0 package, its update/rollback helpers, bundled MCP artifacts and licence notices. Fable remains Codex-only; no installed profile or authentication is switched by this catalogue change.

Upstream `main` had subsequently advanced to 1.3.1 with a Windows busy-cache rollback fix. That update deliberately retained the requested 1.3.0 version rather than following `main`; the catalogue pin was not a claim that every local profile ran 1.3.0.

## Follow-up: Fable 1.3.1 catalogue pin

The next explicit owner request selects version `1.3.1` at commit `f49602f78fe017f5f9116b778303bba309d6c340`, the last upstream revision whose manifest advertises exactly 1.3.1. Both the Codex entry and external lock now select that complete original package, including the Windows busy-cache rollback fix.

At verification time, the separately installed local profile and upstream main already advertised 1.3.2. That later release adds stale-recovery serialization and exact Git-package byte verification. Those subsequent changes are not included in the explicitly requested 1.3.1 pin. This catalogue update does not switch an installed profile or change authentication.

Fable requires Node.js 20+ and a compatible Codex CLI. Gigma MCP retains the original owner callback flow and service permissions. Listing a package does not authenticate the user or provide missing host tools.

The `.codex` fallback mirror and sync scripts still cover only locally maintained plugins. Upstream plugins must be installed from the catalogue so that their complete runtime package is present.

## Verification and maintenance

The installed Codex CLI recognized both new entries, their versions and pinned Git sources through `codex plugin list --marketplace gigma-skills --available --json`. The packages were already installed from their original marketplaces; duplicate installations were deliberately not enabled. This is catalogue discovery and source verification, not a new authentication or live service test.

The catalogue validator now checks the upstream lock, full commit pins, runtime support, version/source consistency, source paths, duplicate ownership and duplicate entries while preserving strict local-path checks. Fourteen regression tests cover valid mixed catalogues and rejected drift/path escapes, including Windows drive paths. They run in CI alongside existing suites.

Update an upstream SHA and version in the lock and every supported runtime entry together. Run:

```sh
python validate_plugin.py
python -m unittest discover -s tests -p "test_*.py"
```

The implementation follows the native source formats in the [Codex marketplace parser](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/marketplace.rs) and [Claude marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces#choose-a-plugin-source).
