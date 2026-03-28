"""
Global user settings for aom.

Stores configuration that is shared across all projects, such as the list
of skill repository URLs.  The settings file lives outside any project
directory so that ``aom init`` in a new project can reuse previously
configured repositories without re-prompting.

Settings location:
  Linux/macOS: ~/.config/aom/settings.json
  Windows:     %APPDATA%/aom/settings.json

Schema (version 1):
{
  "version": 1,
  "repositories": [
    {"url": "git@github.com:myorg/ai-grimoire.git"}
  ]
}
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


_SCHEMA_VERSION = 1


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
    if not path.is_file():
        return {"version": _SCHEMA_VERSION, "repositories": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version", _SCHEMA_VERSION) != _SCHEMA_VERSION:
            print(
                f"Warning: settings at {path} has schema version "
                f"{data.get('version')} (expected {_SCHEMA_VERSION})",
                file=sys.stderr,
            )
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"Warning: corrupt settings at {path}, starting fresh: {exc}",
            file=sys.stderr,
        )
        return {"version": _SCHEMA_VERSION, "repositories": []}


def _save_raw(data: dict) -> None:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
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
