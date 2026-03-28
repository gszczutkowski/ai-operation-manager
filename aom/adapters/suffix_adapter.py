"""
Option A — Suffix-based versioning.

Supported layouts:
  skills/simple-evaluator@1.0.0/SKILL.md
  skills/simple-evaluator@1.0.0.md
  skills/child/page-painter@1.2.3/SKILL.md
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import StructureAdapter
from ..models import SkillRecord, parse_version

_SUFFIX_RE = re.compile(r"^(.+)@(\d+\.\d+\.\d+(?:-.+)?)$")


class SuffixAdapter(StructureAdapter):
    name = "suffix"

    def can_handle(self, path: Path) -> bool:
        stem = path.stem if path.is_file() else path.name
        return bool(_SUFFIX_RE.match(stem))

    def extract_records(
        self,
        artifact_dir: Path,
        artifact_type: str,
    ) -> list[SkillRecord]:
        records: list[SkillRecord] = []
        if not artifact_dir.is_dir():
            return records

        seen: set[tuple[str, str | None]] = set()

        for entry in self._iter_all(artifact_dir):
            stem = entry.stem if entry.is_file() else entry.name
            m = _SUFFIX_RE.match(stem)
            if not m:
                continue

            raw_name, raw_version = m.group(1), m.group(2)
            version = parse_version(raw_version)

            # Compute name relative to artifact_dir, strip version suffix
            try:
                rel = entry.relative_to(artifact_dir)
            except ValueError:
                continue

            # rel could be: "simple-evaluator@1.0.0" or "child/page-painter@1.0.0"
            # Drop the last component (versioned) and replace with the bare name
            parts = list(rel.parts)
            parts[-1] = raw_name  # replace "@version" part with clean name
            name = "/".join(parts)

            # Deduplicate: skip if we already have a record for this name+version
            dedup_key = (name, raw_version)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            records.append(
                SkillRecord(
                    name=name,
                    artifact_type=artifact_type,
                    path=entry,
                    version=version,
                    structure=self.name,
                )
            )

        return records

    # ------------------------------------------------------------------

    def _iter_all(self, root: Path):
        """Yield every direct or nested entry whose name matches @version."""
        for child in root.rglob("*"):
            stem = child.stem if child.is_file() else child.name
            if _SUFFIX_RE.match(stem):
                yield child
