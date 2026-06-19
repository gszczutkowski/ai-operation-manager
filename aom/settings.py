"""
Global user settings for aom.

Stores configuration that is shared across all projects, such as the list
of skill repository URLs and optional local filesystem paths.  The settings
file lives outside any project directory so that ``aom init`` in a new
project can reuse previously configured repositories without re-prompting.

Settings location:
  Linux/macOS: ~/.config/aom/settings.json
  Windows:     %APPDATA%/aom/settings.json

Schema (version 3):
{
  "version": 3,
  "agents": ["ClaudeCode", "Codex"],
  "repositories": [
    {"url": "git@github.com:myorg/ai-grimoire.git"}
  ],
  "local_paths": [
    "/home/user/my-local-skills"
  ],
  "required": {
    "create-jira-story": "1.0.0",
    "design-workflow": ">=1.0.0"
  },
  "initialized_paths": [
    "/home/user/my-project",
    "/home/user/other-project"
  ],
  "fetch_ttl_seconds": 3600
}

IMPORTANT: This file format is versioned. Any changes MUST be backward
compatible — new fields should have sensible defaults so that older configs
are transparently upgraded on read. Never remove or rename existing fields.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


_SCHEMA_VERSION = 3


# ---------------------------------------------------------------------------
# Settings file location
# ---------------------------------------------------------------------------

def get_settings_dir() -> Path:
    """Return the directory that holds the global aom settings file."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        if base:
            return Path(base) / "aom"
        return Path.home() / "AppData" / "Roaming" / "aom"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    return (Path(xdg) if xdg else Path.home() / ".config") / "aom"


def get_settings_path() -> Path:
    """Return the full path to the global settings file."""
    return get_settings_dir() / "settings.json"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def _load_raw() -> dict:
    path = get_settings_path()
    defaults = {
        "version": _SCHEMA_VERSION,
        "agents": [],
        "repositories": [],
        "local_paths": [],
        "required": {},
        "initialized_paths": [],
    }
    try:
        if not path.is_file():
            return dict(defaults)
    except OSError as exc:
        print(
            f"Warning: cannot access settings at {path}, using defaults: {exc}",
            file=sys.stderr,
        )
        return dict(defaults)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Migrate: ensure all expected keys exist (backward compat)
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val
        data["version"] = _SCHEMA_VERSION
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"Warning: corrupt settings at {path}, starting fresh: {exc}",
            file=sys.stderr,
        )
        return dict(defaults)


def _save_raw(data: dict) -> None:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["version"] = _SCHEMA_VERSION
    content = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp", prefix=".settings-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# Repository URL management
# ---------------------------------------------------------------------------

def get_repo_urls() -> list[str]:
    """Return all configured repository URLs from global settings."""
    data = _load_raw()
    repos = data.get("repositories", [])
    return [r["url"] for r in repos if isinstance(r, dict) and r.get("url")]


def set_repo_urls(urls: list[str]) -> None:
    """Replace the repository list in global settings with *urls*."""
    data = _load_raw()
    data["repositories"] = [{"url": u} for u in urls]
    _save_raw(data)


def add_repo_url(url: str) -> bool:
    """Add *url* to the repository list if not already present. Returns True if added."""
    urls = get_repo_urls()
    if url in urls:
        return False
    urls.append(url)
    set_repo_urls(urls)
    return True


def remove_repo_url(url: str) -> bool:
    """Remove *url* from the repository list. Returns True if removed."""
    urls = get_repo_urls()
    if url not in urls:
        return False
    urls.remove(url)
    set_repo_urls(urls)
    return True


# ---------------------------------------------------------------------------
# Local path management
# ---------------------------------------------------------------------------

def get_local_paths() -> list[str]:
    """Return all configured local filesystem paths from global settings."""
    data = _load_raw()
    paths = data.get("local_paths", [])
    return [p for p in paths if isinstance(p, str) and p]


def set_local_paths(paths: list[str]) -> None:
    """Replace the local paths list in global settings with *paths*."""
    data = _load_raw()
    data["local_paths"] = paths
    _save_raw(data)


def add_local_path(path: str) -> bool:
    """Add *path* to the local paths list if not already present. Returns True if added."""
    paths = get_local_paths()
    normalized = str(Path(path).resolve())
    for existing in paths:
        if str(Path(existing).resolve()) == normalized:
            return False
    paths.append(normalized)
    set_local_paths(paths)
    return True


def remove_local_path(path: str) -> bool:
    """Remove *path* from the local paths list. Returns True if removed."""
    paths = get_local_paths()
    normalized = str(Path(path).resolve())
    new_paths = [p for p in paths if str(Path(p).resolve()) != normalized]
    if len(new_paths) == len(paths):
        return False
    set_local_paths(new_paths)
    return True


# ---------------------------------------------------------------------------
# Fetch TTL management
# ---------------------------------------------------------------------------

_DEFAULT_FETCH_TTL = 3600  # 1 hour


def get_fetch_ttl() -> int:
    """Return the configured fetch TTL in seconds (default: 3600)."""
    data = _load_raw()
    return int(data.get("fetch_ttl_seconds", _DEFAULT_FETCH_TTL))


def set_fetch_ttl(seconds: int) -> None:
    """Set the fetch TTL in seconds."""
    data = _load_raw()
    data["fetch_ttl_seconds"] = seconds
    _save_raw(data)


# ---------------------------------------------------------------------------
# Global agents management
# ---------------------------------------------------------------------------

def get_global_agents() -> list[str]:
    """Return the list of globally supported agent names."""
    data = _load_raw()
    agents = data.get("agents", [])
    return [a for a in agents if isinstance(a, str) and a]


def set_global_agents(agents: list[str]) -> None:
    """Replace the global agents list."""
    data = _load_raw()
    data["agents"] = agents
    _save_raw(data)


# ---------------------------------------------------------------------------
# Global required skills management
# ---------------------------------------------------------------------------

def get_global_required() -> dict[str, str]:
    """Return the global required skills mapping {name: constraint}."""
    data = _load_raw()
    req = data.get("required", {})
    return {k: v for k, v in req.items() if isinstance(k, str) and isinstance(v, str)}


def set_global_required(required: dict[str, str]) -> None:
    """Replace the global required skills mapping."""
    data = _load_raw()
    data["required"] = required
    _save_raw(data)


def add_global_required_skill(name: str, constraint: str) -> None:
    """Add or update a skill in the global required mapping."""
    data = _load_raw()
    data.setdefault("required", {})[name] = constraint
    _save_raw(data)


def remove_global_required_skill(name: str) -> bool:
    """Remove a skill from the global required mapping. Returns True if removed."""
    data = _load_raw()
    req = data.get("required", {})
    if name in req:
        del req[name]
        _save_raw(data)
        return True
    return False


# ---------------------------------------------------------------------------
# Initialized paths management
# ---------------------------------------------------------------------------

def get_initialized_paths() -> list[str]:
    """Return all paths where 'aom init' has been run locally."""
    data = _load_raw()
    paths = data.get("initialized_paths", [])
    return [p for p in paths if isinstance(p, str) and p]


def add_initialized_path(path: str) -> bool:
    """Record that aom init was run at *path*. Returns True if newly added."""
    paths = get_initialized_paths()
    normalized = str(Path(path).resolve())
    for existing in paths:
        if str(Path(existing).resolve()) == normalized:
            return False
    paths.append(normalized)
    data = _load_raw()
    data["initialized_paths"] = paths
    _save_raw(data)
    return True


def remove_initialized_path(path: str) -> bool:
    """Remove *path* from the initialized paths list. Returns True if removed."""
    paths = get_initialized_paths()
    normalized = str(Path(path).resolve())
    new_paths = [p for p in paths if str(Path(p).resolve()) != normalized]
    if len(new_paths) == len(paths):
        return False
    data = _load_raw()
    data["initialized_paths"] = new_paths
    _save_raw(data)
    return True


# ---------------------------------------------------------------------------
# Global config check
# ---------------------------------------------------------------------------

def is_global_initialized() -> bool:
    """Return True if the global settings file exists and has agents configured."""
    data = _load_raw()
    return bool(data.get("agents"))
