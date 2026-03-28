"""Shared fixtures for the aom test suite."""
from __future__ import annotations

import io
import os
import sys
import pytest
from pathlib import Path

from aom.models import SkillRecord, Version, parse_version


@pytest.fixture(autouse=True)
def _isolate_agent_cache(monkeypatch):
    """Reset the in-process agent cache between tests."""
    import aom.config as cfg
    monkeypatch.setattr(cfg, "_AGENT_CACHE", None)
    monkeypatch.setenv("AI_AGENT_DEFAULT", "ClaudeCode")


@pytest.fixture(autouse=True)
def _prevent_stdout_wrapping(monkeypatch):
    """Prevent cli.main() from wrapping sys.stdout/stderr on Windows.

    The TextIOWrapper replacement closes the underlying buffer and breaks
    pytest's capsys / tmp_path cleanup.
    """
    monkeypatch.setattr(sys, "_called_from_test", True, raising=False)


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal skills repository layout."""
    for d in ("skills", "commands", "agents", "hooks"):
        (tmp_path / d).mkdir()
    return tmp_path


@pytest.fixture
def make_record():
    """Factory fixture for creating SkillRecords."""
    def _make(
        name="test-skill",
        artifact_type="skills",
        path=None,
        version_str="1.0.0",
        structure="metadata",
        git_tag=None,
    ):
        version = parse_version(version_str) if version_str else None
        return SkillRecord(
            name=name,
            artifact_type=artifact_type,
            path=path,
            version=version,
            structure=structure,
            git_tag=git_tag,
        )
    return _make
