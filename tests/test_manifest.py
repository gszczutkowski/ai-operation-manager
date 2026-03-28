"""Tests for aom.manifest — CLAUDE.md parsing and writing."""
from __future__ import annotations

from aom.manifest import (
    parse_manifest,
    write_manifest,
    parse_repo_url,
    write_repo_url,
    _extract_section,
    _parse_requirements,
)
from aom.models import VersionRequirement


# ===================================================================
# _extract_section
# ===================================================================

class TestExtractSection:
    def test_fenced_yaml(self):
        text = (
            "# My Project\n\n"
            "## Skills Requirements\n\n"
            "```yaml\n"
            "required:\n"
            '  my-skill: "1.0.0"\n'
            "```\n"
        )
        section = _extract_section(text)
        assert section is not None
        assert "my-skill" in section

    def test_no_section(self):
        assert _extract_section("# Some other doc\nNo skills here.") is None

    def test_case_insensitive_header(self):
        text = "## SKILLS REQUIREMENTS\n\n```yaml\nrequired:\n  x: 1.0.0\n```\n"
        assert _extract_section(text) is not None

    def test_indented_fallback(self):
        text = "## Skills Requirements\n\n    required:\n    x: 1.0.0\n"
        section = _extract_section(text)
        assert section is not None

    def test_bounded_by_next_header(self):
        text = (
            "## Skills Requirements\n\n"
            "```yaml\nrequired:\n  a: 1.0.0\n```\n\n"
            "## Other Section\n\nSome other content.\n"
        )
        section = _extract_section(text)
        assert "a" in section
        assert "Other Section" not in (section or "")


# ===================================================================
# _parse_requirements
# ===================================================================

class TestParseRequirements:
    def test_basic(self):
        yaml_text = 'required:\n  my-skill: "1.0.0"\n  other: "latest"\n'
        reqs = _parse_requirements(yaml_text)
        assert len(reqs) == 2
        assert reqs[0].name == "my-skill"
        assert reqs[0].constraint == "1.0.0"
        assert reqs[1].name == "other"
        assert reqs[1].constraint == "latest"

    def test_minimum_version(self):
        yaml_text = 'required:\n  x: ">=1.2.0"\n'
        reqs = _parse_requirements(yaml_text)
        assert reqs[0].constraint == ">=1.2.0"

    def test_nested_name(self):
        yaml_text = 'required:\n  child/page-painter: "1.0.0"\n'
        reqs = _parse_requirements(yaml_text)
        assert reqs[0].name == "child/page-painter"

    def test_empty(self):
        assert _parse_requirements("") == []
        assert _parse_requirements("nothing: here") == []

    def test_comments_skipped(self):
        yaml_text = 'required:\n  # this is a comment\n  x: "1.0.0"\n'
        reqs = _parse_requirements(yaml_text)
        assert len(reqs) == 1

    def test_stops_at_new_top_level_key(self):
        yaml_text = 'required:\n  a: "1.0.0"\noptional:\n  b: "2.0.0"\n'
        reqs = _parse_requirements(yaml_text)
        assert len(reqs) == 1
        assert reqs[0].name == "a"


# ===================================================================
# parse_manifest
# ===================================================================

class TestParseManifest:
    def test_full_manifest(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        md.write_text(
            "# Project\n\n"
            "## Skills Requirements\n\n"
            "```yaml\n"
            "required:\n"
            '  skill-a: "1.0.0"\n'
            '  skill-b: ">=2.0.0"\n'
            "```\n",
            encoding="utf-8",
        )
        reqs = parse_manifest(md)
        assert len(reqs) == 2

    def test_missing_file(self, tmp_path):
        assert parse_manifest(tmp_path / "nonexistent.md") == []

    def test_no_requirements_section(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        md.write_text("# Project\nNo skills section here.", encoding="utf-8")
        assert parse_manifest(md) == []


# ===================================================================
# write_manifest
# ===================================================================

class TestWriteManifest:
    def test_creates_new_file(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        reqs = [VersionRequirement("x", "1.0.0")]
        write_manifest(md, reqs)
        assert md.exists()
        content = md.read_text(encoding="utf-8")
        assert "Skills Requirements" in content
        assert 'x: "1.0.0"' in content

    def test_appends_to_existing(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        md.write_text("# My Project\n\nSome text.\n", encoding="utf-8")
        write_manifest(md, [VersionRequirement("y", "latest")])
        content = md.read_text(encoding="utf-8")
        assert "My Project" in content
        assert "Skills Requirements" in content

    def test_replaces_existing_section(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        md.write_text(
            "# Project\n\n"
            "## Skills Requirements\n\n"
            "```yaml\nrequired:\n  old: \"1.0.0\"\n```\n",
            encoding="utf-8",
        )
        write_manifest(md, [VersionRequirement("new-skill", "2.0.0")])
        content = md.read_text(encoding="utf-8")
        assert "old" not in content
        assert "new-skill" in content

    def test_roundtrip(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        original = [
            VersionRequirement("a", "1.0.0"),
            VersionRequirement("b", ">=2.0.0"),
        ]
        write_manifest(md, original)
        parsed = parse_manifest(md)
        assert len(parsed) == 2
        assert parsed[0].name == "a"
        assert parsed[1].name == "b"


# ===================================================================
# parse_repo_url / write_repo_url
# ===================================================================

class TestRepoUrl:
    def test_parse_no_file(self, tmp_path):
        assert parse_repo_url(tmp_path / "nonexistent.md") is None

    def test_parse_no_section(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        md.write_text("# No source section", encoding="utf-8")
        assert parse_repo_url(md) is None

    def test_write_and_parse(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        write_repo_url(md, "git@github.com:user/repo.git")
        url = parse_repo_url(md)
        assert url == "git@github.com:user/repo.git"

    def test_write_replaces_existing(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        write_repo_url(md, "git@github.com:old/repo.git")
        write_repo_url(md, "git@github.com:new/repo.git")
        url = parse_repo_url(md)
        assert url == "git@github.com:new/repo.git"

    def test_coexists_with_requirements(self, tmp_path):
        md = tmp_path / "CLAUDE.md"
        write_repo_url(md, "git@github.com:user/repo.git")
        write_manifest(md, [VersionRequirement("x", "1.0.0")])
        assert parse_repo_url(md) == "git@github.com:user/repo.git"
        assert len(parse_manifest(md)) == 1
