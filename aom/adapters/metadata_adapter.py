"""
Option C — Metadata-based versioning (RECOMMENDED, current repo standard).

Version lives entirely in the frontmatter of the definition file:

  ---
  name: complex-evaluator
  metadata:
    version: 1.0.0
  ---

or for flat command files:

  ---
  name: deploy-skills
  version: 1.0.0
  ---

Supported layouts (all of which exist in ai-grimoire today):
  skills/simple-evaluator.md                     → flat file
  skills/complex-evaluator/SKILL.md              → module directory
  skills/child/page-painter/SKILL.md             → nested module

This adapter handles whatever is NOT matched by the higher-priority
SuffixAdapter or DirAdapter.
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import SEMVER_RE, StructureAdapter
from ..models import SkillRecord, Version, parse_version

# Canonical definition filenames in order of preference
_SKILL_FILENAMES = ("SKILL.md", "COMMAND.md", "AGENT.md", "skill.md", "index.md")

# Pattern that indicates a path component uses suffix-based versioning
_SUFFIX_RE = re.compile(r"^.+@\d+\.\d+\.\d+")


def _is_versioned_component(name: str) -> bool:
    return bool(SEMVER_RE.match(name)) or bool(_SUFFIX_RE.match(name))


class MetadataAdapter(StructureAdapter):
    name = "metadata"

    def can_handle(self, path: Path) -> bool:
        # We handle anything that wasn't grabbed by higher-priority adapters
        stem = path.stem if path.is_file() else path.name
        return not _is_versioned_component(stem)

    def extract_records(
        self,
        artifact_dir: Path,
        artifact_type: str,
    ) -> list[SkillRecord]:
        records: list[SkillRecord] = []
        if not artifact_dir.is_dir():
            return records

        visited_names: set[str] = set()
        # Track which directories are "module roots" (contain a canonical file)
        module_roots: set[Path] = set()

        # --- Pass 1: module directories that contain a canonical definition file ---
        for filename in _SKILL_FILENAMES:
            for skill_file in artifact_dir.rglob(filename):
                try:
                    rel = skill_file.parent.relative_to(artifact_dir)
                except ValueError:
                    continue

                parts = rel.parts
                # Skip if any component looks like a version (Option A/B leftovers)
                if any(_is_versioned_component(p) for p in parts):
                    continue

                name = "/".join(parts)
                if name in visited_names:
                    continue

                version = self._version_from_file(skill_file)
                records.append(
                    SkillRecord(
                        name=name,
                        artifact_type=artifact_type,
                        path=skill_file.parent,
                        version=version,
                        structure=self.name,
                    )
                )
                visited_names.add(name)
                module_roots.add(skill_file.parent)

        # --- Pass 2: flat .md files, skipping module roots and versioned components ---
        for md_file in self._iter_flat_md(artifact_dir, module_roots):
            if md_file.name in _SKILL_FILENAMES:
                continue

            try:
                rel = md_file.relative_to(artifact_dir)
            except ValueError:
                continue

            parts = rel.parts
            if any(_is_versioned_component(p) for p in parts):
                continue

            # Name = path components with stem (no .md) as last part
            name = "/".join(list(parts[:-1]) + [md_file.stem])

            if name in visited_names:
                continue

            version = self._version_from_file(md_file)
            records.append(
                SkillRecord(
                    name=name,
                    artifact_type=artifact_type,
                    path=md_file,
                    version=version,
                    structure=self.name,
                )
            )
            visited_names.add(name)

        return records

    # ------------------------------------------------------------------

    def _iter_flat_md(self, root: Path, skip_dirs: set[Path]):
        """
        Walk *root*, yielding .md files but not descending into *skip_dirs*
        or any of their subdirectories (module roots already handled in Pass 1).
        """
        # Check if root itself is inside a skip directory
        if any(root == sd or sd in root.parents for sd in skip_dirs):
            return
        for child in root.iterdir():
            if child.is_file() and child.suffix.lower() == ".md":
                yield child
            elif child.is_dir() and child not in skip_dirs:
                yield from self._iter_flat_md(child, skip_dirs)

    def _version_from_file(self, path: Path) -> Version | None:
        """Extract version from frontmatter of *path*."""
        frontmatter = self._read_frontmatter(path)
        if not frontmatter:
            return None
        raw = self._extract_version_from_frontmatter(frontmatter)
        return parse_version(raw) if raw else None
