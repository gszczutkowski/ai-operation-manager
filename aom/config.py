"""
Configuration and environment management.

Resolves AI agent, path locations, and repository sources from global
user settings and project config files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict


# ---------------------------------------------------------------------------
# AI Agent map
# ---------------------------------------------------------------------------
# Each entry maps an agent name to its deployment configuration:
#   dir_name    - folder created inside the project root and home directory
#   config_file - file the agent reads for project configuration / requirements
#   type_dirs   - maps grimoire artifact types to the agent's subdir names
#
# Add new agents here; aom.ps1 contains a matching display-only copy for
# interactive prompts - keep the two lists in sync when adding entries.
# ---------------------------------------------------------------------------


class AgentConfig(TypedDict):
    dir_name: str
    config_file: str
    type_dirs: dict[str, str]


AGENT_MAP: dict[str, AgentConfig] = {
    "Codex": {
        "dir_name": ".agents",         # ~/.agents  /  <project>/.agents
        "config_file": "AGENTS.md",    # project requirements live here
        "type_dirs": {
            "skills": "skills",
            "commands": "commands",
            "agents": "agents",
            "hooks": "hooks",
        },
    },
    "ClaudeCode": {
        "dir_name": ".claude",         # ~/.claude  /  <project>/.claude
        "config_file": "CLAUDE.md",    # project requirements live here
        "type_dirs": {
            "skills": "skills",
            "commands": "commands",
            "agents": "agents",
            "hooks": "hooks",
        },
    },
    "Kiro": {
        "dir_name": ".kiro",           # ~/.kiro  /  <project>/.kiro
        "config_file": ".kiro",        # detection: directory presence in CWD
        "type_dirs": {
            "skills": "steering",
            "commands": "steering",
            "agents": "agents",
            "hooks": "hooks",
        },
    },
    # Uncomment / fill in when paths are confirmed:
    # "OpenCode": {
    #     "dir_name": ".opencode",
    #     "config_file": "opencode.json",
    #     "type_dirs": {
    #         "skills": "skills",
    #         "commands": "commands",
    #         "agents": "agents",
    #         "hooks": "hooks",
    #     },
    # },
    # "Cursor": {
    #     "dir_name": ".cursor",
    #     "config_file": ".cursorrules",
    #     "type_dirs": {
    #         "skills": "rules",
    #         "commands": "rules",
    #         "agents": "agents",
    #         "hooks": "hooks",
    #     },
    # },
}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTIFACT_TYPES = ("skills", "commands", "agents", "hooks")

LOCAL_REGISTRY_NAME = "registry.json"
PROJECT_AGENT_FILE = ".aom/agents.json"


# ---------------------------------------------------------------------------
# AI Agent detection
# ---------------------------------------------------------------------------

_AGENT_CACHE: str | None = None


def detect_supported_agents(project_dir: Path | None = None) -> list[str]:
    """Return all supported agents detected in *project_dir* (cwd by default)."""
    cwd = (project_dir or Path.cwd()).resolve()
    found: list[str] = []
    for agent, cfg in AGENT_MAP.items():
        if (cwd / cfg["config_file"]).exists():
            found.append(agent)
    return found


def _detect_agent_from_cwd() -> str | None:
    """Detect one active agent by looking for known config files in CWD."""
    detected = detect_supported_agents(Path.cwd())
    if detected:
        return detected[0]
    return None


def get_project_agent_file(project_dir: Path | None = None) -> Path:
    """Return path to the per-project selected-agents file."""
    base = (project_dir or Path.cwd()).resolve()
    return base / PROJECT_AGENT_FILE


def read_selected_agents(project_dir: Path | None = None) -> list[str] | None:
    """Read selected agents from ``.aom/agents.json``."""
    path = get_project_agent_file(project_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    raw = data.get("agents")
    if not isinstance(raw, list):
        return None
    selected = [a for a in raw if isinstance(a, str) and a in AGENT_MAP]
    if not selected:
        return None

    out: list[str] = []
    seen: set[str] = set()
    for name in selected:
        if name not in seen:
            out.append(name)
            seen.add(name)
    return out


def write_selected_agents(agents: list[str], project_dir: Path | None = None) -> None:
    """Persist selected agents into ``.aom/agents.json``."""
    out: list[str] = []
    seen: set[str] = set()
    for agent in agents:
        if agent in AGENT_MAP and agent not in seen:
            out.append(agent)
            seen.add(agent)
    if not out:
        raise ValueError("At least one valid agent is required.")
    path = get_project_agent_file(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"agents": out}, indent=2), encoding="utf-8")


def get_selected_agents(project_dir: Path | None = None) -> list[str]:
    """
    Return active agents for *project_dir*.

    Resolution order:
      1. ``.aom/agents.json`` selections.
      2. Supported agents detected in project directory.
    """
    selected = read_selected_agents(project_dir)
    if selected:
        return selected
    return detect_supported_agents(project_dir)


def get_agent(project_dir: Path | None = None) -> str:
    """
    Return one active AI agent name.

    If multiple agents are selected, returns the first selected agent.
    """
    global _AGENT_CACHE
    if _AGENT_CACHE is not None:
        return _AGENT_CACHE

    selected = get_selected_agents(project_dir)
    if selected:
        _AGENT_CACHE = selected[0]
        return _AGENT_CACHE

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
        print(f"  [{i}] {name:<20}  ->  {dir_name}")
    print()

    while True:
        choice = input(f"Select agent (1-{len(agents)}) or enter name: ").strip()
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


def _resolve_agent(agent: str | None = None, project_dir: Path | None = None) -> str:
    if agent:
        if agent not in AGENT_MAP:
            raise KeyError(f"Unknown agent: {agent}")
        return agent
    return get_agent(project_dir)


# ---------------------------------------------------------------------------
# Agent-aware path functions
# ---------------------------------------------------------------------------


def get_global_dir(agent: str | None = None, project_dir: Path | None = None) -> Path:
    """Return the global install directory for the active AI agent (e.g. ~/.claude)."""
    resolved = _resolve_agent(agent, project_dir)
    return Path.home() / AGENT_MAP[resolved]["dir_name"]


def get_global_registry(agent: str | None = None, project_dir: Path | None = None) -> Path:
    """Return the global registry file (inside the global agent dir)."""
    return get_global_dir(agent=agent, project_dir=project_dir) / LOCAL_REGISTRY_NAME


def get_config_file(agent: str | None = None, project_dir: Path | None = None) -> str:
    """Return the project config filename for the active AI agent (e.g. CLAUDE.md)."""
    resolved = _resolve_agent(agent, project_dir)
    return AGENT_MAP[resolved]["config_file"]


def get_type_subdir(
    artifact_type: str,
    agent: str | None = None,
    project_dir: Path | None = None,
) -> str:
    """
    Map a grimoire artifact type to the agent-specific subdirectory name.

    Example (ClaudeCode): "skills" -> "skills", "agents" -> "agents"
    """
    resolved = _resolve_agent(agent, project_dir)
    type_dirs = AGENT_MAP[resolved].get("type_dirs", {})
    return type_dirs.get(artifact_type, artifact_type)


def ensure_global_dir(agent: str | None = None, project_dir: Path | None = None) -> None:
    """Create the global agent directory and its artifact subdirectories."""
    global_dir = get_global_dir(agent=agent, project_dir=project_dir)
    global_dir.mkdir(parents=True, exist_ok=True)
    created: set[str] = set()
    for artifact_type in ARTIFACT_TYPES:
        subdir = get_type_subdir(artifact_type, agent=agent, project_dir=project_dir)
        if subdir not in created:
            (global_dir / subdir).mkdir(exist_ok=True)
            created.add(subdir)


def ensure_local_dir(project_dir: Path | None = None, agent: str | None = None) -> None:
    """Create the local agent directory and its artifact subdirectories."""
    local = get_local_dir(project_dir, agent=agent)
    local.mkdir(parents=True, exist_ok=True)
    created: set[str] = set()
    for artifact_type in ARTIFACT_TYPES:
        subdir = get_type_subdir(artifact_type, agent=agent, project_dir=project_dir)
        if subdir not in created:
            (local / subdir).mkdir(exist_ok=True)
            created.add(subdir)


# ---------------------------------------------------------------------------
# Local directory / registry helpers
# ---------------------------------------------------------------------------


def get_local_dir(project_dir: Path | None = None, agent: str | None = None) -> Path:
    """Return the local agent directory for *project_dir* (cwd by default)."""
    base = (project_dir or Path.cwd()).resolve()
    resolved = _resolve_agent(agent, project_dir)
    dir_name = AGENT_MAP[resolved]["dir_name"]
    return base / dir_name


def get_local_registry(project_dir: Path | None = None, agent: str | None = None) -> Path:
    return get_local_dir(project_dir, agent=agent) / LOCAL_REGISTRY_NAME


# ---------------------------------------------------------------------------
# Repository URL resolution
# ---------------------------------------------------------------------------


def get_repo_url(project_dir: Path | None = None, agent: str | None = None) -> str | None:
    """
    Read the skills repository URL from the project's agent config file
    (e.g. CLAUDE.md -> ``## Skills Source`` -> ``url``).

    Returns None if no URL is configured.
    """
    from .manifest import parse_repo_url

    project = (project_dir or Path.cwd()).resolve()
    try:
        config_file = get_config_file(agent=agent, project_dir=project)
    except (KeyError, FileNotFoundError):
        return None
    return parse_repo_url(project / config_file)


def get_repo_urls(project_dir: Path | None = None, agent: str | None = None) -> list[str]:
    """
    Return all configured repository URLs.

    Sources (in order, deduplicated):
      1. Global user settings (``~/.config/aom/settings.json``).
      2. Project config file (``CLAUDE.md`` -> ``## Skills Source``).

    Returns an empty list when no repositories are configured anywhere.
    """
    from .settings import get_repo_urls as _global_urls

    urls: list[str] = []
    seen: set[str] = set()

    for url in _global_urls():
        if url not in seen:
            urls.append(url)
            seen.add(url)

    project_url = get_repo_url(project_dir, agent=agent)
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
