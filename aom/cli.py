"""
aom — AI Operation Manager

Manage versioned AI operations across projects, using git tags as a
lightweight package registry.

An "operation" is any versioned markdown artifact managed by aom.
Operation types include: skills, commands, agents, and hooks.

Commands:
  init      Set up a project: detect agent, configure repositories
  fetch     Refresh the operation index from all remote repositories
  install   Install an operation into the local or global scope
  list      Show available and installed operations with version info
  sync      Install all required operations declared in the project config
  remove    Uninstall an operation from the local or global scope
  update    Upgrade an operation to the latest available version
  view      View details about an operation (e.g. available versions)
  env       Display environment configuration and diagnostics

Run `aom <command> --help` for command-specific options and examples.
"""
from __future__ import annotations

import argparse
import json
import sys
import io
from pathlib import Path
from .config import (
    AGENT_MAP,
    ARTIFACT_TYPES,
    ensure_global_dir,
    ensure_local_dir,
    get_config_file,
    get_global_dir,
    get_global_registry,
    get_local_dir,
    get_local_registry,
    get_local_paths,
    get_repo_urls,
)
from .discovery import scan_git_repository, scan_installed, scan_repository
from .git import GitRepo
from .installer import install, uninstall
from .manifest import parse_manifest, parse_repo_url, write_repo_url
from .models import SkillRecord, VersionRequirement, parse_version
from .registry import Registry
from .resolver import resolve, resolve_all, resolve_latest
from .settings import (
    get_repo_urls as get_global_repo_urls,
    set_repo_urls as set_global_repo_urls,
    get_local_paths as get_global_local_paths,
    set_local_paths as set_global_local_paths,
    get_fetch_ttl,
)


# ---------------------------------------------------------------------------
# Colour helpers (no external dep)
# ---------------------------------------------------------------------------

_USE_COLOUR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text


def green(t: str) -> str: return _c(t, "32")
def yellow(t: str) -> str: return _c(t, "33")
def red(t: str) -> str: return _c(t, "31")
def bold(t: str) -> str: return _c(t, "1")
def dim(t: str) -> str: return _c(t, "2")


# ---------------------------------------------------------------------------
# Repository source helpers (multi-repo)
# ---------------------------------------------------------------------------

def _get_git_repos(project_dir=None) -> list[GitRepo]:
    """Return GitRepo instances for all configured repository URLs."""
    urls = get_repo_urls(project_dir)
    return [GitRepo(url) for url in urls]


def _get_repo_records(git_repos: list[GitRepo]) -> list:
    """Return aggregated skill records from all git repos and local filesystem paths."""
    records: list = []
    for repo in git_repos:
        records.extend(scan_git_repository(repo))
    # Also scan configured local filesystem paths
    for local_path in get_local_paths():
        p = Path(local_path)
        if p.is_dir():
            records.extend(scan_repository(p))
    return records


def _fetch_if_requested(git_repos: list[GitRepo], fetch: bool, no_fetch: bool = False) -> None:
    """Refresh git repos based on flags and TTL.

    Priority:
      --fetch     → always fetch (force refresh)
      --no-fetch  → never fetch (offline mode), only clone if needed
      (default)   → auto-fetch if stale (TTL-based)
    """
    ttl = get_fetch_ttl()
    for repo in git_repos:
        if fetch:
            repo.fetch(verbose=True)
        elif no_fetch:
            if not repo.is_cloned:
                repo.ensure_cloned(verbose=True)
        else:
            repo.fetch_if_stale(ttl_seconds=ttl, verbose=True)


def _find_git_repo_for_record(record: SkillRecord, git_repos: list[GitRepo]) -> GitRepo | None:
    """Find the GitRepo that contains *record* (by matching git_tag against tags)."""
    if not record.git_tag or not git_repos:
        return None
    for repo in git_repos:
        if not repo.is_cloned:
            continue
        tags = repo.list_skill_tags()
        tag_set = {f"{t}/{n}@{v}" for t, n, v in tags}
        if record.git_tag in tag_set:
            return repo
    # Fallback: return first repo (best effort)
    return git_repos[0] if git_repos else None


# ---------------------------------------------------------------------------
# Subcommand: fetch
# ---------------------------------------------------------------------------

def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch latest tags from all configured remote repositories."""
    git_repos = _get_git_repos(getattr(args, "project_dir", None))

    if not git_repos:
        print(yellow("No repositories configured. Run 'aom init' to set up."))
        return 1

    total_tags = 0
    errors = 0
    for repo in git_repos:
        try:
            repo.fetch(verbose=True)
            tags = repo.list_skill_tags()
            total_tags += len(tags)
            print(green(f"  ✓ {repo.url} — {len(tags)} skill version(s)"))
        except RuntimeError as exc:
            print(red(f"  ✗ {repo.url}: {exc}"))
            errors += 1

    print()
    if errors:
        print(yellow(f"Fetched with {errors} error(s). {total_tags} skill version(s) available."))
        return 1
    print(green(f"✓ All repositories up to date. {total_tags} skill version(s) available."))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: install
# ---------------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> int:
    """Install a skill into the global or local scope."""
    git_repos = _get_git_repos(args.project_dir)
    _fetch_if_requested(git_repos, getattr(args, "fetch", False), getattr(args, "no_fetch", False))

    # Parse "name:version" or "name"
    spec = args.spec
    if ":" in spec:
        name, version_constraint = spec.split(":", 1)
    else:
        name, version_constraint = spec, "latest"

    repo_records = _get_repo_records(git_repos)
    req = VersionRequirement(name=name, constraint=version_constraint)

    global_dir = get_global_dir()
    global_records = scan_installed(global_dir) if global_dir.exists() else []
    local_dir = get_local_dir(args.project_dir)
    local_records = scan_installed(local_dir) if local_dir.exists() else []

    record = resolve(req, repo_records, global_records, local_records)

    if record is None:
        print(red(f"✗ Skill not found: {name}@{version_constraint}"))
        _suggest_similar(name, repo_records)
        if git_repos and not getattr(args, "fetch", False):
            print(dim("  Tip: run with --fetch to refresh the tag index from the remote."))
        return 1

    if args.global_:
        scope_label = "global"
        ensure_global_dir()
        target_dir = get_global_dir()
        registry = Registry(get_global_registry())
    else:
        scope_label = "local"
        project_dir = args.project_dir
        ensure_local_dir(project_dir)
        target_dir = get_local_dir(project_dir)
        registry = Registry(get_local_registry(project_dir))

    git_repo = _find_git_repo_for_record(record, git_repos)
    dest = install(record, target_dir, registry, overwrite=not args.no_overwrite, git_repo=git_repo)
    v = record.version.raw if record.version else "unknown"
    print(green(f"✓ Installed {record.name}@{v} [{scope_label}] → {dest}"))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    """List all known skills with their installed and available versions."""
    git_repos = _get_git_repos(args.project_dir)
    _fetch_if_requested(git_repos, getattr(args, "fetch", False), getattr(args, "no_fetch", False))

    repo_records = _get_repo_records(git_repos)
    global_dir = get_global_dir()
    global_records = scan_installed(global_dir) if global_dir.exists() else []
    local_dir = get_local_dir(args.project_dir)
    local_records = scan_installed(local_dir) if local_dir.exists() else []

    # Collect all unique names across all sources
    all_names: set[str] = set()
    for r in repo_records + global_records + local_records:
        if not args.type or r.artifact_type == args.type:
            all_names.add(r.name)

    if not all_names:
        print(yellow("No skills found."))
        return 0

    if args.json:
        return _list_json(sorted(all_names), repo_records, global_records, local_records)

    return _list_table(sorted(all_names), repo_records, global_records, local_records)


def _list_table(
    names: list[str],
    repo_records: list[SkillRecord],
    global_records: list[SkillRecord],
    local_records: list[SkillRecord],
) -> int:
    col_w = max(len(n) for n in names) + 2

    print()
    print(bold(f"{'SKILL':<{col_w}}  {'LOCAL':<12}  {'GLOBAL':<12}  {'LATEST'}"))
    print("-" * (col_w + 42))

    for name in names:
        local_v = _best_version_str(name, local_records)
        global_v = _best_version_str(name, global_records)
        latest_v = _best_version_str(name, repo_records, stable_only=True)

        local_d = green(local_v) if local_v != "—" else dim("—")
        global_d = yellow(global_v) if global_v != "—" else dim("—")
        latest_d = bold(latest_v) if latest_v != "—" else dim("—")

        print(f"{name:<{col_w}}  {local_d:<21}  {global_d:<21}  {latest_d}")

    print()
    return 0


def _list_json(
    names: list[str],
    repo_records: list[SkillRecord],
    global_records: list[SkillRecord],
    local_records: list[SkillRecord],
) -> int:
    out = {}
    for name in names:
        out[name] = {
            "local": _best_version_str(name, local_records),
            "global": _best_version_str(name, global_records),
            "latest": _best_version_str(name, repo_records, stable_only=True),
        }
    print(json.dumps(out, indent=2))
    return 0


def _best_version_str(
    name: str,
    records: list[SkillRecord],
    stable_only: bool = False,
) -> str:
    r = resolve_latest(name, records, stable_only=stable_only)
    if r and r.version:
        return r.version.raw
    return "—"


# ---------------------------------------------------------------------------
# Subcommand: sync
# ---------------------------------------------------------------------------

def cmd_sync(args: argparse.Namespace) -> int:
    """Sync skills from the agent's project config file (e.g. CLAUDE.md)."""
    project_dir = args.project_dir or Path.cwd()
    manifest_path = Path(project_dir) / get_config_file()

    requirements = parse_manifest(manifest_path)
    if not requirements:
        print(yellow(f"No skills requirements found in {manifest_path.name}"))
        print(dim(f"  Looked in: {manifest_path}"))
        print(dim("  Add a '## Skills Requirements' section with a YAML block."))
        return 0

    git_repos = _get_git_repos(project_dir)
    _fetch_if_requested(git_repos, getattr(args, "fetch", False), getattr(args, "no_fetch", False))

    repo_records = _get_repo_records(git_repos)
    global_dir = get_global_dir()
    global_records = scan_installed(global_dir) if global_dir.exists() else []

    ensure_local_dir(project_dir)
    local_dir = get_local_dir(project_dir)
    local_records = scan_installed(local_dir) if local_dir.exists() else []
    local_registry = Registry(get_local_registry(project_dir))

    resolved = resolve_all(requirements, repo_records, global_records, local_records)

    errors = 0
    installed_count = 0

    for req in requirements:
        record = resolved.get(req.name)
        if record is None:
            print(red(f"✗ {req.name}: not found (constraint: {req.constraint})"))
            if git_repos and not getattr(args, "fetch", False):
                print(dim("    Tip: run with --fetch to refresh the tag index from the remote."))
            errors += 1
            continue

        v = record.version.raw if record.version else "unknown"

        # Already installed locally at the right version?
        already = local_registry.get_version(record.full_name)
        if already == v and not args.force:
            print(dim(f"  {req.name}@{v} — already installed, skipping"))
            continue

        if args.dry_run:
            print(f"  {req.name}@{v} — would install (dry-run)")
            continue

        git_repo = _find_git_repo_for_record(record, git_repos)
        dest = install(record, local_dir, local_registry, overwrite=True, git_repo=git_repo)
        print(green(f"✓ {req.name}@{v} → {dest}"))
        installed_count += 1

    print()
    if args.dry_run:
        print(yellow(f"Dry-run complete. {len(requirements)} requirement(s) checked."))
    else:
        print(bold(f"Sync complete. {installed_count} installed, {errors} error(s)."))

    return 0 if errors == 0 else 1


# ---------------------------------------------------------------------------
# Subcommand: remove
# ---------------------------------------------------------------------------

def cmd_remove(args: argparse.Namespace) -> int:
    """Remove a skill from global or local scope."""
    name = args.name
    artifact_type = args.type or "skills"

    if args.global_:
        scope_label = "global"
        target_dir = get_global_dir()
        registry = Registry(get_global_registry())
    else:
        scope_label = "local"
        target_dir = get_local_dir(args.project_dir)
        registry = Registry(get_local_registry(args.project_dir))

    removed = uninstall(artifact_type, name, target_dir, registry)
    if removed:
        print(green(f"✓ Removed {name} [{scope_label}]"))
        return 0
    else:
        print(yellow(f"  {name} was not installed [{scope_label}]"))
        return 0


# ---------------------------------------------------------------------------
# Subcommand: update
# ---------------------------------------------------------------------------

def cmd_update(args: argparse.Namespace) -> int:
    """Update a skill to its latest available repository version."""
    install_args = argparse.Namespace(
        spec=f"{args.name}:latest",
        no_overwrite=False,
        global_=getattr(args, "global_", False),
        local_=getattr(args, "local_", False),
        project_dir=getattr(args, "project_dir", None),
        type=getattr(args, "type", None),
        fetch=getattr(args, "fetch", False),
        no_fetch=getattr(args, "no_fetch", False),
    )
    return cmd_install(install_args)


# ---------------------------------------------------------------------------
# Subcommand: view
# ---------------------------------------------------------------------------

def cmd_view(args: argparse.Namespace) -> int:
    """View details about an operation."""
    if args.view_command == "versions":
        return _view_versions(args)
    # Shouldn't happen due to argparse choices, but just in case
    print(red(f"Unknown view subcommand: {args.view_command}"))
    return 1


def _view_versions(args: argparse.Namespace) -> int:
    """List all available versions of a given operation."""
    name = args.name
    git_repos = _get_git_repos(getattr(args, "project_dir", None))
    _fetch_if_requested(git_repos, getattr(args, "fetch", False), getattr(args, "no_fetch", False))

    repo_records = _get_repo_records(git_repos)
    global_dir = get_global_dir()
    global_records = scan_installed(global_dir) if global_dir.exists() else []
    local_dir = get_local_dir(getattr(args, "project_dir", None))
    local_records = scan_installed(local_dir) if local_dir.exists() else []

    # Collect all records matching the name
    name_lower = name.lower()
    matching = [
        r for r in repo_records + global_records + local_records
        if r.name.lower() == name_lower or r.name.lower().endswith("/" + name_lower)
    ]

    if not matching:
        print(red(f"✗ No versions found for: {name}"))
        _suggest_similar(name, repo_records)
        if git_repos and not getattr(args, "fetch", False):
            print(dim("  Tip: run with --fetch to refresh the tag index from the remote."))
        return 1

    if args.json:
        return _view_versions_json(name, matching)

    return _view_versions_table(name, matching, local_records, global_records)


def _view_versions_table(
    name: str,
    matching: list[SkillRecord],
    local_records: list[SkillRecord],
    global_records: list[SkillRecord],
) -> int:
    # Deduplicate by version string, tracking source
    version_info: dict[str, dict] = {}
    for r in matching:
        v_str = r.version.raw if r.version else "unknown"
        if v_str not in version_info:
            version_info[v_str] = {
                "version": r.version,
                "type": r.artifact_type,
                "sources": set(),
            }
        if r in local_records:
            version_info[v_str]["sources"].add("local")
        elif r in global_records:
            version_info[v_str]["sources"].add("global")
        else:
            version_info[v_str]["sources"].add("repo")

    # Sort versions descending
    sorted_versions = sorted(
        version_info.items(),
        key=lambda item: item[1]["version"] if item[1]["version"] else "",
        reverse=True,
    )

    print()
    print(bold(f"Versions of {name}"))
    print("-" * 50)
    print(f"  {'VERSION':<20}  {'SOURCE':<15}  {'STATUS'}")
    print(f"  {'-------':<20}  {'------':<15}  {'------'}")

    for v_str, info in sorted_versions:
        sources = ", ".join(sorted(info["sources"]))
        is_snapshot = info["version"] and info["version"].is_snapshot
        status = yellow("snapshot") if is_snapshot else green("stable")
        installed = ""
        if "local" in info["sources"] or "global" in info["sources"]:
            installed = f"  {bold('[installed]')}"
        print(f"  {v_str:<20}  {sources:<15}  {status}{installed}")

    print()
    print(dim(f"  {len(sorted_versions)} version(s) found"))
    print()
    return 0


def _view_versions_json(name: str, matching: list[SkillRecord]) -> int:
    versions = []
    seen = set()
    for r in matching:
        v_str = r.version.raw if r.version else "unknown"
        if v_str in seen:
            continue
        seen.add(v_str)
        versions.append({
            "version": v_str,
            "type": r.artifact_type,
            "stable": r.version.is_stable if r.version else False,
            "structure": r.structure,
        })
    # Sort by version descending
    versions.sort(
        key=lambda v: parse_version(v["version"]) or "",
        reverse=True,
    )
    out = {"name": name, "versions": versions}
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: env
# ---------------------------------------------------------------------------

def cmd_env(args: argparse.Namespace) -> int:
    """Show or validate environment configuration."""
    import time as _time
    from datetime import datetime, timezone
    from .config import get_agent
    from .settings import get_settings_path

    agent = get_agent()
    all_urls = get_repo_urls()
    local_paths = get_local_paths()
    ttl = get_fetch_ttl()

    print()
    print(bold("AI Agent"))
    print("-" * 40)
    print(f"  {'Agent':<30} {green(agent)}")
    cfg = AGENT_MAP[agent]
    print(f"  {'dir_name':<30} {cfg['dir_name']}")
    print(f"  {'config_file':<30} {cfg['config_file']}")

    print()
    print(bold("Global Settings"))
    print("-" * 40)
    print(f"  {'settings file':<30} {get_settings_path()}")
    print(f"  {'fetch_ttl_seconds':<30} {ttl}")

    print()
    print(bold("Skills Repositories (remote)"))
    print("-" * 40)
    if all_urls:
        for i, url in enumerate(all_urls, 1):
            git_repo = GitRepo(url)
            status = green("✓ cloned") if git_repo.is_cloned else yellow("not yet cloned")
            print(f"  [{i}] {url}")
            print(f"      {'cache':<26} {git_repo.cache_dir}  [{status}]")
            if git_repo.is_cloned:
                tags = git_repo.list_skill_tags()
                print(f"      {'tagged versions':<26} {len(tags)}")
                last = git_repo._load_last_fetched()
                if last is not None:
                    dt = datetime.fromtimestamp(last, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    age = int(_time.time() - last)
                    stale = age > ttl
                    age_label = f"{age}s ago" if age < 120 else f"{age // 60}m ago"
                    freshness = red("stale") if stale else green("fresh")
                    print(f"      {'last fetched':<26} {dt}  ({age_label}, {freshness})")
                else:
                    print(f"      {'last fetched':<26} {yellow('unknown')}")
    else:
        print(f"  {yellow('(not configured — run aom init)')}")

    print()
    print(bold("Skills Repositories (local paths)"))
    print("-" * 40)
    if local_paths:
        for i, lp in enumerate(local_paths, 1):
            p = Path(lp)
            status = green("✓ exists") if p.is_dir() else red("✗ path missing")
            print(f"  [{i}] {lp}  [{status}]")
    else:
        print(f"  {dim('(none configured)')}")

    print()
    print(bold("Install locations"))
    print("-" * 40)
    print(f"  global : {get_global_dir()}")
    print(f"  local  : {get_local_dir()}")
    print()

    if args.check:
        if not all_urls and not local_paths:
            print(red("✗ No repository configured. Run 'aom init' to set up."))
            return 1
    return 0


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------

# Known agent config files — includes agents not yet in AGENT_MAP for detection
_KNOWN_AGENT_FILES = {
    "CLAUDE.md":        "ClaudeCode",
    ".cursorrules":     "Cursor",
    "opencode.json":    "OpenCode",
    "AGENTS.md":        "Codex",
    ".aider.conf.yml":  "Aider",
}


def cmd_init(args: argparse.Namespace) -> int:
    """Interactive project initialization: detect agent, save repository URL(s)."""
    from .settings import get_settings_path

    project_dir = (args.project_dir or Path.cwd()).resolve()

    print()
    print(bold("aom init"))
    print(f"  Directory: {project_dir}")
    print()

    # ---- Step 1: find config files in the project directory ----
    found = [
        (filename, agent_name, project_dir / filename)
        for filename, agent_name in _KNOWN_AGENT_FILES.items()
        if (project_dir / filename).is_file()
    ]

    if not found:
        print(yellow("No AI agent config files found in this directory."))
        print()
        print("Select an agent to initialize:")
        agents = list(_KNOWN_AGENT_FILES.items())
        for i, (filename, name) in enumerate(agents, 1):
            print(f"  [{i}] {name:<20}  ({filename})")
        print()
        while True:
            choice = input(f"Agent (1-{len(agents)}): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(agents):
                    filename, agent_name = agents[idx]
                    config_path = project_dir / filename
                    break
            print("  Invalid selection.", file=sys.stderr)
    elif len(found) == 1:
        filename, agent_name, config_path = found[0]
        print(f"Found: {bold(filename)}  →  {agent_name}")
        ans = input("Use this config file? [Y/n]: ").strip().lower()
        if ans == "n":
            print("Aborted.")
            return 0
    else:
        print("Found multiple AI agent config files:")
        for i, (filename, agent_name, _) in enumerate(found, 1):
            print(f"  [{i}] {filename:<25}  →  {agent_name}")
        print()
        while True:
            choice = input(f"Select config file (1-{len(found)}): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(found):
                    filename, agent_name, config_path = found[idx]
                    break
            print("  Invalid selection.", file=sys.stderr)

    print()
    print(f"  Agent:       {bold(agent_name)}")
    print(f"  Config file: {config_path}")
    print()

    # ---- Step 2: configure repository URLs (global settings) ----
    saved_urls = get_global_repo_urls()

    if saved_urls:
        # Repositories already configured globally — show them and offer to change
        print(bold("Configured repositories:"))
        for i, u in enumerate(saved_urls, 1):
            print(f"  [{i}] {u}")
        print()
        ans = input("  Change repositories? [y/N]: ").strip().lower()
        if ans == "y":
            urls = _prompt_repo_urls()
            set_global_repo_urls(urls)
            saved_urls = urls
            print(green(f"✓ Saved {len(urls)} repository URL(s) to {get_settings_path()}"))
            print()
        else:
            print(dim("  Using existing repository configuration."))
            print()
    else:
        # First time — prompt for repositories
        print("No repositories configured yet.")
        print()
        urls = _prompt_repo_urls()
        set_global_repo_urls(urls)
        saved_urls = urls
        print()
        print(green(f"✓ Saved {len(urls)} repository URL(s) to {get_settings_path()}"))
        print()

    # ---- Step 3: configure local filesystem paths (optional) ----
    saved_local_paths = get_global_local_paths()

    if saved_local_paths:
        print(bold("Configured local paths:"))
        for i, lp in enumerate(saved_local_paths, 1):
            p = Path(lp)
            status = green("✓ exists") if p.is_dir() else red("✗ missing")
            print(f"  [{i}] {lp}  [{status}]")
        print()
        ans = input("  Change local paths? [y/N]: ").strip().lower()
        if ans == "y":
            local_paths = _prompt_local_paths()
            set_global_local_paths(local_paths)
            saved_local_paths = local_paths
            print(green(f"✓ Saved {len(local_paths)} local path(s) to {get_settings_path()}"))
            print()
        else:
            print(dim("  Using existing local path configuration."))
            print()
    else:
        print("Optionally, you can add local filesystem paths to skill repositories.")
        print("This is useful for local development or when skills are stored on disk.")
        print()
        ans = input("  Add local paths? [y/N]: ").strip().lower()
        if ans == "y":
            local_paths = _prompt_local_paths()
            set_global_local_paths(local_paths)
            saved_local_paths = local_paths
            print()
            print(green(f"✓ Saved {len(local_paths)} local path(s) to {get_settings_path()}"))
            print()
        else:
            print(dim("  Skipped."))
            print()

    # ---- Step 4: write primary URL to project config (backward compat) ----
    if saved_urls:
        primary_url = saved_urls[0]
        existing_url = parse_repo_url(config_path)
        if existing_url != primary_url:
            write_repo_url(config_path, primary_url)
            print(green(f"✓ Primary repository URL saved to {config_path.name}"))
            print()

    # ---- Step 5: offer to fetch the tag index from all repos ----
    if saved_urls:
        ans = input("  Fetch skill index from repositories now? [Y/n]: ").strip().lower()
        if ans != "n":
            total_tags = 0
            for url in saved_urls:
                try:
                    repo = GitRepo(url)
                    repo.fetch(verbose=True)
                    tags = repo.list_skill_tags()
                    total_tags += len(tags)
                    print(green(f"  ✓ {url} — {len(tags)} skill version(s)"))
                except RuntimeError as exc:
                    print(red(f"  ✗ {url}: {exc}"))
                    print(yellow("    Check your SSH key and URL, then run 'aom list --fetch'."))
            print()
            print(green(f"✓ Fetched. {total_tags} total skill version(s) available."))

    # Count local skills if any local paths configured
    if saved_local_paths:
        local_skill_count = 0
        for lp in saved_local_paths:
            p = Path(lp)
            if p.is_dir():
                local_records = scan_repository(p)
                local_skill_count += len(local_records)
        if local_skill_count:
            print(green(f"  ✓ {local_skill_count} skill(s) found in local paths"))

    print()
    print(bold("Next steps:"))
    print("  aom list            — view available skills")
    print("  aom install NAME    — install a skill")
    print("  aom sync            — install all required skills from config")
    print()
    return 0


def _prompt_repo_urls() -> list[str]:
    """Interactively prompt the user for one or more repository URLs."""
    print("Enter the SSH (or HTTPS) URLs of your skill repositories.")
    print("  Separate multiple URLs with commas.")
    print("  Examples:")
    print("    git@gitlab.com:myorg/ai-grimoire.git")
    print("    git@github.com:myuser/skills.git, git@github.com:myuser/more-skills.git")
    print()
    while True:
        raw = input("  Repository URL(s): ").strip()
        if not raw:
            print("  At least one URL is required.", file=sys.stderr)
            continue

        urls = [u.strip() for u in raw.split(",") if u.strip()]
        if not urls:
            print("  At least one URL is required.", file=sys.stderr)
            continue

        # Validate each URL
        valid = True
        for url in urls:
            if not any(url.startswith(p) for p in ("git@", "ssh://", "https://", "http://")):
                print(yellow(f"  Warning: URL doesn't look like a standard git remote: {url}"))
                ans = input("  Continue anyway? [y/N]: ").strip().lower()
                if ans != "y":
                    valid = False
                    break
        if valid:
            return urls


def _prompt_local_paths() -> list[str]:
    """Interactively prompt the user for local filesystem paths to skill repositories."""
    print("Enter local filesystem paths to skill repositories.")
    print("  Separate multiple paths with commas.")
    print("  Example:")
    print("    /home/user/my-skills, /home/user/more-skills")
    print()
    while True:
        raw = input("  Local path(s): ").strip()
        if not raw:
            print("  At least one path is required.", file=sys.stderr)
            continue

        paths = [p.strip() for p in raw.split(",") if p.strip()]
        if not paths:
            print("  At least one path is required.", file=sys.stderr)
            continue

        # Validate each path
        valid = True
        resolved_paths: list[str] = []
        for p in paths:
            resolved = Path(p).expanduser().resolve()
            if not resolved.is_dir():
                print(yellow(f"  Warning: directory does not exist: {resolved}"))
                ans = input("  Add anyway? [y/N]: ").strip().lower()
                if ans != "y":
                    valid = False
                    break
            resolved_paths.append(str(resolved))
        if valid:
            return resolved_paths


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aom",
        description=(
            "AI Operation Manager — manage versioned AI operations across projects\n"
            "using git tags as a lightweight package registry.\n\n"
            "An \"operation\" is any versioned markdown artifact managed by aom.\n"
            "Operation types include: skills, commands, agents, and hooks."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    from . import __version__
    parser.add_argument(
        "-v", "--version", action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print the full Python traceback when an error occurs",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    def _add_scope_args(p: argparse.ArgumentParser) -> None:
        scope = p.add_mutually_exclusive_group()
        scope.add_argument(
            "--global", dest="global_", action="store_true",
            help="Target the global scope (~/.claude), shared across all projects",
        )
        scope.add_argument(
            "--local", dest="local_", action="store_true",
            help="Target the local project scope (<project>/.claude) [default]",
        )
        p.add_argument(
            "--project-dir", metavar="DIR", type=Path, default=None,
            help=(
                "Path to the project root directory used to locate the local scope "
                "and config file (default: current working directory)"
            ),
        )
        p.add_argument(
            "--type", choices=ARTIFACT_TYPES, metavar="TYPE",
            help=(
                "Filter by artifact type: %(choices)s "
                "(default: all types)"
            ),
        )

    def _add_fetch_args(p: argparse.ArgumentParser) -> None:
        fetch_group = p.add_mutually_exclusive_group()
        fetch_group.add_argument(
            "--fetch", action="store_true",
            help="Force a fresh fetch of tags from all remote repositories, ignoring the TTL cache",
        )
        fetch_group.add_argument(
            "--no-fetch", action="store_true",
            help="Skip automatic fetching entirely; use only the locally cached tag index (offline mode)",
        )

    # -- init -----------------------------------------------------------------
    p_init = sub.add_parser(
        "init",
        help="Set up a project: detect AI agent, configure operation repositories",
        description=(
            "Interactive project setup wizard.\n\n"
            "Detects the AI agent in use (e.g. ClaudeCode, Cursor), prompts for\n"
            "one or more operation repository URLs, and writes the configuration\n"
            "to the agent's config file and global settings."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_init.add_argument(
        "--project-dir", metavar="DIR", type=Path, default=None,
        help=(
            "Path to the project root directory to initialize "
            "(default: current working directory)"
        ),
    )

    # -- fetch ----------------------------------------------------------------
    p_fetch = sub.add_parser(
        "fetch",
        help="Refresh the operation index from all remote repositories",
        description=(
            "Fetch the latest git tags from every configured remote repository.\n\n"
            "This updates the local tag cache so that subsequent install, list,\n"
            "and sync commands see newly published operation versions. Repositories\n"
            "are configured via 'aom init' or the global settings file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_fetch.add_argument(
        "--project-dir", metavar="DIR", type=Path, default=None,
        help=(
            "Path to the project root directory whose config is used to discover "
            "repository URLs (default: current working directory)"
        ),
    )

    # -- install --------------------------------------------------------------
    p_install = sub.add_parser(
        "install",
        help="Install an operation into the local or global scope",
        description=(
            "Install an operation by name, with an optional version constraint.\n\n"
            "The operation is resolved from remote repositories and local paths,\n"
            "then written to the target scope directory. When no scope flag is\n"
            "given, the operation is installed into the local project scope.\n\n"
            "Version constraint formats:\n"
            "  NAME              Install the latest stable version\n"
            "  NAME:1.2.0        Install exactly version 1.2.0\n"
            "  NAME:>=1.0.0      Install the newest version >= 1.0.0\n"
            "  NAME:latest       Same as omitting the version (latest stable)\n"
            "  NAME:*            Include pre-release versions"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_install.add_argument(
        "spec", metavar="NAME[:VERSION]",
        help="Operation name with an optional version constraint (e.g. create-jira-story:>=1.0.0)",
    )
    p_install.add_argument(
        "--no-overwrite", action="store_true",
        help="Do not overwrite the operation if it is already installed at any version",
    )
    _add_fetch_args(p_install)
    _add_scope_args(p_install)

    # -- list -----------------------------------------------------------------
    p_list = sub.add_parser(
        "list",
        help="Show available and installed operations with version info",
        description=(
            "Display a table of all known operations with their installed (local\n"
            "and global) and latest available versions. Use --json for machine-\n"
            "readable output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_list.add_argument(
        "--json", action="store_true",
        help="Print the operation list as a JSON object instead of a human-readable table",
    )
    _add_fetch_args(p_list)
    p_list.add_argument(
        "--project-dir", metavar="DIR", type=Path, default=None,
        help=(
            "Path to the project root directory used to locate the local scope "
            "(default: current working directory)"
        ),
    )
    p_list.add_argument(
        "--type", choices=ARTIFACT_TYPES, metavar="TYPE",
        help="Show only artifacts of the given type: %(choices)s",
    )

    # -- sync -----------------------------------------------------------------
    p_sync = sub.add_parser(
        "sync",
        help="Install all required operations declared in the project config",
        description=(
            "Read the 'Skills Requirements' section from the agent's project\n"
            "config file (e.g. CLAUDE.md) and install every listed operation into\n"
            "the local scope. Operations that are already installed at the required\n"
            "version are skipped unless --force is given."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_sync.add_argument(
        "--project-dir", metavar="DIR", type=Path, default=None,
        help=(
            "Path to the project root directory containing the config file "
            "(default: current working directory)"
        ),
    )
    p_sync.add_argument(
        "--dry-run", action="store_true",
        help="Show which operations would be installed without writing any files",
    )
    p_sync.add_argument(
        "--force", action="store_true",
        help="Re-install every required operation even if already installed at the correct version",
    )
    _add_fetch_args(p_sync)

    # -- remove ---------------------------------------------------------------
    p_remove = sub.add_parser(
        "remove",
        help="Uninstall an operation from the local or global scope",
        description=(
            "Remove a previously installed operation and delete its file from the\n"
            "target scope directory. When no scope flag is given, the operation is\n"
            "removed from the local project scope."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_remove.add_argument(
        "name", metavar="NAME",
        help="Name of the operation to remove (e.g. create-jira-story)",
    )
    _add_scope_args(p_remove)

    # -- update ---------------------------------------------------------------
    p_update = sub.add_parser(
        "update",
        help="Upgrade an operation to the latest available version",
        description=(
            "Replace an installed operation with the latest version available in\n"
            "the configured repositories. Equivalent to running\n"
            "'aom install NAME:latest' with overwrite enabled."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_update.add_argument(
        "name", metavar="NAME",
        help="Name of the operation to update (e.g. create-jira-story)",
    )
    _add_fetch_args(p_update)
    _add_scope_args(p_update)

    # -- view -----------------------------------------------------------------
    p_view = sub.add_parser(
        "view",
        help="View details about an operation (e.g. available versions)",
        description=(
            "Inspect a specific operation.\n\n"
            "Subcommands:\n"
            "  versions   List all available versions of the operation"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_view.add_argument(
        "name", metavar="NAME",
        help="Name of the operation to inspect (e.g. implement-missing-components)",
    )
    p_view.add_argument(
        "view_command", metavar="SUBCOMMAND", choices=["versions"],
        help="What to view: versions",
    )
    p_view.add_argument(
        "--json", action="store_true",
        help="Print output as JSON instead of a human-readable table",
    )
    _add_fetch_args(p_view)
    p_view.add_argument(
        "--project-dir", metavar="DIR", type=Path, default=None,
        help=(
            "Path to the project root directory used to locate the local scope "
            "(default: current working directory)"
        ),
    )

    # -- env ------------------------------------------------------------------
    p_env = sub.add_parser(
        "env",
        help="Display environment configuration and diagnostics",
        description=(
            "Print a summary of the current aom environment: detected AI agent,\n"
            "configured repositories (remote and local), cache status, fetch\n"
            "freshness, and install locations. Useful for debugging configuration\n"
            "issues."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_env.add_argument(
        "--check", action="store_true",
        help="Exit with code 1 if no operation repository is configured (useful in CI scripts)",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    # Ensure UTF-8 output on Windows (only when running as CLI entry point)
    if sys.platform == "win32" and not hasattr(sys, "_called_from_test"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "init":    cmd_init,
        "fetch":   cmd_fetch,
        "install": cmd_install,
        "list":    cmd_list,
        "sync":    cmd_sync,
        "remove":  cmd_remove,
        "update":  cmd_update,
        "view":    cmd_view,
        "env":     cmd_env,
    }

    try:
        return dispatch[args.command](args)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130
    except (RuntimeError, FileNotFoundError, PermissionError, OSError) as exc:
        print(red(f"Error: {exc}"), file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guess_type(name: str, git_repos: list[GitRepo], repo_records: list) -> str:
    """
    Heuristically determine artifact type for *name*.

    For git-backed repos: look it up in the already-fetched records.
    For local repos: scan the filesystem.
    """
    name_lower = name.lower()
    for r in repo_records:
        if r.name.lower() == name_lower or r.name.lower().endswith("/" + name_lower):
            return r.artifact_type

    # Filesystem fallback — scan configured local paths
    for local_path in get_local_paths():
        try:
            repo_path = Path(local_path)
            for t in ARTIFACT_TYPES:
                type_dir = repo_path / t
                if (type_dir / name).exists() or list(type_dir.glob(f"{name}.md")):
                    return t
        except (OSError, RuntimeError):
            pass

    return "skills"


def _suggest_similar(name: str, records: list[SkillRecord]) -> None:
    """Print names that share a prefix with *name*."""
    name_lower = name.lower()
    similar = [r.name for r in records if name_lower[:3] in r.name.lower()]
    if similar:
        print(dim("  Similar skills found:"))
        for s in sorted(set(similar))[:5]:
            print(dim(f"    {s}"))


if __name__ == "__main__":
    sys.exit(main())
