"""
Abstract base class for structure adapters.

Each adapter is responsible for:
  - detecting whether a given path matches its layout
  - extracting one or more SkillRecord instances from it
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from ..models import SkillRecord, Version

# Shared semver pattern used by multiple adapters
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-.+)?$")


class StructureAdapter(ABC):
    """Detect a versioning layout and extract SkillRecords from it."""

    name: str = "abstract"  # Subclasses must override; value here is for documentation only

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Return True if *path* (file or directory) matches this layout."""

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    @abstractmethod
    def extract_records(
        self,
        artifact_dir: Path,
        artifact_type: str,
    ) -> list[SkillRecord]:
        """
        Scan *artifact_dir* (e.g. repo/skills/) and return all SkillRecords
        this adapter can find.  The adapter must NOT return records that
        belong to a higher-priority adapter.  Callers should iterate adapters
        in priority order and skip already-claimed paths.
        """

    # ------------------------------------------------------------------
    # Helpers shared by subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _read_frontmatter(path: Path) -> str | None:
        """
        Return the raw YAML frontmatter block from *path* (the text between
        the first pair of --- delimiters), or None if not present.
        """
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return None

        end = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end = i
                break

        if end is None:
            return None

        return "\n".join(lines[1:end])

    @staticmethod
    def _extract_version_from_frontmatter(frontmatter: str) -> str | None:
        """
        Pull a version string from raw YAML frontmatter without a full YAML
        parser dependency.  Handles both:
          version: 1.0.0
          metadata:
            version: 1.0.0
        """
        # Try nested metadata.version first (skills), then top-level version.
        # The nested pattern allows blank lines and comment-only lines within
        # the metadata block.
        for pattern in (
            r"metadata:\s*\n(?:[ \t]*(?:#[^\n]*)?\n|[ \t]+\S[^\n]*\n)*?[ \t]+version:\s*([^\s#]+)",
            r"^version:\s*([^\s#]+)",
        ):
            m = re.search(pattern, frontmatter, re.MULTILINE)
            if m:
                return m.group(1).strip().strip("\"'")
        return None

    @staticmethod
    def _normalize_name(raw_name: str, artifact_dir: Path) -> str:
        """
        Convert a raw path component into a normalized skill name.
        Names may contain slashes for nested paths (e.g. "child/page-painter").
        """
        return raw_name.replace("\\", "/").strip("/")
