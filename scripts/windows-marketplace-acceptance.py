"""Real Codex marketplace acceptance on a disposable GitHub Windows runner only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BASELINE = "7488f662dfa56ba37382b5c7277009d77a311b9a"
URL = "https://marketplace-fixture.invalid/gigma-skills.git"
BRANCH = "acceptance"
NAME = "gigma-skills"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(args, *, cwd, env, check=True, input_text=None):
    result = subprocess.run(args, cwd=cwd, env=env, input=input_text, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def main():
    require(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_OS") == "Windows"
            and os.environ.get("WINDOWS_MARKETPLACE_ACCEPTANCE") == "1",
            "Run only in the dedicated disposable Windows GitHub Actions job")
    require(not os.environ.get("CODEX_HOME"), "CODEX_HOME override would contaminate the default profile")
    require(not os.environ.get("GIT_CONFIG_COUNT"), "Inherited Git command configuration would contaminate the fixture")
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_ADMIN_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID"):
        require(not os.environ.get(key), f"{key} is set; refusing a potentially authenticated test")
    profile = Path(os.environ["USERPROFILE"]).resolve()
    if os.environ.get("HOME"):
        require(Path(os.environ["HOME"]).resolve() == profile, "HOME and USERPROFILE differ; default profile is ambiguous")
    codex_home = profile / ".codex"
    require(not codex_home.exists(), f"Default Codex profile already exists: {codex_home}")
    repo = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    git = shutil.which("git")
    codex = shutil.which("codex")
    require(git and codex, "git and codex must be available on PATH")
    env = os.environ.copy()
    # Command-scoped settings are inherited by Codex's Git subprocesses.
    env.update(GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.longpaths", GIT_CONFIG_VALUE_0="false",
               GIT_CONFIG_KEY_1="url.file:///unused.insteadOf", GIT_CONFIG_VALUE_1=URL,
               GIT_TERMINAL_PROMPT="0")
    version = run([codex, "--version"], cwd=repo, env=env).stdout.strip()
    require(version == "codex-cli 0.167.1", f"Unexpected Codex version: {version!r}")
    candidate = run([git, "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    require(candidate == os.environ["CANDIDATE_SHA"], f"Checkout {candidate} differs from candidate {os.environ['CANDIDATE_SHA']}")
    require(run([git, "rev-parse", "--is-shallow-repository"], cwd=repo, env=env).stdout.strip() == "false", "History is shallow")
    print(f"Codex: {version}; Git: {git}; candidate: {candidate}; baseline: {BASELINE}", flush=True)
    with tempfile.TemporaryDirectory(prefix="marketplace-fixture-", dir=os.environ["RUNNER_TEMP"]) as tmp:
        fixture = Path(tmp) / "fixture.git"
        env["GIT_CONFIG_KEY_1"] = f"url.{fixture.as_uri()}.insteadOf"
        config = run([git, "config", "--show-origin", "--get", "core.longpaths"], cwd=tmp, env=env).stdout.strip()
        require(config.endswith("false"), f"Unexpected effective core.longpaths: {config}")
        print(f"Effective core.longpaths: {config}; fixture: {fixture}", flush=True)
        run([git, "init", "--bare", str(fixture)], cwd=tmp, env=env)
        run([git, "--git-dir", str(fixture), "fetch", str(repo),
             f"{BASELINE}:refs/heads/baseline", f"{candidate}:refs/heads/{BRANCH}"], cwd=tmp, env=env)
        def bare(*args, input_text=None):
            return run([git, "--git-dir", str(fixture), *args], cwd=tmp, env=env, input_text=input_text).stdout.strip()
        def cli(*args, check=True):
            return run([codex, "plugin", "marketplace", *args], cwd=tmp, env=env, check=check)
        def listing():
            return json.loads(cli("list", "--json").stdout)["marketplaces"]
        def select():
            entries = [entry for entry in listing() if entry["name"] == NAME]
            require(len(entries) == 1, f"Expected one {NAME} entry, got {entries!r}")
            return entries[0]
        def verify_checkout(root, revision):
            require(root.resolve() == (codex_home / ".tmp" / "marketplaces" / NAME).resolve(), f"Unexpected install root: {root}")
            head = run([git, "rev-parse", "HEAD"], cwd=root, env=env).stdout.strip()
            require(head == revision, f"Installed HEAD {head} != {revision}")
            sparse = run([git, "config", "--bool", "core.sparseCheckout"], cwd=root, env=env, check=False)
            require(sparse.returncode == 1 or (sparse.returncode == 0 and sparse.stdout.strip() == "false"), f"Sparse checkout is enabled or unreadable: {sparse.stdout} {sparse.stderr}")
            missing = run([git, "ls-files", "--deleted"], cwd=root, env=env).stdout.strip()
            require(not missing, f"Checkout is missing tracked files: {missing}")
            tracked = run([git, "ls-files", "-z"], cwd=root, env=env).stdout.split("\0")
            cache = [p for p in tracked if ".gitlab-ci-local" in p.split("/")]
            require(not cache, f"Tracked generated cache paths: {cache[:10]}")
            for path, dirs, _ in os.walk(root):
                if Path(path) == root and ".git" in dirs:
                    dirs.remove(".git")
                require(".gitlab-ci-local" not in dirs, f"Generated cache exists under {path}")
            actual = json.loads((root / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
            expected = json.loads((repo / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
            require(actual == expected and len(actual["plugins"]) > 0, "Installed catalogue differs from candidate")
            for plugin in actual["plugins"]:
                source = plugin["source"]
                if source["source"] == "local":
                    require((root / source["path"] / ".codex-plugin/plugin.json").is_file(), f"Missing plugin: {plugin['name']}")
            print(f"Installed {len(actual['plugins'])} catalogue entries; root length {len(str(root))}; tracked files {len(tracked)-1}", flush=True)
        bare("symbolic-ref", "HEAD", "refs/heads/baseline")
        baseline_paths = bare("ls-tree", "-r", "--name-only", BASELINE).splitlines()
        longest = max(baseline_paths, key=len)
        print(f"Longest baseline tracked path: {len(longest)} characters: {longest}", flush=True)
        print(f"Staging parent: {codex_home / '.tmp/marketplaces/.staging'} (length {len(str(codex_home / '.tmp/marketplaces/.staging'))})", flush=True)
        negative = cli("add", URL, "--ref", BRANCH, "--json", check=False)
        output = negative.stdout + negative.stderr
        require(negative.returncode != 0 and "filename too long" in output.lower(), f"Negative control did not fail with Filename too long (exit {negative.returncode}):\n{output}")
        require(not any(entry["name"] == NAME for entry in listing()), "Failed baseline was registered as a marketplace")
        print("Baseline rejected with Filename too long and was not registered", flush=True)
        bare("symbolic-ref", "HEAD", f"refs/heads/{BRANCH}")
        added = json.loads(cli("add", URL, "--ref", BRANCH, "--json").stdout)
        require(added["marketplaceName"] == NAME and not added["alreadyAdded"], f"Unexpected add result: {added}")
        root = Path(added["installedRoot"])
        entry = select()
        require(Path(entry["root"]).resolve() == root.resolve(), f"List root differs: {entry}")
        require(entry.get("marketplaceSource") == {"sourceType": "git", "source": URL}, f"Unexpected Git source: {entry}")
        verify_checkout(root, candidate)
        tree = bare("rev-parse", f"{candidate}^{{tree}}")
        env.update(GIT_AUTHOR_NAME="CI Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="CI Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        descendant = bare("commit-tree", tree, "-p", candidate, input_text="Acceptance refresh\n")
        require(descendant != candidate, "Fixture refresh revision must differ")
        bare("update-ref", f"refs/heads/{BRANCH}", descendant, candidate)
        upgraded = json.loads(cli("upgrade", NAME, "--json").stdout)
        require(upgraded["selectedMarketplaces"] == [NAME] and not upgraded["errors"] and
                any(Path(p).resolve() == root.resolve() for p in upgraded["upgradedRoots"]), f"Unexpected upgrade result: {upgraded}")
        verify_checkout(root, descendant)
        installed_tree = run([git, "rev-parse", "HEAD^{tree}"], cwd=root, env=env).stdout.strip()
        require(installed_tree == tree, f"Upgraded tree {installed_tree} != candidate tree {tree}")
        print(f"Upgrade refreshed to {descendant}; identical tree {tree}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Windows marketplace acceptance failed: {exc}", file=sys.stderr)
        sys.exit(1)
