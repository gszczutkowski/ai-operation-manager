"""
Registry — a JSON file that tracks installed skills at a given scope
(global ~/.ai-skills/registry.json or local .ai-skills/registry.json).

Schema:
{
  "version": 1,
  "installed": {
    "skills/complex-evaluator": "1.0.2",
    "commands/deploy-skills":   "1.0.0"
  },
  "updated_at": "2026-03-27T12:00:00"
}
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


_SCHEMA_VERSION = 1


class Registry:
    """Read/write wrapper around a JSON registry file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_version(self, full_name: str) -> str | None:
        """Return the installed version string for *full_name*, or None."""
        return self._data.get("installed", {}).get(full_name)

    def set_version(self, full_name: str, version: str) -> None:
        """Record *version* as installed for *full_name* and persist."""
        self._data.setdefault("installed", {})[full_name] = version
        self._touch()
        self._save()

    def remove(self, full_name: str) -> bool:
        """Remove an entry. Returns True if the entry existed."""
        installed = self._data.get("installed", {})
        if full_name in installed:
            del installed[full_name]
            self._touch()
            self._save()
            return True
        return False

    def all_installed(self) -> dict[str, str]:
        """Return a copy of the full installed mapping."""
        return dict(self._data.get("installed", {}))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                schema_ver = data.get("version")
                if schema_ver is not None and schema_ver != _SCHEMA_VERSION:
                    print(
                        f"Warning: registry at {self.path} has schema version "
                        f"{schema_ver} (expected {_SCHEMA_VERSION})",
                        file=sys.stderr,
                    )
                return data
            except (json.JSONDecodeError, OSError) as exc:
                print(
                    f"Warning: corrupt registry at {self.path}, starting fresh: {exc}",
                    file=sys.stderr,
                )
        return {"version": _SCHEMA_VERSION, "installed": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self._data, indent=2, ensure_ascii=False)
        # Atomic write: write to temp file then rename to prevent partial writes
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".registry-",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp_path, self.path)
        except BaseException:
            os.unlink(tmp_path)
            raise

    def _touch(self) -> None:
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()

    def reload(self) -> None:
        self._data = self._load()
