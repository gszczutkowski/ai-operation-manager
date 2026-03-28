"""Tests for aom.registry — JSON registry persistence."""
from __future__ import annotations

import json

from aom.registry import Registry


class TestRegistry:
    def test_new_registry(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        assert reg.all_installed() == {}

    def test_set_and_get(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        reg.set_version("skills/my-skill", "1.0.0")
        assert reg.get_version("skills/my-skill") == "1.0.0"

    def test_get_missing(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        assert reg.get_version("nonexistent") is None

    def test_remove_existing(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        reg.set_version("skills/x", "1.0.0")
        assert reg.remove("skills/x") is True
        assert reg.get_version("skills/x") is None

    def test_remove_nonexistent(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        assert reg.remove("nonexistent") is False

    def test_all_installed(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        reg.set_version("skills/a", "1.0.0")
        reg.set_version("commands/b", "2.0.0")
        installed = reg.all_installed()
        assert installed == {"skills/a": "1.0.0", "commands/b": "2.0.0"}

    def test_persistence(self, tmp_path):
        path = tmp_path / "registry.json"
        reg1 = Registry(path)
        reg1.set_version("skills/x", "1.0.0")

        # Load a fresh instance from disk
        reg2 = Registry(path)
        assert reg2.get_version("skills/x") == "1.0.0"

    def test_reload(self, tmp_path):
        path = tmp_path / "registry.json"
        reg = Registry(path)
        reg.set_version("skills/x", "1.0.0")

        # Externally modify the file
        data = json.loads(path.read_text(encoding="utf-8"))
        data["installed"]["skills/y"] = "2.0.0"
        path.write_text(json.dumps(data), encoding="utf-8")

        # Before reload, new entry not visible
        assert reg.get_version("skills/y") is None
        reg.reload()
        assert reg.get_version("skills/y") == "2.0.0"

    def test_corrupt_file(self, tmp_path, capsys):
        path = tmp_path / "registry.json"
        path.write_text("NOT JSON", encoding="utf-8")
        reg = Registry(path)
        assert reg.all_installed() == {}
        captured = capsys.readouterr()
        assert "corrupt" in captured.err.lower() or "warning" in captured.err.lower()

    def test_schema_version_mismatch(self, tmp_path, capsys):
        path = tmp_path / "registry.json"
        path.write_text(json.dumps({"version": 99, "installed": {}}), encoding="utf-8")
        Registry(path)
        captured = capsys.readouterr()
        assert "schema version" in captured.err.lower() or "99" in captured.err

    def test_overwrite_version(self, tmp_path):
        reg = Registry(tmp_path / "registry.json")
        reg.set_version("skills/x", "1.0.0")
        reg.set_version("skills/x", "2.0.0")
        assert reg.get_version("skills/x") == "2.0.0"

    def test_updated_at_set(self, tmp_path):
        path = tmp_path / "registry.json"
        reg = Registry(path)
        reg.set_version("skills/x", "1.0.0")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "updated_at" in data

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "registry.json"
        reg = Registry(path)
        reg.set_version("skills/x", "1.0.0")
        assert path.exists()
