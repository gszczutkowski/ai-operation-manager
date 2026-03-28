"""Tests for aom.discovery — repository scanning and grouping."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aom.discovery import (
    scan_repository,
    scan_git_repository,
    group_by_name,
    group_by_full_name,
    _deduplicate,
)
from aom.models import SkillRecord, parse_version


class TestScanRepository:
    def test_empty_repo(self, tmp_repo):
        records = scan_repository(tmp_repo)
        assert records == []

    def test_finds_metadata_skills(self, tmp_repo):
        skill_dir = tmp_repo / "skills" / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\nmetadata:\n  version: 1.0.0\n---\n",
            encoding="utf-8",
        )
        records = scan_repository(tmp_repo)
        assert len(records) >= 1
        names = [r.name for r in records]
        assert "my-skill" in names

    def test_finds_suffix_skills(self, tmp_repo):
        skill = tmp_repo / "skills" / "evaluator@2.0.0"
        skill.mkdir()
        (skill / "SKILL.md").touch()
        records = scan_repository(tmp_repo)
        names = [r.name for r in records]
        assert "evaluator" in names

    def test_finds_dir_skills(self, tmp_repo):
        (tmp_repo / "skills" / "resolver" / "1.0.0").mkdir(parents=True)
        records = scan_repository(tmp_repo)
        names = [r.name for r in records]
        assert "resolver" in names

    def test_multiple_artifact_types(self, tmp_repo):
        (tmp_repo / "skills" / "a").mkdir()
        (tmp_repo / "skills" / "a" / "SKILL.md").touch()
        (tmp_repo / "commands" / "b").mkdir()
        (tmp_repo / "commands" / "b" / "COMMAND.md").touch()
        records = scan_repository(tmp_repo)
        types = {r.artifact_type for r in records}
        assert "skills" in types
        assert "commands" in types

    def test_nonexistent_type_dir(self, tmp_path):
        """Repo path exists but has no artifact type dirs."""
        records = scan_repository(tmp_path)
        assert records == []


class TestScanGitRepository:
    def test_scan_git(self):
        git_repo = MagicMock()
        git_repo.list_skill_tags.return_value = [
            ("skills", "create-jira", "1.0.0"),
            ("skills", "create-jira", "1.2.0"),
            ("commands", "deploy", "1.0.0"),
        ]
        records = scan_git_repository(git_repo)
        assert len(records) == 3
        assert all(r.structure == "git" for r in records)
        assert all(r.path is None for r in records)
        assert records[0].git_tag == "skills/create-jira@1.0.0"


class TestGroupBy:
    def test_group_by_name(self, make_record):
        records = [
            make_record(name="x", artifact_type="skills"),
            make_record(name="x", artifact_type="commands"),
            make_record(name="y", artifact_type="skills"),
        ]
        groups = group_by_name(records)
        assert len(groups["x"]) == 2
        assert len(groups["y"]) == 1

    def test_group_by_full_name(self, make_record):
        records = [
            make_record(name="x", artifact_type="skills"),
            make_record(name="x", artifact_type="commands"),
        ]
        groups = group_by_full_name(records)
        assert "skills/x" in groups
        assert "commands/x" in groups


class TestDeduplicate:
    def test_removes_exact_dupes(self):
        p = Path("/fake/path")
        r1 = SkillRecord("x", "skills", p, parse_version("1.0.0"), "metadata")
        r2 = SkillRecord("x", "skills", p, parse_version("1.0.0"), "metadata")
        result = _deduplicate([r1, r2])
        assert len(result) == 1

    def test_keeps_different_versions(self):
        r1 = SkillRecord("x", "skills", Path("/a"), parse_version("1.0.0"), "metadata")
        r2 = SkillRecord("x", "skills", Path("/b"), parse_version("2.0.0"), "metadata")
        result = _deduplicate([r1, r2])
        assert len(result) == 2

    def test_keeps_different_types(self):
        p = Path("/same")
        r1 = SkillRecord("x", "skills", p, parse_version("1.0.0"), "metadata")
        r2 = SkillRecord("x", "commands", p, parse_version("1.0.0"), "metadata")
        result = _deduplicate([r1, r2])
        assert len(result) == 2
