"""
Data models for the skill version management system.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$")


@dataclass
class Version:
    """Normalized semantic version with optional prerelease label."""

    raw: str
    major: int
    minor: int
    patch: int
    prerelease: str | None = None  # e.g. "SNAPSHOT", "alpha.1"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_snapshot(self) -> bool:
        return self.prerelease is not None and "SNAPSHOT" in self.prerelease.upper()

    @property
    def is_stable(self) -> bool:
        return self.prerelease is None

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    # ------------------------------------------------------------------
    # Comparison (stable > prerelease of same numbers)
    # ------------------------------------------------------------------

    def _sort_key(self) -> tuple:
        """Return a consistent comparison key: (major, minor, patch, stability, prerelease)."""
        # stable (prerelease=None) sorts after any prerelease of the same version
        if self.prerelease is None:
            return (self.major, self.minor, self.patch, 1, "")
        return (self.major, self.minor, self.patch, 0, self.prerelease)

    def __lt__(self, other: Version) -> bool:
        return self._sort_key() < other._sort_key()

    def __le__(self, other: Version) -> bool:
        return self._sort_key() <= other._sort_key()

    def __gt__(self, other: Version) -> bool:
        return self._sort_key() > other._sort_key()

    def __ge__(self, other: Version) -> bool:
        return self._sort_key() >= other._sort_key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._sort_key() == other._sort_key()

    def __hash__(self) -> int:
        return hash(self._sort_key())

    def __str__(self) -> str:
        return self.raw

    def __repr__(self) -> str:
        return f"Version({self.raw!r})"


def parse_version(raw: str) -> Version | None:
    """Parse a semantic version string. Returns None if unparseable."""
    if not raw:
        return None
    raw = raw.strip()
    m = _SEMVER_RE.match(raw)
    if not m:
        return None
    major, minor, patch, prerelease = m.groups()
    return Version(
        raw=raw,
        major=int(major),
        minor=int(minor),
        patch=int(patch),
        prerelease=prerelease,
    )


# ---------------------------------------------------------------------------
# SkillRecord
# ---------------------------------------------------------------------------

@dataclass
class SkillRecord:
    """A single discovered artifact with all its metadata."""

    name: str                  # normalized: "complex-evaluator" or "child/page-painter"
    artifact_type: str         # "skills" | "commands" | "agents" | "hooks"
    path: Path | None           # absolute local path; None for git-only records
    version: Version | None
    structure: str             # "suffix" | "directory" | "metadata" | "flat" | "git"
    git_tag: str | None = None  # e.g. "skills/create-jira-story@1.0.0"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def full_name(self) -> str:
        """artifact_type/name — unique key across all types."""
        return f"{self.artifact_type}/{self.name}"

    @property
    def display_name(self) -> str:
        v = self.version.raw if self.version else "unknown"
        return f"{self.name}@{v}"

    def __repr__(self) -> str:
        return (
            f"SkillRecord(name={self.name!r}, type={self.artifact_type!r}, "
            f"version={self.version}, structure={self.structure!r})"
        )


# ---------------------------------------------------------------------------
# VersionRequirement
# ---------------------------------------------------------------------------

@dataclass
class VersionRequirement:
    """A version requirement as specified in CLAUDE.md skills block."""

    name: str
    constraint: str   # "1.0.0" | ">=1.2.0" | "latest" | "*"

    def is_latest(self) -> bool:
        return self.constraint.strip() in ("latest", "*", "")

    def is_exact(self) -> bool:
        return bool(re.match(r"^\d+\.\d+\.\d+", self.constraint.strip()))

    def is_minimum(self) -> bool:
        return self.constraint.strip().startswith(">=")

    def get_minimum_version(self) -> Version | None:
        if self.is_minimum():
            return parse_version(self.constraint.strip()[2:].strip())
        if self.is_exact():
            return parse_version(self.constraint.strip())
        return None

    def get_exact_version(self) -> Version | None:
        if self.is_exact():
            return parse_version(self.constraint.strip())
        return None

    def matches(self, version: Version) -> bool:
        """Return True if *version* satisfies this requirement."""
        if self.is_latest():
            return True
        if self.is_exact():
            exact = self.get_exact_version()
            return exact is not None and version == exact
        if self.is_minimum():
            minimum = self.get_minimum_version()
            return minimum is not None and version >= minimum
        warnings.warn(
            f"Unsupported version constraint: {self.constraint!r} for {self.name}",
            stacklevel=2,
        )
        return False

    def __repr__(self) -> str:
        return f"VersionRequirement({self.name!r}, {self.constraint!r})"
