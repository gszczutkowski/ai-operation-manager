"""
Configuration and environment management.

Resolves AI_SKILLS_REPO_PATH / AI_SKILLS_SCRIPTS_PATH, prompts when absent,
and persists the values to the user's shell profile (Linux/macOS) or Windows
environment (via setx).
"""
from __future__ import annotations

import os
import platform
import re
import shlex
import subprocess
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
# Environment variable helpers
# ---------------------------------------------------------------------------

def _read_env(var: str) -> str | None:
    return os.environ.get(var) or None


def _persist_env_unix(var: str, value: str) -> None:
    """Append export to ~/.bashrc and ~/.zshrc (best-effort)."""
    line = f'\nexport {var}={shlex.quote(value)}\n'
    for rc in (Path.home() / ".bashrc", Path.home() / ".zshrc"):
        try:
            existing = rc.read_text(encoding="utf-8") if rc.exists() else ""
            if not re.search(rf'^export {re.escape(var)}=', existing, re.MULTILINE):
                with rc.open("a", encoding="utf-8") as f:
                    f.write(line)
                print(f"  → Persisted to {rc}")
        except OSError as exc:
            print(f"  ⚠  Could not write to {rc}: {exc}", file=sys.stderr)


def _persist_env_windows(var: str, value: str) -> None:
    """Persist to Windows user environment via setx."""
    try:
        subprocess.run(
            ["setx", var, value],
            check=True,
            capture_output=True,
        )
        print(f"  → Persisted to Windows user environment ({var})")
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"  ⚠  Could not run setx: {exc}", file=sys.stderr)
        print(
            f"  ⚠  Set {var}={value!r} in System Properties → Environment Variables manually.",
            file=sys.stderr,
        )


def _persist_env(var: str, value: str) -> None:
    if platform.system() == "Windows":
        _persist_env_windows(var, value)
    else:
        _persist_env_unix(var, value)


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
      3. AI_AGENT_DEFAULT environment variable.
      4. Auto-select when only one agent is defined in AGENT_MAP.
      5. Interactive prompt listing all available agents.

    The selected agent is cached in-process and persisted to the environment.
    """
    global _AGENT_CACHE
    if _AGENT_CACHE is not None:
        return _AGENT_CACHE

    # Step 2: detect from project config file in CWD
    detected = _detect_agent_from_cwd()
    if detected:
        _AGENT_CACHE = detected
        return _AGENT_CACHE

    raw = os.environ.get("AI_AGENT_DEFAULT", "").strip()
    if raw:
        if raw in AGENT_MAP:
            _AGENT_CACHE = raw
            return _AGENT_CACHE
        print(
            f"  ⚠  AI_AGENT_DEFAULT={raw!r} is not a known agent. "
            f"Available: {', '.join(AGENT_MAP)}",
            file=sys.stderr,
        )

    agents = list(AGENT_MAP.keys())

    if len(agents) == 1:
        _AGENT_CACHE = agents[0]
        print(f"  Using AI agent: {_AGENT_CACHE}  "
              f"(set AI_AGENT_DEFAULT to skip this message)")
        os.environ["AI_AGENT_DEFAULT"] = _AGENT_CACHE
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

    os.environ["AI_AGENT_DEFAULT"] = _AGENT_CACHE
    _persist_env("AI_AGENT_DEFAULT", _AGENT_CACHE)
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
# Path resolution for repo / scripts
# ---------------------------------------------------------------------------

def _prompt_path(var: str, description: str) -> Path:
    """Ask the user for a directory path, validate it, then persist the env var."""
    while True:
        raw = input(f"\n{description}\n  {var} is not set. Enter the path: ").strip()
        if not raw:
            print("  Path cannot be empty.", file=sys.stderr)
            continue
        p = Path(raw).expanduser().resolve()
        if not p.is_dir():
            print(f"  Directory does not exist: {p}", file=sys.stderr)
            continue
        os.environ[var] = str(p)
        _persist_env(var, str(p))
        return p


def get_repo_path() -> Path:
    """Return the absolute path to the skills repository."""
    raw = _read_env("AI_SKILLS_REPO_PATH")
    if raw:
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            return p
        print(
            f"  ⚠  AI_SKILLS_REPO_PATH={raw!r} does not exist or is not a directory.",
            file=sys.stderr,
        )

    # Fall back: scripts_path parent (ai-grimoire/scripts/../ == ai-grimoire/)
    scripts_raw = _read_env("AI_SKILLS_SCRIPTS_PATH")
    if scripts_raw:
        candidate = Path(scripts_raw).expanduser().resolve().parent
        if (candidate / "skills").is_dir():
            os.environ["AI_SKILLS_REPO_PATH"] = str(candidate)
            return candidate

    # Fall back: resolve relative to this file's location (…/aom/config.py → repo root)
    candidate = Path(__file__).resolve().parent.parent.parent
    if (candidate / "skills").is_dir():
        os.environ["AI_SKILLS_REPO_PATH"] = str(candidate)
        return candidate

    return _prompt_path(
        "AI_SKILLS_REPO_PATH",
        "The AI skills repository path (the root of ai-grimoire).",
    )


def get_scripts_path() -> Path:
    """Return the absolute path to the scripts directory."""
    raw = _read_env("AI_SKILLS_SCRIPTS_PATH")
    if raw:
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            return p

    # Fall back: resolve relative to this file's location
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "aom").is_dir():
        os.environ["AI_SKILLS_SCRIPTS_PATH"] = str(candidate)
        return candidate

    return _prompt_path(
        "AI_SKILLS_SCRIPTS_PATH",
        "The AI scripts directory path (ai-grimoire/scripts).",
    )


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


def get_repo_url(project_dir: Path | None = None) -> str | None:
    """
    Read the skills repository URL from the project's agent config file
    (e.g. CLAUDE.md → ``## Skills Source`` → ``url``).

    Returns None if no URL is configured (caller should fall back to
    ``get_repo_path()`` for local development).
    """
    from .manifest import parse_repo_url
    project = (project_dir or Path.cwd()).resolve()
    try:
        config_file = get_config_file()
    except (KeyError, FileNotFoundError):
        return None
    return parse_repo_url(project / config_file)
