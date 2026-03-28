"""Tests for aom.git — GitRepo and helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aom.git import GitRepo, _cache_base, _url_hash, _TAG_RE


# ===================================================================
# Tag regex
# ===================================================================

class TestTagRegex:
    @pytest.mark.parametrize("tag,expected", [
        ("skills/create-jira@1.0.0", ("skills", "create-jira", "1.0.0")),
        ("commands/deploy-skills@2.0.0", ("commands", "deploy-skills", "2.0.0")),
        ("agents/my-agent@1.0.0-beta", ("agents", "my-agent", "1.0.0-beta")),
        ("hooks/pre-commit@0.1.0", ("hooks", "pre-commit", "0.1.0")),
        ("skills/child/painter@1.2.3", ("skills", "child/painter", "1.2.3")),
    ])
    def test_valid_tags(self, tag, expected):
        m = _TAG_RE.match(tag)
        assert m is not None
        assert (m.group(1), m.group(2), m.group(3)) == expected

    @pytest.mark.parametrize("tag", [
        "invalid-tag",
        "skills/no-version",
        "other/create@1.0.0",  # 'other' not in allowed types
        "",
    ])
    def test_invalid_tags(self, tag):
        assert _TAG_RE.match(tag) is None


# ===================================================================
# Cache helpers
# ===================================================================

class TestCacheHelpers:
    def test_url_hash_deterministic(self):
        h1 = _url_hash("git@github.com:user/repo.git")
        h2 = _url_hash("git@github.com:user/repo.git")
        assert h1 == h2
        assert len(h1) == 12

    def test_url_hash_different(self):
        h1 = _url_hash("git@github.com:a/repo.git")
        h2 = _url_hash("git@github.com:b/repo.git")
        assert h1 != h2

    @patch("platform.system", return_value="Linux")
    def test_cache_base_linux(self, mock_sys, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        base = _cache_base()
        assert "ai-operation-manager" in str(base)

    @patch("platform.system", return_value="Windows")
    def test_cache_base_windows(self, mock_sys, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")
        base = _cache_base()
        assert "ai-operation-manager" in str(base)


# ===================================================================
# GitRepo
# ===================================================================

class TestGitRepo:
    def test_init(self):
        repo = GitRepo("git@github.com:user/repo.git")
        assert repo.url == "git@github.com:user/repo.git"
        assert "ai-operation-manager" in str(repo.cache_dir)

    def test_custom_cache_dir(self, tmp_path):
        repo = GitRepo("git@github.com:user/repo.git", cache_dir=tmp_path / "cache")
        assert repo.cache_dir == tmp_path / "cache"

    def test_is_cloned_false(self, tmp_path):
        repo = GitRepo("x", cache_dir=tmp_path / "empty")
        assert repo.is_cloned is False

    def test_is_cloned_true(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        repo = GitRepo("x", cache_dir=cache)
        assert repo.is_cloned is True

    @patch.object(GitRepo, "_run")
    def test_ensure_cloned_skips_if_cloned(self, mock_run, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        repo = GitRepo("x", cache_dir=cache)
        repo.ensure_cloned()
        mock_run.assert_not_called()

    @patch.object(GitRepo, "_run")
    def test_ensure_cloned_calls_git(self, mock_run, tmp_path):
        repo = GitRepo("git@github.com:x/y.git", cache_dir=tmp_path / "cache")
        repo.ensure_cloned()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "clone" in cmd

    @patch.object(GitRepo, "_run")
    def test_fetch(self, mock_run, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        repo = GitRepo("x", cache_dir=cache)
        repo.fetch()
        cmd = mock_run.call_args[0][0]
        assert "fetch" in cmd

    @patch.object(GitRepo, "_run")
    def test_list_skill_tags(self, mock_run, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        mock_run.return_value = (
            "skills/a@1.0.0\n"
            "skills/b@2.0.0\n"
            "invalid-tag\n"
        )
        repo = GitRepo("x", cache_dir=cache)
        tags = repo.list_skill_tags()
        assert len(tags) == 2
        assert ("skills", "a", "1.0.0") in tags
        assert ("skills", "b", "2.0.0") in tags

    @patch.object(GitRepo, "_run")
    def test_get_object_type(self, mock_run, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        mock_run.return_value = "tree\n"
        repo = GitRepo("x", cache_dir=cache)
        assert repo.get_object_type("tag", "path") == "tree"

    @patch.object(GitRepo, "_run", side_effect=RuntimeError("not found"))
    def test_get_object_type_not_found(self, mock_run, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        repo = GitRepo("x", cache_dir=cache)
        assert repo.get_object_type("tag", "path") is None

    @patch.object(GitRepo, "_run")
    def test_read_file_at_tag(self, mock_run, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "HEAD").touch()
        mock_run.return_value = "file content"
        repo = GitRepo("x", cache_dir=cache)
        content = repo.read_file_at_tag("tag", "file.md")
        assert content == "file content"
