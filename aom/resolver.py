"""
Version resolver.

Resolution priority (highest to lowest):
  1. Local project (.ai-skills/)
  2. Global install (~/.ai-skills/)
  3. Repository (available versions)

Constraint syntax supported:
  "1.2.3"     — exact version
  ">=1.2.0"   — minimum version (latest satisfying)
  "latest"    — newest stable version available
  "*"         — same as latest
"""
from __future__ import annotations


from .models import SkillRecord, Version, VersionRequirement  # noqa: F401


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------

def resolve(
    requirement: VersionRequirement,
    repo_records: list[SkillRecord],
    global_records: list[SkillRecord],
    local_records: list[SkillRecord],
) -> SkillRecord | None:
    """
    Return the best SkillRecord satisfying *requirement*, or None.

    Resolution order:
      1. If a matching version already exists locally → use it (no install needed)
      2. If a matching version exists globally → prefer global
      3. Resolve from repo records
    """
    # Filter to matching name across all collections
    name = requirement.name

    # Check local first (already installed, fastest path)
    local_match = _best_match(requirement, _by_name(local_records, name))
    if local_match:
        return local_match

    # Check global
    global_match = _best_match(requirement, _by_name(global_records, name))
    if global_match:
        return global_match

    # Fall back to repo
    return _best_match(requirement, _by_name(repo_records, name))


def resolve_latest(
    name: str,
    records: list[SkillRecord],
    stable_only: bool = True,
) -> SkillRecord | None:
    """Return the record with the highest version from *records* for *name*."""
    candidates = _by_name(records, name)
    if stable_only:
        candidates = [r for r in candidates if r.version and r.version.is_stable]
    return _highest(candidates)


def latest_available(records: list[SkillRecord], name: str) -> Version | None:
    """Return the latest stable version for *name* in *records*."""
    r = resolve_latest(name, records, stable_only=True)
    return r.version if r else None


# ---------------------------------------------------------------------------
# Batch resolution for skill-sync
# ---------------------------------------------------------------------------

def resolve_all(
    requirements: list[VersionRequirement],
    repo_records: list[SkillRecord],
    global_records: list[SkillRecord],
    local_records: list[SkillRecord],
) -> dict[str, SkillRecord | None]:
    """
    Resolve every requirement.  Returns a mapping of skill-name → best record
    (or None if not found).
    """
    return {
        req.name: resolve(req, repo_records, global_records, local_records)
        for req in requirements
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _by_name(records: list[SkillRecord], name: str) -> list[SkillRecord]:
    """Filter records to those matching *name* (case-insensitive, ignoring type)."""
    name_lower = name.lower()
    return [
        r for r in records
        if r.name.lower() == name_lower or r.name.lower().endswith("/" + name_lower)
    ]


def _best_match(
    requirement: VersionRequirement,
    candidates: list[SkillRecord],
) -> SkillRecord | None:
    """Return the highest-version record that satisfies *requirement*."""
    matching = [
        r for r in candidates
        if r.version and requirement.matches(r.version)
    ]
    return _highest(matching)


def _highest(records: list[SkillRecord]) -> SkillRecord | None:
    """Return the record with the highest version, or None."""
    versioned = [r for r in records if r.version is not None]
    if not versioned:
        return None
    return max(versioned, key=lambda r: r.version)
