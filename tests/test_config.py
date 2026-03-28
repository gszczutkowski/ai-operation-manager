"""Tests for aom.config — configuration and environment management."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from aom.config import (
    AGENT_MAP,
    ARTIFACT_TYPES,
    _read_env,
    _detect_agent_from_cwd,
    get_agent,
    get_global_dir,
    get_config_file,
    get_type_subdir,
    get_local_dir,
    get_local_registry,
    ensure_global_dir,
    ensure_local_dir,
)


# ===================================================================
# Constants
# ===================================================================

class TestConstants:
    def test_artifact_types(self):
        assert "skills" in ARTIFACT_TYPES
        assert "commands" in ARTIFACT_TYPES
        assert "agents" in ARTIFACT_TYPES
        assert "hooks" in ARTIFACT_TYPES

    def test_agent_map_has_claude(self):
        assert "ClaudeCode" in AGENT_MAP
        cfg = AGENT_MAP["ClaudeCode"]
        assert cfg["dir_name"] == ".claude"
        assert cfg["config_file"] == "CLAUDE.md"


# ===================================================================
# _read_env
# ===================================================================

class TestReadEnv:
    def test_reads_existing(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert _read_env("TEST_VAR") == "hello"

    def test_returns_none_for_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert _read_env("TEST_VAR") is None

    def test_returns_none_for_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "")
        assert _read_env("TEST_VAR") is None


# ===================================================================
# Agent detection
# ===================================================================

class TestDetectAgent:
    def test_detect_from_cwd(self, tmp_path, monkeypatch):
        (tmp_path / "CLAUDE.md").touch()
        monkeypatch.chdir(tmp_path)
        assert _detect_agent_from_cwd() == "ClaudeCode"

    def test_no_detection(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _detect_agent_from_cwd() is None


class TestGetAgent:
    def test_from_env(self, monkeypatch):
        """AI_AGENT_DEFAULT env var should select the agent."""
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", None)
        monkeypatch.setenv("AI_AGENT_DEFAULT", "ClaudeCode")
        # No CLAUDE.md in CWD, so detection won't find it
        monkeypatch.chdir(Path(__file__).parent)
        assert get_agent() == "ClaudeCode"

    def test_auto_select_single_agent(self, monkeypatch, tmp_path):
        """When only one agent in AGENT_MAP, auto-select it."""
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", None)
        monkeypatch.delenv("AI_AGENT_DEFAULT", raising=False)
        monkeypatch.chdir(tmp_path)
        # AGENT_MAP has only ClaudeCode by default
        assert get_agent() == "ClaudeCode"


# ===================================================================
# Agent-aware path functions
# ===================================================================

class TestPathFunctions:
    def test_get_global_dir(self, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        gd = get_global_dir()
        assert gd == Path.home() / ".claude"

    def test_get_config_file(self, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        assert get_config_file() == "CLAUDE.md"

    def test_get_type_subdir_skills(self, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        assert get_type_subdir("skills") == "commands"

    def test_get_type_subdir_agents(self, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        assert get_type_subdir("agents") == "agents"

    def test_get_local_dir(self, tmp_path, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        ld = get_local_dir(tmp_path)
        assert ld == tmp_path / ".claude"

    def test_get_local_registry(self, tmp_path, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        lr = get_local_registry(tmp_path)
        assert lr == tmp_path / ".claude" / "registry.json"


# ===================================================================
# ensure_* functions
# ===================================================================

class TestEnsureDirs:
    def test_ensure_global_dir(self, tmp_path, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        # Patch home to use tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ensure_global_dir()
        assert (tmp_path / ".claude").is_dir()
        assert (tmp_path / ".claude" / "commands").is_dir()
        assert (tmp_path / ".claude" / "agents").is_dir()
        assert (tmp_path / ".claude" / "hooks").is_dir()

    def test_ensure_local_dir(self, tmp_path, monkeypatch):
        import aom.config as cfg
        monkeypatch.setattr(cfg, "_AGENT_CACHE", "ClaudeCode")
        ensure_local_dir(tmp_path)
        assert (tmp_path / ".claude").is_dir()
        assert (tmp_path / ".claude" / "commands").is_dir()
