"""Tests for aom.settings — global user settings management."""
from __future__ import annotations

from pathlib import Path

import pytest

from aom.settings import (
    get_settings_dir,
    get_settings_path,
    get_repo_urls,
    set_repo_urls,
    add_repo_url,
    remove_repo_url,
    get_local_paths,
    set_local_paths,
    add_local_path,
    remove_local_path,
    _load_raw,
    _save_raw,
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Redirect settings to a temp directory for every test."""
    settings_dir = tmp_path / "aom-settings"
    monkeypatch.setattr("aom.settings.get_settings_dir", lambda: settings_dir)
    monkeypatch.setattr(
        "aom.settings.get_settings_path",
        lambda: settings_dir / "settings.json",
    )


# ===================================================================
# Path helpers
# ===================================================================

class TestSettingsPaths:
    def test_get_settings_dir_unix(self, monkeypatch):
        """On non-Windows, uses XDG_CONFIG_HOME or ~/.config."""
        monkeypatch.setattr("aom.settings.sys.platform", "linux")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        # Just verify the function is callable and returns a Path
        result = get_settings_dir()
        assert isinstance(result, Path)

    def test_get_settings_path(self):
        result = get_settings_path()
        assert result.name == "settings.json"


# ===================================================================
# Load / save
# ===================================================================

class TestLoadSave:
    def test_load_empty(self):
        data = _load_raw()
        assert data["version"] == 2
        assert data["repositories"] == []
        assert data["local_paths"] == []

    def test_save_and_load(self):
        data = {"version": 2, "repositories": [{"url": "git@example.com:test.git"}], "local_paths": []}
        _save_raw(data)
        loaded = _load_raw()
        assert loaded["repositories"] == data["repositories"]
        assert loaded["local_paths"] == []

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        """Corrupt JSON should fall back to empty settings."""
        settings_path = get_settings_path()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("not valid json", encoding="utf-8")
        data = _load_raw()
        assert data["repositories"] == []
        assert data["local_paths"] == []

    def test_migrate_v1_to_v2(self):
        """v1 settings without local_paths should be migrated transparently."""
        data = {"version": 1, "repositories": [{"url": "git@example.com:test.git"}]}
        _save_raw(data)
        loaded = _load_raw()
        assert loaded["version"] == 2
        assert loaded["local_paths"] == []
        assert len(loaded["repositories"]) == 1


# ===================================================================
# Repository URL management
# ===================================================================

class TestRepoUrls:
    def test_get_empty(self):
        assert get_repo_urls() == []

    def test_set_and_get(self):
        urls = ["git@github.com:a/b.git", "git@github.com:c/d.git"]
        set_repo_urls(urls)
        assert get_repo_urls() == urls

    def test_add_new(self):
        added = add_repo_url("git@github.com:a/b.git")
        assert added is True
        assert get_repo_urls() == ["git@github.com:a/b.git"]

    def test_add_duplicate(self):
        add_repo_url("git@github.com:a/b.git")
        added = add_repo_url("git@github.com:a/b.git")
        assert added is False
        assert len(get_repo_urls()) == 1

    def test_add_multiple(self):
        add_repo_url("git@github.com:a/b.git")
        add_repo_url("git@github.com:c/d.git")
        assert get_repo_urls() == [
            "git@github.com:a/b.git",
            "git@github.com:c/d.git",
        ]

    def test_remove_existing(self):
        set_repo_urls(["git@github.com:a/b.git", "git@github.com:c/d.git"])
        removed = remove_repo_url("git@github.com:a/b.git")
        assert removed is True
        assert get_repo_urls() == ["git@github.com:c/d.git"]

    def test_remove_nonexistent(self):
        removed = remove_repo_url("git@github.com:x/y.git")
        assert removed is False

    def test_set_replaces(self):
        set_repo_urls(["git@github.com:a/b.git"])
        set_repo_urls(["git@github.com:x/y.git"])
        assert get_repo_urls() == ["git@github.com:x/y.git"]

    def test_malformed_entries_skipped(self):
        """Entries without 'url' key are ignored."""
        data = {"version": 2, "repositories": [
            {"url": "git@github.com:a/b.git"},
            {"name": "no-url"},
            "just-a-string",
        ], "local_paths": []}
        _save_raw(data)
        assert get_repo_urls() == ["git@github.com:a/b.git"]


# ===================================================================
# Local path management
# ===================================================================

class TestLocalPaths:
    def test_get_empty(self):
        assert get_local_paths() == []

    def test_set_and_get(self, tmp_path):
        paths = [str(tmp_path / "a"), str(tmp_path / "b")]
        set_local_paths(paths)
        assert get_local_paths() == paths

    def test_add_new(self, tmp_path):
        p = str(tmp_path)
        added = add_local_path(p)
        assert added is True
        assert get_local_paths() == [str(tmp_path.resolve())]

    def test_add_duplicate(self, tmp_path):
        p = str(tmp_path)
        add_local_path(p)
        added = add_local_path(p)
        assert added is False
        assert len(get_local_paths()) == 1

    def test_add_multiple(self, tmp_path):
        p1 = tmp_path / "a"
        p2 = tmp_path / "b"
        p1.mkdir()
        p2.mkdir()
        add_local_path(str(p1))
        add_local_path(str(p2))
        result = get_local_paths()
        assert len(result) == 2

    def test_remove_existing(self, tmp_path):
        p1 = str(tmp_path / "a")
        p2 = str(tmp_path / "b")
        set_local_paths([p1, p2])
        removed = remove_local_path(p1)
        assert removed is True
        assert get_local_paths() == [p2]

    def test_remove_nonexistent(self, tmp_path):
        removed = remove_local_path(str(tmp_path / "nonexistent"))
        assert removed is False

    def test_set_replaces(self, tmp_path):
        set_local_paths([str(tmp_path / "a")])
        set_local_paths([str(tmp_path / "b")])
        assert get_local_paths() == [str(tmp_path / "b")]

    def test_malformed_entries_skipped(self):
        """Empty strings and non-string entries are ignored."""
        data = {"version": 2, "repositories": [], "local_paths": [
            "/valid/path",
            "",
        ]}
        _save_raw(data)
        assert get_local_paths() == ["/valid/path"]

    def test_persists_with_repo_urls(self):
        """Local paths and repo URLs coexist in settings."""
        set_repo_urls(["git@github.com:a/b.git"])
        set_local_paths(["/some/path"])
        assert get_repo_urls() == ["git@github.com:a/b.git"]
        assert get_local_paths() == ["/some/path"]
