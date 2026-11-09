# Upstream and local adaptations

- [cc-devops-skills](https://github.com/akin-ozer/cc-devops-skills), Akin Ozer, Apache-2.0, commit `276af751e659315aaf56d3ad13d7c26f4e72e28a`: 31 skill directories, including their nested licenses and resources.
- [vps-forge](https://github.com/mountain-beaver/vps-forge), Hung Up, MIT, commit `de8b1c084559b4175be7aaabf5cb61a4d5a19580`: complete `skills/vps-forge` directory.

License texts are in `licenses/`; nested third-party licenses remain in their source directories. Text files are normalized to LF. Each of the 31 DevOps skills has a Codex portability note for companion and installed-resource paths, placed after the H1 or after frontmatter when no H1 exists. `vps-forge/SKILL.md` has the local Codex companion routing and authorization boundaries in §4 and §9. Local plugin manifests and marketplace metadata package the skills without upstream hooks, MCP or apps.

Version 0.1.1 also fixes the upstream `vps-forge/assets/cloud-init.yaml` first-boot lockout. The owner selects `password` or `nopasswd` sudo. Password mode generates the credential on the target into the admin-owned `~/SUDO-PASSWORD` file (0600), with exclusive creation and no log output. Both modes validate sudoers and prove sudo access before activating the SSH drop-in that disables root. Failed or unselected policy stops first-boot commands while leaving that restrictive drop-in inactive. Tests in `tests/test_vps_cloud_init.py` exercise this bootstrap on temporary files in Linux CI; no live VPS is used.
