"""Tests for aom.installer — install and uninstall logic."""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aom.installer import install, uninstall, _destination, _copy
from aom.models import SkillRecord, parse_version
from aom.registry import Registry


@pytest.fixture
def install_dir(tmp_path):
    """Create a target install directory with standard subdirs."""
    d = tmp_path / "install"
    for sub in ("commands", "agents", "hooks"):
        (d / sub).mkdir(parents=True)
    return d


@pytest.fixture
def registry(tmp_path):
    return Registry(tmp_path / "registry.json")


# ===================================================================
# _copy
# ===================================================================

class TestCopy:
    def test_copy_file(self, tmp_path):
        src = tmp_path / "source.md"
        src.write_text("hello", encoding="utf-8")
        dest = tmp_path / "dest" / "file.md"
        _copy(src, dest)
        assert dest.read_text(encoding="utf-8") == "hello"

    def test_copy_directory(self, tmp_path):
        src = tmp_path / "src_dir"
        src.mkdir()
        (src / "a.md").write_text("a", encoding="utf-8")
        (src / "sub").mkdir()
        (src / "sub" / "b.md").write_text("b", encoding="utf-8")

        dest = tmp_path / "dest_dir"
        _copy(src, dest)
        assert (dest / "a.md").read_text(encoding="utf-8") == "a"
        assert (dest / "sub" / "b.md").read_text(encoding="utf-8") == "b"

    def test_copy_overwrites_existing_dir(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "new.md").write_text("new", encoding="utf-8")

        dest = tmp_path / "dst"
        dest.mkdir()
        (dest / "old.md").write_text("old", encoding="utf-8")

        _copy(src, dest)
        assert (dest / "new.md").exists()
        assert not (dest / "old.md").exists()


# ===================================================================
# _destination
# ===================================================================

class TestDestination:
    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_directory_record(self, mock_subdir, tmp_path, install_dir):
        src = tmp_path / "my-skill"
        src.mkdir()
        record = SkillRecord("my-skill", "skills", src, parse_version("1.0.0"), "metadata")
        dest = _destination(record, install_dir)
        assert dest == install_dir / "commands" / "my-skill"

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_flat_file_record(self, mock_subdir, tmp_path, install_dir):
        src = tmp_path / "deploy.md"
        src.touch()
        record = SkillRecord("deploy", "skills", src, parse_version("1.0.0"), "metadata")
        dest = _destination(record, install_dir)
        assert dest == install_dir / "commands" / "deploy.md"

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_nested_name(self, mock_subdir, tmp_path, install_dir):
        src = tmp_path / "painter.md"
        src.touch()
        record = SkillRecord("child/painter", "skills", src, parse_version("1.0.0"), "metadata")
        dest = _destination(record, install_dir)
        assert dest == install_dir / "commands" / "child" / "painter.md"

    def test_no_path_raises(self, install_dir):
        record = SkillRecord("x", "skills", None, parse_version("1.0.0"), "git")
        with pytest.raises(RuntimeError):
            _destination(record, install_dir)


# ===================================================================
# install
# ===================================================================

class TestInstall:
    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_install_file(self, mock_subdir, tmp_path, install_dir, registry):
        src = tmp_path / "my-skill.md"
        src.write_text("content", encoding="utf-8")
        record = SkillRecord("my-skill", "skills", src, parse_version("1.0.0"), "metadata")

        dest = install(record, install_dir, registry)
        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == "content"
        assert registry.get_version("skills/my-skill") == "1.0.0"

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_install_directory(self, mock_subdir, tmp_path, install_dir, registry):
        src = tmp_path / "my-skill"
        src.mkdir()
        (src / "SKILL.md").write_text("skill content", encoding="utf-8")
        record = SkillRecord("my-skill", "skills", src, parse_version("2.0.0"), "metadata")

        dest = install(record, install_dir, registry)
        assert dest.is_dir()
        assert (dest / "SKILL.md").exists()
        assert registry.get_version("skills/my-skill") == "2.0.0"

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_no_overwrite(self, mock_subdir, tmp_path, install_dir, registry):
        src = tmp_path / "x.md"
        src.write_text("new", encoding="utf-8")
        record = SkillRecord("x", "skills", src, parse_version("1.0.0"), "metadata")

        # Pre-install
        existing = install_dir / "commands" / "x.md"
        existing.write_text("existing", encoding="utf-8")

        dest = install(record, install_dir, registry, overwrite=False)
        assert dest.read_text(encoding="utf-8") == "existing"

    def test_install_no_path_no_git_raises(self, install_dir, registry):
        record = SkillRecord("x", "skills", None, parse_version("1.0.0"), "git")
        with pytest.raises(RuntimeError, match="no local path"):
            install(record, install_dir, registry, git_repo=None)

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_install_from_git_tree(self, mock_subdir, install_dir, registry):
        git_repo = MagicMock()
        git_repo.get_object_type.return_value = "tree"

        record = SkillRecord("my-skill", "skills", None, parse_version("1.0.0"), "git",
                             git_tag="skills/my-skill@1.0.0")

        dest = install(record, install_dir, registry, git_repo=git_repo)
        git_repo.extract_path_at_tag.assert_called_once()
        assert registry.get_version("skills/my-skill") == "1.0.0"

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_install_from_git_blob(self, mock_subdir, install_dir, registry):
        git_repo = MagicMock()
        git_repo.get_object_type.return_value = "blob"
        git_repo.read_file_at_tag.return_value = "# Skill content"

        record = SkillRecord("my-skill", "skills", None, parse_version("1.0.0"), "git",
                             git_tag="skills/my-skill@1.0.0")

        dest = install(record, install_dir, registry, git_repo=git_repo)
        assert dest.name == "my-skill.md"
        assert registry.get_version("skills/my-skill") == "1.0.0"


# ===================================================================
# uninstall
# ===================================================================

class TestUninstall:
    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_uninstall_module(self, mock_subdir, install_dir, registry):
        module = install_dir / "commands" / "my-skill"
        module.mkdir(parents=True)
        (module / "SKILL.md").touch()
        registry.set_version("skills/my-skill", "1.0.0")

        removed = uninstall("skills", "my-skill", install_dir, registry)
        assert removed is True
        assert not module.exists()
        assert registry.get_version("skills/my-skill") is None

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_uninstall_flat_file(self, mock_subdir, install_dir, registry):
        flat = install_dir / "commands" / "deploy.md"
        flat.write_text("x", encoding="utf-8")
        registry.set_version("skills/deploy", "1.0.0")

        removed = uninstall("skills", "deploy", install_dir, registry)
        assert removed is True
        assert not flat.exists()

    @patch("aom.installer.get_type_subdir", return_value="commands")
    def test_uninstall_not_found(self, mock_subdir, install_dir, registry):
        removed = uninstall("skills", "nonexistent", install_dir, registry)
        assert removed is False
