#!/usr/bin/env python3
"""Validate the Gigma skills plugin catalogue.

This is intentionally dependency-free so it can run in Codex, Claude, and
GitHub Actions without bootstrapping a Python package.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = ROOT / "plugins"
CODEX_SKILLS = ROOT / ".codex" / "skills"
CODEX_REFERENCE = ROOT / ".codex" / "reference"
IGNORED_GENERATED_DIRS = {"__pycache__"}
IGNORED_GENERATED_SUFFIXES = {".pyc", ".pyo"}


errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - message matters more here
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")
        return {}


def require_string(obj: dict, key: str, path: Path) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{path.relative_to(ROOT)} missing non-empty string field {key!r}")
        return ""
    return value


def require_list(obj: dict, key: str, path: Path) -> list:
    value = obj.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{path.relative_to(ROOT)} missing non-empty list field {key!r}")
        return []
    return value


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_generated_cache(path: Path, base: Path) -> bool:
    relative = path.relative_to(base)
    return any(part in IGNORED_GENERATED_DIRS for part in relative.parts) or (
        path.suffix.lower() in IGNORED_GENERATED_SUFFIXES
    )


def load_external_plugins(plugin_names: set[str]) -> dict[str, dict]:
    """Validate immutable upstream sources without downloading or copying them."""
    path = ROOT / "external-plugins.lock.json"
    if not path.is_file():
        return {}
    lock = load_json(path)
    if not isinstance(lock, dict):
        fail("external-plugins.lock.json must be an object")
        return {}
    records = lock.get("plugins")
    if lock.get("schema_version") != 1 or not isinstance(records, list):
        fail("external-plugins.lock.json requires schema_version 1 and a plugins list")
        return {}
    result: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            fail("external plugin lock has a non-object entry")
            continue
        name = require_string(record, "name", path)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            fail(f"external plugin has invalid name {name!r}")
        if name in result or name in plugin_names:
            fail(f"external plugin {name!r} duplicates an existing owner")
            continue
        runtimes = record.get("runtimes")
        if not isinstance(runtimes, list) or not runtimes or any(x not in ("codex", "claude") for x in runtimes) or len(runtimes) != len(set(runtimes)):
            fail(f"external plugin {name!r} needs unique supported runtimes")
            record = {**record, "runtimes": []}
        for key in ("version", "license"):
            require_string(record, key, path)
        skills = record.get("skills")
        if not isinstance(skills, list) or not skills or any(not isinstance(x, str) or not x for x in skills):
            fail(f"external plugin {name!r} needs non-empty skill names")
        elif len(skills) != len(set(skills)):
            fail(f"external plugin {name!r} has duplicate skill names")
        source = record.get("source")
        if not isinstance(source, dict):
            fail(f"external plugin {name!r} needs a source object")
            result[name] = record
            continue
        if source.get("source") not in ("url", "git-subdir"):
            fail(f"external plugin {name!r} must use a pinned Git source")
        if not isinstance(source.get("sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", source["sha"]):
            fail(f"external plugin {name!r} requires a full immutable commit SHA")
        url = source.get("url")
        if not isinstance(url, str) or not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", url):
            fail(f"external plugin {name!r} needs an HTTPS GitHub URL without credentials or query")
        subdir = source.get("path")
        if source.get("source") == "git-subdir" or subdir is not None:
            if not isinstance(subdir, str) or not subdir or "\\" in subdir or re.match(r"^[A-Za-z]:", subdir) or PurePosixPath(subdir).is_absolute() or any(x in ("", ".", "..") for x in subdir.split("/")):
                fail(f"external plugin {name!r} has an invalid repository subdirectory")
        result[name] = record
    return result


def validate_marketplaces(plugin_names: set[str]) -> None:
    external = load_external_plugins(plugin_names)
    for runtime, path in (("codex", ROOT / ".agents/plugins/marketplace.json"), ("claude", ROOT / ".claude-plugin/marketplace.json")):
        data = load_json(path)
        entries = data.get("plugins")
        if not isinstance(entries, list):
            fail(f"{rel(path)} missing plugins list")
            continue
        expected = plugin_names | {name for name, record in external.items() if runtime in record["runtimes"]}
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                fail(f"{rel(path)} has non-object plugin entry")
                continue
            name = require_string(entry, "name", path)
            if name in seen:
                fail(f"{rel(path)} duplicates plugin {name!r}")
            seen.add(name)
            if name in external:
                record = external[name]
                if runtime not in record["runtimes"]:
                    fail(f"{rel(path)} plugin {name!r} does not support {runtime}")
                if entry.get("source") != record.get("source"):
                    fail(f"{rel(path)} plugin {name!r} differs from its locked Git source")
                if entry.get("version") != record.get("version"):
                    fail(f"{rel(path)} plugin {name!r} differs from its locked version")
                require_string(entry, "description", path)
                continue
            source = entry.get("source")
            if runtime == "codex":
                if not isinstance(source, dict) or source.get("source") != "local":
                    fail(f"{rel(path)} plugin {name!r} must use local source")
                    continue
                source = source.get("path")
            if not isinstance(source, str):
                fail(f"{rel(path)} plugin {name!r} needs a local source path")
                continue
            expected_raw = f"./plugins/{name}"
            resolved = (ROOT / source).resolve()
            if source != expected_raw:
                fail(f"{rel(path)} plugin {name!r} source must be {expected_raw!r}")
            if resolved != (PLUGIN_DIR / name).resolve():
                fail(f"{rel(path)} plugin {name!r} source resolves outside plugins/{name}")
            if not resolved.is_dir():
                fail(f"{rel(path)} plugin {name!r} source path does not exist")
            if runtime == "claude":
                require_string(entry, "description", path)
        if seen != expected:
            fail(f"{rel(path)} plugins {sorted(seen)} do not match expected {sorted(expected)}")


def validate_plugin_manifests(plugin_path: Path) -> None:
    name = plugin_path.name
    codex_manifest = plugin_path / ".codex-plugin" / "plugin.json"
    claude_manifest = plugin_path / ".claude-plugin" / "plugin.json"

    codex = load_json(codex_manifest)
    if require_string(codex, "name", codex_manifest) != name:
        fail(f"{rel(codex_manifest)} name must be {name!r}")
    for key in ("version", "description", "license", "skills"):
        require_string(codex, key, codex_manifest)
    author = codex.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("name"), str):
        fail(f"{rel(codex_manifest)} missing author.name")
    skills_field = codex.get("skills")
    if isinstance(skills_field, str) and not (plugin_path / skills_field).resolve().is_dir():
        fail(f"{rel(codex_manifest)} skills path does not exist: {skills_field}")
    interface = codex.get("interface")
    if not isinstance(interface, dict):
        fail(f"{rel(codex_manifest)} missing interface object")
    else:
        for key in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
            require_string(interface, key, codex_manifest)
        require_list(interface, "capabilities", codex_manifest)
        require_list(interface, "defaultPrompt", codex_manifest)

    claude = load_json(claude_manifest)
    if require_string(claude, "name", claude_manifest) != name:
        fail(f"{rel(claude_manifest)} name must be {name!r}")
    require_string(claude, "version", claude_manifest)
    require_string(claude, "description", claude_manifest)


def validate_plugin_hooks(plugin_path: Path) -> None:
    """Validate hook discovery and reject user-specific paths in runtime/tests."""

    codex_manifest = plugin_path / ".codex-plugin" / "plugin.json"
    manifest = load_json(codex_manifest)
    interface = manifest.get("interface")
    capabilities = interface.get("capabilities", []) if isinstance(interface, dict) else []
    declares_hooks = any(str(value).lower() == "hooks" for value in capabilities)

    hooks_dir = plugin_path / "hooks"
    hooks_path = hooks_dir / "hooks.json"
    if declares_hooks and not hooks_path.is_file():
        fail(f"{rel(codex_manifest)} declares hooks but {rel(hooks_path)} is missing")
    if hooks_dir.is_dir() and not hooks_path.is_file():
        fail(f"{rel(hooks_dir)} exists without hooks.json")

    if hooks_path.is_file():
        config = load_json(hooks_path)
        event_map = config.get("hooks")
        if not isinstance(event_map, dict) or not event_map:
            fail(f"{rel(hooks_path)} missing non-empty hooks object")
        else:
            for event, bindings in event_map.items():
                if not isinstance(bindings, list) or not bindings:
                    fail(f"{rel(hooks_path)} event {event!r} must contain hook bindings")
                    continue
                for binding in bindings:
                    commands = binding.get("hooks") if isinstance(binding, dict) else None
                    if not isinstance(commands, list) or not commands:
                        fail(f"{rel(hooks_path)} event {event!r} has an empty binding")
                        continue
                    for command in commands:
                        if not isinstance(command, dict) or command.get("type") != "command":
                            fail(f"{rel(hooks_path)} event {event!r} must use command hooks")
                            continue
                        if not isinstance(command.get("command"), str) or not command["command"].strip():
                            fail(f"{rel(hooks_path)} event {event!r} missing command")

    user_path = re.compile(r"(?i)(?:[A-Z]:\\Users\\[^\\/\s]+|/Users/[^/\s]+|/home/[^/\s]+)")
    for root in (hooks_dir, plugin_path / "tests"):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".ps1", ".py", ".sh", ".yaml", ".yml"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if user_path.search(text):
                fail(f"{rel(path)} contains a user-specific absolute path")


FRONTMATTER_RE = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---\r?\n", re.DOTALL)
FIELD_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):\s*(?P<value>.*)$")


def is_quoted(value: str) -> bool:
    value = value.strip()
    return len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}


def validate_skill(skill_path: Path) -> tuple[str | None, str | None]:
    text = skill_path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        fail(f"{rel(skill_path)} missing YAML frontmatter")
        return None, None

    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        field = FIELD_RE.match(line)
        if field:
            key = field.group("key")
            value = field.group("value").strip()
            fields[key] = value
            if key in {"description", "when_to_use"} and ": " in value and not is_quoted(value):
                fail(f"{rel(skill_path)} field {key!r} contains ': ' and must be quoted")

    name = fields.get("name")
    description = fields.get("description")
    if not name:
        fail(f"{rel(skill_path)} missing frontmatter name")
    if not description:
        fail(f"{rel(skill_path)} missing frontmatter description")
    if name and skill_path.parent.name != name.strip("'\""):
        fail(f"{rel(skill_path)} name {name!r} must match folder {skill_path.parent.name!r}")
    return name.strip("'\"") if name else None, description


def validate_skills(plugin_paths: list[Path]) -> None:
    names: dict[str, Path] = {}
    for plugin_path in plugin_paths:
        skill_files = sorted((plugin_path / "skills").glob("*/SKILL.md"))
        if not skill_files:
            fail(f"{rel(plugin_path)} has no skills/*/SKILL.md files")
        for skill_path in skill_files:
            name, _ = validate_skill(skill_path)
            if not name:
                continue
            previous = names.get(name)
            if previous:
                fail(f"duplicate skill name {name!r}: {rel(previous)} and {rel(skill_path)}")
            names[name] = skill_path

    for skill_path in sorted(CODEX_SKILLS.glob("*/SKILL.md")):
        validate_skill(skill_path)


def collect_canonical_files(plugin_paths: list[Path], child: str) -> dict[Path, Path]:
    result: dict[Path, Path] = {}
    for plugin_path in plugin_paths:
        base = plugin_path / child
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if is_generated_cache(path, base):
                continue
            relative = path.relative_to(base)
            if relative in result:
                fail(f"mirror path conflict for {child}/{relative.as_posix()}")
            result[relative] = path
    return result


def validate_codex_mirror(plugin_paths: list[Path]) -> None:
    mirror_pairs = [
        (collect_canonical_files(plugin_paths, "skills"), CODEX_SKILLS, ".codex/skills"),
        (collect_canonical_files(plugin_paths, "reference"), CODEX_REFERENCE, ".codex/reference"),
    ]

    for canonical, mirror_root, label in mirror_pairs:
        if not mirror_root.is_dir():
            fail(f"{label} directory missing")
            continue

        for relative, source_path in canonical.items():
            mirror_path = mirror_root / relative
            if not mirror_path.is_file():
                fail(f"{label}/{relative.as_posix()} missing; run bash sync-codex.sh")
            elif file_hash(source_path) != file_hash(mirror_path):
                fail(f"{label}/{relative.as_posix()} differs from {rel(source_path)}; run bash sync-codex.sh")

        expected = {relative for relative in canonical}
        for mirror_path in mirror_root.rglob("*"):
            if not mirror_path.is_file():
                continue
            if is_generated_cache(mirror_path, mirror_root):
                continue
            relative = mirror_path.relative_to(mirror_root)
            if relative not in expected:
                fail(f"{label}/{relative.as_posix()} is extra; run bash sync-codex.sh")


def validate_glaim_guardrails() -> None:
    stale_patterns = [
        "через backend/BFF",
        "source backend / BFF",
        "server-side-source-secret",
        "production frontend не получает",
        "browser-direct",
        "direct source-token",
        "miniapp -> ERP -> GLAIM",
        "frontend -> свой backend",
    ]
    search_roots = [
        ROOT / "AGENTS.md",
        ROOT / ".agents",
        ROOT / ".claude-plugin",
        ROOT / ".codex",
        ROOT / "plugins" / "glaim",
    ]
    for path in search_roots:
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        for file_path in files:
            if file_path.suffix == ".svg":
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in stale_patterns:
                if pattern in text:
                    fail(f"{rel(file_path)} contains stale GLAIM wording: {pattern!r}")

    contract = ROOT / "plugins" / "glaim" / "reference" / "chat-frontend-contract.md"
    skill = ROOT / "plugins" / "glaim" / "skills" / "connect-chat-frontend" / "SKILL.md"
    contract_text = contract.read_text(encoding="utf-8")
    skill_text = skill.read_text(encoding="utf-8")
    required_contract = "Production-доступ из публичного клиента разрешён только если source token"
    required_skill = "Production-доступ разрешён только если source token chat-scoped"
    if required_contract not in contract_text:
        fail(f"{rel(contract)} missing hard production source-token scope requirement")
    if required_skill not in skill_text:
        fail(f"{rel(skill)} missing hard production source-token scope requirement")


def main() -> int:
    plugin_paths = sorted([path for path in PLUGIN_DIR.iterdir() if path.is_dir()])
    plugin_names = {path.name for path in plugin_paths}
    if not plugin_paths:
        fail("plugins directory is empty")

    validate_marketplaces(plugin_names)
    for plugin_path in plugin_paths:
        validate_plugin_manifests(plugin_path)
        validate_plugin_hooks(plugin_path)
    validate_skills(plugin_paths)
    validate_codex_mirror(plugin_paths)
    validate_glaim_guardrails()

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 1

    external = load_external_plugins(plugin_names)
    remote_skills = sum(len(p["skills"]) for p in external.values())
    print(f"Validation OK: {len(plugin_paths)} local plugins, {len(list(PLUGIN_DIR.glob('*/skills/*/SKILL.md')))} local skills; {len(external)} pinned upstream plugins, {remote_skills} declared upstream skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
