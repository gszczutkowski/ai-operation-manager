"""
Option B — Directory-based versioning.

Supported layouts:
  skills/simple-evaluator/1.0.0/SKILL.md
  skills/simple-evaluator/1.0.0.md
  skills/child/page-painter/1.2.3/SKILL.md

A directory (or file stem) whose name matches X.Y.Z[-prerelease] and whose
PARENT is NOT itself a semver-named directory is treated as a version container.
"""
from __future__ import annotations

from pathlib import Path

from .base import SEMVER_RE, StructureAdapter
from ..models import SkillRecord, parse_version


def _is_version(name: str) -> bool:
    return bool(SEMVER_RE.match(name))


class DirAdapter(StructureAdapter):
    name = "directory"

    def can_handle(self, path: Path) -> bool:
        # The path itself is a version directory / versioned file
        stem = path.stem if path.is_file() else path.name
        return _is_version(stem)

    def extract_records(
        self,
        artifact_dir: Path,
        artifact_type: str,
    ) -> list[SkillRecord]:
        records: list[SkillRecord] = []
        if not artifact_dir.is_dir():
            return records

        visited: set[Path] = set()

        for entry in artifact_dir.rglob("*"):
            if entry in visited:
                continue

            # Only consider directories and .md files
            if entry.is_file() and entry.suffix.lower() != ".md":
                continue

            stem = entry.stem if entry.is_file() else entry.name
            if not _is_version(stem):
                continue

            version = parse_version(stem)
            if version is None:
                continue

            # The skill name is the relative path of the PARENT from artifact_dir
            try:
                parent_rel = entry.parent.relative_to(artifact_dir)
            except ValueError:
                continue

            if not str(parent_rel) or str(parent_rel) == ".":
                # Version directly under artifact_dir — no skill name, skip
                continue

            name = "/".join(parent_rel.parts)
            records.append(
                SkillRecord(
                    name=name,
                    artifact_type=artifact_type,
                    path=entry,
                    version=version,
                    structure=self.name,
                )
            )
            visited.add(entry)

        return records
