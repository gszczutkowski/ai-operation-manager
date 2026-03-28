"""Tests for aom.adapters — SuffixAdapter, DirAdapter, MetadataAdapter."""
from __future__ import annotations

from pathlib import Path

from aom.adapters.suffix_adapter import SuffixAdapter
from aom.adapters.dir_adapter import DirAdapter
from aom.adapters.metadata_adapter import MetadataAdapter
from aom.adapters.base import StructureAdapter


# ===================================================================
# SuffixAdapter
# ===================================================================

class TestSuffixAdapter:
    def setup_method(self):
        self.adapter = SuffixAdapter()

    def test_can_handle_dir(self, tmp_path):
        d = tmp_path / "my-skill@1.0.0"
        d.mkdir()
        assert self.adapter.can_handle(d) is True

    def test_can_handle_file(self, tmp_path):
        f = tmp_path / "my-skill@1.0.0.md"
        f.touch()
        assert self.adapter.can_handle(f) is True

    def test_cannot_handle_plain(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        assert self.adapter.can_handle(d) is False

    def test_extract_dir_layout(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill = skills_dir / "evaluator@1.0.0"
        skill.mkdir()
        (skill / "SKILL.md").write_text("content", encoding="utf-8")

        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "evaluator"
        assert records[0].version.raw == "1.0.0"
        assert records[0].structure == "suffix"

    def test_extract_file_layout(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "my-cmd@2.0.0.md").write_text("content", encoding="utf-8")

        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "my-cmd"
        assert records[0].version.raw == "2.0.0"

    def test_extract_nested(self, tmp_path):
        skills_dir = tmp_path / "skills"
        child = skills_dir / "child"
        versioned = child / "painter@1.2.3"
        versioned.mkdir(parents=True)
        (versioned / "SKILL.md").touch()

        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "child/painter"

    def test_empty_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        assert self.adapter.extract_records(skills_dir, "skills") == []

    def test_nonexistent_dir(self, tmp_path):
        assert self.adapter.extract_records(tmp_path / "nope", "skills") == []

    def test_deduplication(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skill = skills_dir / "x@1.0.0"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("a", encoding="utf-8")
        (skill / "extra.md").write_text("b", encoding="utf-8")

        records = self.adapter.extract_records(skills_dir, "skills")
        # The dir itself matches, but files inside don't match suffix pattern
        names = [r.name for r in records]
        assert names.count("x") == 1

    def test_prerelease(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        d = skills_dir / "x@1.0.0-beta"
        d.mkdir()
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].version.prerelease == "beta"


# ===================================================================
# DirAdapter
# ===================================================================

class TestDirAdapter:
    def setup_method(self):
        self.adapter = DirAdapter()

    def test_can_handle_version_dir(self, tmp_path):
        d = tmp_path / "1.0.0"
        d.mkdir()
        assert self.adapter.can_handle(d) is True

    def test_cannot_handle_name_dir(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        assert self.adapter.can_handle(d) is False

    def test_extract_dir_layout(self, tmp_path):
        skills_dir = tmp_path / "skills"
        version_dir = skills_dir / "evaluator" / "1.0.0"
        version_dir.mkdir(parents=True)
        (version_dir / "SKILL.md").touch()

        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "evaluator"
        assert records[0].version.raw == "1.0.0"
        assert records[0].structure == "directory"

    def test_extract_file_layout(self, tmp_path):
        skills_dir = tmp_path / "skills"
        (skills_dir / "my-skill").mkdir(parents=True)
        (skills_dir / "my-skill" / "2.0.0.md").write_text("x", encoding="utf-8")

        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "my-skill"

    def test_multiple_versions(self, tmp_path):
        skills_dir = tmp_path / "skills"
        for v in ("1.0.0", "2.0.0", "3.0.0"):
            (skills_dir / "x" / v).mkdir(parents=True)
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 3
        versions = {r.version.raw for r in records}
        assert versions == {"1.0.0", "2.0.0", "3.0.0"}

    def test_skips_version_at_root(self, tmp_path):
        skills_dir = tmp_path / "skills"
        (skills_dir / "1.0.0").mkdir(parents=True)
        records = self.adapter.extract_records(skills_dir, "skills")
        assert records == []

    def test_nonexistent_dir(self, tmp_path):
        assert self.adapter.extract_records(tmp_path / "nope", "skills") == []

    def test_nested_name(self, tmp_path):
        skills_dir = tmp_path / "skills"
        (skills_dir / "child" / "painter" / "1.0.0").mkdir(parents=True)
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "child/painter"


# ===================================================================
# MetadataAdapter
# ===================================================================

class TestMetadataAdapter:
    def setup_method(self):
        self.adapter = MetadataAdapter()

    def test_can_handle_plain(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        assert self.adapter.can_handle(d) is True

    def test_cannot_handle_suffix(self, tmp_path):
        d = tmp_path / "my-skill@1.0.0"
        d.mkdir()
        assert self.adapter.can_handle(d) is False

    def test_cannot_handle_version_dir(self, tmp_path):
        d = tmp_path / "1.0.0"
        d.mkdir()
        assert self.adapter.can_handle(d) is False

    def test_extract_module_with_frontmatter(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "evaluator"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: evaluator\nmetadata:\n  version: 1.0.0\n---\n\nContent",
            encoding="utf-8",
        )
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "evaluator"
        assert records[0].version is not None
        assert records[0].version.raw == "1.0.0"
        assert records[0].structure == "metadata"

    def test_extract_flat_file(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "deploy.md").write_text(
            "---\nname: deploy\nversion: 2.0.0\n---\n\nDeploy skill",
            encoding="utf-8",
        )
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "deploy"
        assert records[0].version.raw == "2.0.0"

    def test_no_frontmatter(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "plain.md").write_text("Just text, no frontmatter.", encoding="utf-8")
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].version is None

    def test_nested_module(self, tmp_path):
        skills_dir = tmp_path / "skills"
        nested = skills_dir / "child" / "painter"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text(
            "---\nname: painter\nmetadata:\n  version: 1.2.3\n---\n",
            encoding="utf-8",
        )
        records = self.adapter.extract_records(skills_dir, "skills")
        assert len(records) == 1
        assert records[0].name == "child/painter"

    def test_skips_versioned_components(self, tmp_path):
        """Should not pick up paths that look like suffix/dir versioning."""
        skills_dir = tmp_path / "skills"
        versioned = skills_dir / "x@1.0.0"
        versioned.mkdir(parents=True)
        (versioned / "SKILL.md").touch()
        records = self.adapter.extract_records(skills_dir, "skills")
        assert records == []

    def test_empty_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        assert self.adapter.extract_records(skills_dir, "skills") == []

    def test_nonexistent_dir(self, tmp_path):
        assert self.adapter.extract_records(tmp_path / "nope", "skills") == []


# ===================================================================
# StructureAdapter base helpers
# ===================================================================

class TestBaseHelpers:
    def test_read_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: x\nversion: 1.0.0\n---\nBody", encoding="utf-8")
        fm = StructureAdapter._read_frontmatter(f)
        assert fm is not None
        assert "name: x" in fm

    def test_read_frontmatter_missing(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("No frontmatter here.", encoding="utf-8")
        assert StructureAdapter._read_frontmatter(f) is None

    def test_read_frontmatter_no_close(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: x\nNo closing delimiter", encoding="utf-8")
        assert StructureAdapter._read_frontmatter(f) is None

    def test_extract_version_top_level(self):
        fm = "name: x\nversion: 1.2.3\n"
        v = StructureAdapter._extract_version_from_frontmatter(fm)
        assert v == "1.2.3"

    def test_extract_version_nested(self):
        fm = "name: x\nmetadata:\n  version: 2.0.0\n"
        v = StructureAdapter._extract_version_from_frontmatter(fm)
        assert v == "2.0.0"

    def test_extract_version_none(self):
        assert StructureAdapter._extract_version_from_frontmatter("name: x\n") is None

    def test_normalize_name(self):
        assert StructureAdapter._normalize_name("child\\painter", Path()) == "child/painter"
        assert StructureAdapter._normalize_name("/trailing/", Path()) == "trailing"
