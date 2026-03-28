"""
Configuration and environment management.

Resolves AI agent, path locations, and repository sources from global
user settings and project config files.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict


# ---------------------------------------------------------------------------
# AI Agent map
# ---------------------------------------------------------------------------
# Each entry maps an agent name to its deployment configuration:
#   dir_name    – folder created inside the project root and home directory
#   config_file – file the agent reads for project configuration / requirements
#   type_dirs   – maps grimoire artifact types to the agent's subdir names
#
# Add new agents here; aom.ps1 contains a matching display-only copy for
# interactive prompts — keep the two lists in sync when adding entries.
# ---------------------------------------------------------------------------

class AgentConfig(TypedDict):
    dir_name: str
    config_file: str
    type_dirs: dict[str, str]


AGENT_MAP: dict[str, AgentConfig] = {
    "ClaudeCode": {
        "dir_name":    ".claude",        # ~/.claude  /  <project>/.claude
        "config_file": "CLAUDE.md",      # project requirements live here
        "type_dirs": {                   # grimoire type  →  agent subdir
            "skills":   "commands",
            "commands": "commands",
            "agents":   "agents",
            "hooks":    "hooks",
        },
    },
    # Uncomment / fill in when paths are confirmed:
    # "OpenCode": {
    #     "dir_name":    ".opencode",
    #     "config_file": "opencode.json",
    #     "type_dirs": {
    #         "skills":   "skills",
    #         "commands": "commands",
    #         "agents":   "agents",
    #         "hooks":    "hooks",
    #     },
    # },
    # "Cursor": {
    #     "dir_name":    ".cursor",
    #     "config_file": ".cursorrules",
    #     "type_dirs": {
    #         "skills":   "rules",
    #         "commands": "rules",
    #         "agents":   "agents",
    #         "hooks":    "hooks",
    #     },
    # },
}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTIFACT_TYPES = ("skills", "commands", "agents", "hooks")

LOCAL_REGISTRY_NAME = "registry.json"


# ---------------------------------------------------------------------------
# AI Agent detection
# ---------------------------------------------------------------------------

_AGENT_CACHE: str | None = None


def _detect_agent_from_cwd() -> str | None:
    """Detect the active agent by looking for known config files in CWD."""
    cwd = Path.cwd()
    for agent, cfg in AGENT_MAP.items():
        if (cwd / cfg["config_file"]).exists():
            return agent
    return None


def get_agent() -> str:
    """
    Return the active AI agent name.

    Resolution order:
      1. In-process cache (already resolved this session).
      2. Config file detected in CWD (e.g. CLAUDE.md → ClaudeCode).
      3. Auto-select when only one agent is defined in AGENT_MAP.
      4. Interactive prompt listing all available agents.

    The selected agent is cached in-process.
    """
    global _AGENT_CACHE
    if _AGENT_CACHE is not None:
        return _AGENT_CACHE

    # Step 2: detect from project config file in CWD
    detected = _detect_agent_from_cwd()
    if detected:
        _AGENT_CACHE = detected
        return _AGENT_CACHE

    agents = list(AGENT_MAP.keys())

    if len(agents) == 1:
        _AGENT_CACHE = agents[0]
        return _AGENT_CACHE

    print()
    print("Available AI agents:")
    for i, name in enumerate(agents, 1):
        dir_name = AGENT_MAP[name]["dir_name"]
        print(f"  [{i}] {name:<20}  →  {dir_name}")
    print()

    while True:
        choice = input(
            f"Select agent (1-{len(agents)}) or enter name: "
        ).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(agents):
                _AGENT_CACHE = agents[idx]
                break
        elif choice in AGENT_MAP:
            _AGENT_CACHE = choice
            break
        print(f"  Invalid selection: {choice!r}. Try again.", file=sys.stderr)

    return _AGENT_CACHE


# ---------------------------------------------------------------------------
# Agent-aware path functions
# ---------------------------------------------------------------------------

def get_global_dir() -> Path:
    """Return the global install directory for the active AI agent (e.g. ~/.claude)."""
    return Path.home() / AGENT_MAP[get_agent()]["dir_name"]


def get_global_registry() -> Path:
    """Return the global registry file (inside the global agent dir)."""
    return get_global_dir() / LOCAL_REGISTRY_NAME


def get_config_file() -> str:
    """Return the project config filename for the active AI agent (e.g. CLAUDE.md)."""
    return AGENT_MAP[get_agent()]["config_file"]


def get_type_subdir(artifact_type: str) -> str:
    """
    Map a grimoire artifact type to the agent-specific subdirectory name.

    Example (ClaudeCode): "skills" → "commands", "agents" → "agents"
    """
    type_dirs = AGENT_MAP[get_agent()].get("type_dirs", {})
    return type_dirs.get(artifact_type, artifact_type)


def ensure_global_dir() -> None:
    """Create the global agent directory and its artifact subdirectories."""
    global_dir = get_global_dir()
    global_dir.mkdir(parents=True, exist_ok=True)
    # Create each unique mapped subdir (multiple types may share one subdir)
    created: set = set()
    for t in ARTIFACT_TYPES:
        subdir = get_type_subdir(t)
        if subdir not in created:
            (global_dir / subdir).mkdir(exist_ok=True)
            created.add(subdir)


def ensure_local_dir(project_dir: Path | None = None) -> None:
    """Create the local agent directory and its artifact subdirectories."""
    local = get_local_dir(project_dir)
    local.mkdir(parents=True, exist_ok=True)
    created: set = set()
    for t in ARTIFACT_TYPES:
        subdir = get_type_subdir(t)
        if subdir not in created:
            (local / subdir).mkdir(exist_ok=True)
            created.add(subdir)


# ---------------------------------------------------------------------------
# Local directory / registry helpers
# ---------------------------------------------------------------------------

def get_local_dir(project_dir: Path | None = None) -> Path:
    """Return the local agent directory for *project_dir* (cwd by default).

    The directory name is agent-specific (e.g. .claude for ClaudeCode).
    The base is always the directory where the command is run, not the
    ai-grimoire repository itself.
    """
    base = (project_dir or Path.cwd()).resolve()
    dir_name = AGENT_MAP[get_agent()]["dir_name"]
    return base / dir_name


def get_local_registry(project_dir: Path | None = None) -> Path:
    return get_local_dir(project_dir) / LOCAL_REGISTRY_NAME


# ---------------------------------------------------------------------------
# Repository URL resolution
# ---------------------------------------------------------------------------

def get_repo_url(project_dir: Path | None = None) -> str | None:
    """
    Read the skills repository URL from the project's agent config file
    (e.g. CLAUDE.md → ``## Skills Source`` → ``url``).

    Returns None if no URL is configured.
    """
    from .manifest import parse_repo_url
    project = (project_dir or Path.cwd()).resolve()
    try:
        config_file = get_config_file()
    except (KeyError, FileNotFoundError):
        return None
    return parse_repo_url(project / config_file)


def get_repo_urls(project_dir: Path | None = None) -> list[str]:
    """
    Return all configured repository URLs.

    Sources (in order, deduplicated):
      1. Global user settings (``~/.config/aom/settings.json``).
      2. Project config file (``CLAUDE.md`` → ``## Skills Source``).

    Returns an empty list when no repositories are configured anywhere.
    """
    from .settings import get_repo_urls as _global_urls

    urls: list[str] = []
    seen: set[str] = set()

    for u in _global_urls():
        if u not in seen:
            urls.append(u)
            seen.add(u)

    project_url = get_repo_url(project_dir)
    if project_url and project_url not in seen:
        urls.append(project_url)
        seen.add(project_url)

    return urls


def get_local_paths() -> list[str]:
    """
    Return all configured local filesystem paths for skill repositories.

    Reads from global user settings (``~/.config/aom/settings.json``).
    """
    from .settings import get_local_paths as _global_local_paths
    return _global_local_paths()
