"""
Repository discovery — scan all artifact directories and return a unified
list of SkillRecords using the registered adapter chain.

Adapters are tried in priority order:
  1. SuffixAdapter   (Option A)
  2. DirAdapter      (Option B)
  3. MetadataAdapter (Option C — catches everything else)

Because adapters operate at the artifact-directory level (not per-path),
de-duplication is done by (artifact_type, name, structure) after collection.
If the same logical skill name is found by multiple adapters (mixed repo),
all versions are preserved so the resolver can pick the right one.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .adapters import ADAPTERS
from .config import ARTIFACT_TYPES
from .models import SkillRecord, parse_version

if TYPE_CHECKING:
    from .git import GitRepo


def scan_repository(repo_path: Path) -> list[SkillRecord]:
    """
    Recursively scan *repo_path* for all artifacts across all artifact types
    and all supported versioning structures.

    Returns a flat list of SkillRecords, deduplicated by
    (artifact_type, name, structure) — keeping the first occurrence
    when there are duplicates within the same adapter.
    """
    all_records: list[SkillRecord] = []

    for artifact_type in ARTIFACT_TYPES:
        artifact_dir = repo_path / artifact_type
        if not artifact_dir.is_dir():
            continue

        for adapter in ADAPTERS:
            records = adapter.extract_records(artifact_dir, artifact_type)
            all_records.extend(records)

    return _deduplicate(all_records)


def scan_git_repository(git_repo: GitRepo) -> list[SkillRecord]:
    """
    Discover all versioned skills from a git-backed remote repository.

    Reads skill tags from the local clone (no network call).  Each returned
    SkillRecord has ``git_tag`` set and ``path=None`` — the file content is
    fetched from git on demand when the record is installed.
    """
    tags = git_repo.list_skill_tags()
    records: list[SkillRecord] = []
    for artifact_type, name, version_str in tags:
        version = parse_version(version_str)
        tag = f"{artifact_type}/{name}@{version_str}"
        records.append(SkillRecord(
            name=name,
            artifact_type=artifact_type,
            path=None,
            version=version,
            structure="git",
            git_tag=tag,
        ))
    return records


def scan_installed(install_dir: Path) -> list[SkillRecord]:
    """
    Scan an install target directory (global ~/.ai-skills or local .ai-skills).
    Uses the same adapter chain, so any structure is understood.
    """
    return scan_repository(install_dir)


def group_by_name(records: list[SkillRecord]) -> dict[str, list[SkillRecord]]:
    """Group records by their canonical name (ignoring artifact_type).

    Note: This groups across artifact types — a skill named 'deploy' and a
    command named 'deploy' will be in the same group.  Use ``group_by_full_name``
    when cross-type collision must be avoided.
    """
    groups: dict[str, list[SkillRecord]] = {}
    for r in records:
        groups.setdefault(r.name, []).append(r)
    return groups


def group_by_full_name(records: list[SkillRecord]) -> dict[str, list[SkillRecord]]:
    """Group records by artifact_type/name."""
    groups: dict[str, list[SkillRecord]] = {}
    for r in records:
        groups.setdefault(r.full_name, []).append(r)
    return groups


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _deduplicate(records: list[SkillRecord]) -> list[SkillRecord]:
    """
    Remove exact duplicates (same path + adapter).
    Different versions of the same skill are NOT removed — the resolver
    chooses among them.
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[SkillRecord] = []
    for r in records:
        key = (r.artifact_type, r.name, str(r.path))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out
