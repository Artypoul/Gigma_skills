# Installing Gigma Skills on Windows

In the Codex marketplace UI, use:

- **Repository:** `https://github.com/Artypoul/Gigma_skills`
- **Git ref:** `main`
- **Selective paths:** leave empty for the full catalogue.

Then choose the desired plugins from `gigma-skills`. `plugins/codex` is not a valid checkout filter for this repository; the catalogue and its local plugins are elsewhere in the tree.

## If Git reports `Filename too long`

The repository previously included generated `.gitlab-ci-local` cache files whose deeply nested paths, combined with Codex's staging directory, could exceed a Windows Git checkout limit. The fix removes these generated files and prevents the sync from copying them into the Codex mirror. It does not guarantee that every future path, installation prefix, or Windows program will fit within its limits. Microsoft documents [Windows path length limits](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation).

As a short-term workaround, in a Windows terminal using the same account as Codex:

```powershell
where.exe git
git --version
git config --global core.longpaths true
git config --show-origin --show-scope --get-all core.longpaths
git config --bool --get core.longpaths
```

Confirm the Git executable is the Git for Windows installation used by Codex and that the effective setting is `true` (a later, higher-precedence value can override the global value). Git documents [configuration scopes and precedence](https://git-scm.com/docs/git-config#SCOPES), and Git for Windows documents [long path support](https://github.com/git-for-windows/git/wiki/FAQ#i-have-a-repository-with-long-paths-and-i-cant-check-it-out). Restart Codex so it picks up the environment, then retry. This is a change you make on your own machine; the repository or assistant does not make it for you.

Alternatively, clone into a short path and add that local checkout as the marketplace:

```powershell
git clone https://github.com/Artypoul/Gigma_skills C:\gigma
codex plugin marketplace add C:\gigma
```

A local marketplace uses that checkout; update it with `git -C C:\gigma pull` as appropriate. A short path reduces the length but cannot guarantee checkout for all future files.

For a pre-merge test, setting **Git ref** to the PR branch alone may still require the workaround. In Codex CLI 0.167.1, the full Git checkout clones the default branch first and then switches to the requested ref, so a long path on the default branch can fail before the PR branch is reached. See the pinned [Codex marketplace clone implementation](https://github.com/openai/codex/blob/rust-v0.167.1/codex-rs/core-plugins/src/marketplace_add/install.rs) and [marketplace CLI](https://github.com/openai/codex/blob/rust-v0.167.1/codex-rs/cli/src/marketplace_cmd.rs).

The Windows CI job uses the real pinned `@openai/codex@0.167.1` CLI to test Git marketplace add and an actual refresh against an isolated local fixture, with `core.longpaths=false`. It includes a historical failing checkout as a negative control. This is a CLI acceptance test, not a desktop GUI end-to-end test; consult the job result for the revision under test.
