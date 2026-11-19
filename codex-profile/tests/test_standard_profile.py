"""Real Standard Codex profile install regression and source ownership tests.

Tests use only temporary Codex homes. An unrelated user's profile is never touched.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "codex-profile"
INSTALLER = PROFILE / "setup.ps1"
PWSH = shutil.which("pwsh")
REQUIRE_PWSH = os.environ.get("REQUIRE_STANDARD_PROFILE_PWSH") == "1"


def skill_sources(repo: Path = ROOT) -> dict[str, list[Path]]:
    """Use the same two source roots and SKILL.md predicate as setup.ps1."""
    sources: dict[str, list[Path]] = defaultdict(list)
    plugins = repo / "plugins"
    if plugins.is_dir():
        for plugin in sorted(plugins.iterdir()):
            skills_root = plugin / "skills"
            if not plugin.is_dir() or not skills_root.is_dir():
                continue
            for skill in sorted(skills_root.iterdir()):
                if skill.is_dir() and (skill / "SKILL.md").is_file():
                    sources[skill.name].append(skill)
    personal = repo / "codex-profile" / "personal-skills"
    if personal.is_dir():
        for skill in sorted(personal.iterdir()):
            if skill.is_dir() and (skill / "SKILL.md").is_file():
                sources[skill.name].append(skill)
    return sources


def file_inventory(path: Path) -> dict[str, str]:
    """Complete file inventory with byte digests, including helper files."""
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def run_setup(home: Path, *extra_args: str, installer: Path = INSTALLER) -> subprocess.CompletedProcess[str]:
    if not PWSH:
        raise RuntimeError("PowerShell 7 (pwsh) is required for Standard installation")
    return subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-File", str(installer),
         "-CodexHome", str(home), *extra_args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )


class StandardSourceOwnershipTests(unittest.TestCase):
    def test_source_skill_names_are_unique(self):
        sources = skill_sources()
        duplicates = {name for name, paths in sources.items() if len(paths) != 1}
        self.assertEqual(duplicates, set(), {
            name: [str(path) for path in paths] for name, paths in sources.items()
            if len(paths) != 1
        })
        for name in ("banquet-image-generation", "counterparty-audit-investigation",
                     "figma-cli", "figma-poster-positioning",
                     "no-unapproved-product-limits", "self-review-report",
                     "segment-anything", "agent-session-execution"):
            self.assertIn(name, sources)


class StandardInstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PWSH:
            if REQUIRE_PWSH:
                raise AssertionError("CI requires pwsh for real Standard profile tests")
            raise unittest.SkipTest("PowerShell 7 not installed; no Standard runtime evidence")

    def assert_installed(self, home: Path) -> None:
        sources = skill_sources()
        names = set(sources)
        installed = home / "skills"
        self.assertEqual(
            {p.name for p in installed.iterdir() if p.is_dir()}, names
        )
        manifest = home / ".gigma-skills-profile-manifest"
        self.assertTrue(manifest.is_file())
        self.assertEqual(set(manifest.read_text(encoding="utf-8-sig").splitlines()), names)
        for name, roots in sources.items():
            with self.subTest(name=name):
                self.assertEqual(len(roots), 1)
                self.assertEqual(
                    file_inventory(installed / name), file_inventory(roots[0]),
                    f"Installed {name} is not a complete copy of its canonical source",
                )
        self.assertEqual(
            (home / "AGENTS.md").read_bytes(), (PROFILE / "global-AGENTS.md").read_bytes()
        )

    def test_default_install_uses_complete_canonical_trees(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "new user" / "codex home"
            result = run_setup(home)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_installed(home)
            sources = skill_sources()
            for name in ("banquet-image-generation", "counterparty-audit-investigation",
                         "figma-cli", "figma-poster-positioning",
                         "no-unapproved-product-limits", "self-review-report"):
                self.assertIn("plugins", sources[name][0].parts)
            self.assertEqual(sources["segment-anything"][0].parent.name, "personal-skills")

    def test_managed_reinstall_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            first = run_setup(home)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            before = file_inventory(home)
            second = run_setup(home)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(file_inventory(home), before)
            self.assert_installed(home)

    def test_unmanaged_destination_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            dest = home / "skills" / "segment-anything"
            dest.mkdir(parents=True)
            (dest / "SKILL.md").write_text("user's unmanaged skill\n", encoding="utf-8")
            before = file_inventory(home)
            result = run_setup(home)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("segment-anything", result.stdout + result.stderr)
            self.assertEqual(file_inventory(home), before)

    def test_existing_global_agents_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            home.mkdir()
            custom = "# My own global instructions\n"
            (home / "AGENTS.md").write_text(custom, encoding="utf-8")
            result = run_setup(home)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((home / "AGENTS.md").read_text(encoding="utf-8"), custom)
            self.assertEqual(list(home.glob("AGENTS.md.gigma-backup-*")), [])

    def test_unknown_source_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "isolated repo"
            local_profile = repo / "codex-profile"
            local_profile.mkdir(parents=True)
            shutil.copy2(INSTALLER, local_profile / "setup.ps1")
            for path in (
                repo / "plugins" / "custom" / "skills" / "collision",
                local_profile / "personal-skills" / "collision",
            ):
                path.mkdir(parents=True)
                (path / "SKILL.md").write_text("# collision\n", encoding="utf-8")
            home = Path(td) / "home"
            result = run_setup(home, installer=local_profile / "setup.ps1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Duplicate skill names", result.stdout + result.stderr)
            self.assertFalse((home / ".gigma-skills-profile-manifest").exists())

    def test_self_review_helpers_are_present_without_hook_installation(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            result = run_setup(home)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(
                (home / "skills" / "self-review-report" / "scripts" /
                 "short-task-stop.ps1").is_file()
            )
            self.assertTrue((home / "skills" / "agent-session-execution" / "SKILL.md").is_file())
            self.assertFalse((home / "hooks.json").exists())
            self.assertFalse((home / "profile-hooks").exists())


if __name__ == "__main__":
    unittest.main()
