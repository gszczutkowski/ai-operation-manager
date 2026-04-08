"""Tests for aom.cli — argument parsing and command dispatch."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aom.cli import build_parser, main, _c, _best_version_str, _suggest_similar


# ===================================================================
# Colour helpers
# ===================================================================

class TestColourHelpers:
    def test_c_with_colour(self):
        result = _c("hello", "32")
        assert result in ("hello", "\033[32mhello\033[0m")

    def test_c_no_colour(self):
        # When not a tty, should return plain text
        with patch("aom.cli._USE_COLOUR", False):
            assert _c("test", "32") == "test"


# ===================================================================
# Argument parsing
# ===================================================================

class TestBuildParser:
    def test_no_command_prints_help(self, capsys):
        """No subcommand should print help and return 0."""
        result = main([])
        assert result == 0

    def test_install_spec(self):
        parser = build_parser()
        args = parser.parse_args(["install", "my-skill:1.0.0"])
        assert args.command == "install"
        assert args.spec == "my-skill:1.0.0"

    def test_install_with_global(self):
        parser = build_parser()
        args = parser.parse_args(["install", "x", "--global"])
        assert args.global_ is True

    def test_list_json(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--json"])
        assert args.json is True

    def test_sync_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--dry-run"])
        assert args.dry_run is True

    def test_sync_force(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--force"])
        assert args.force is True

    def test_remove_name(self):
        parser = build_parser()
        args = parser.parse_args(["remove", "old-skill"])
        assert args.name == "old-skill"

    def test_update_name(self):
        parser = build_parser()
        args = parser.parse_args(["update", "my-skill"])
        assert args.name == "my-skill"

    def test_env_check(self):
        parser = build_parser()
        args = parser.parse_args(["env", "--check"])
        assert args.check is True

    def test_type_filter(self):
        parser = build_parser()
        args = parser.parse_args(["install", "x", "--type", "commands"])
        assert args.type == "commands"

    def test_project_dir(self):
        parser = build_parser()
        args = parser.parse_args(["install", "x", "--project-dir", "/tmp/proj"])
        assert args.project_dir == Path("/tmp/proj")

    def test_fetch_flag(self):
        parser = build_parser()
        args = parser.parse_args(["install", "x", "--fetch"])
        assert args.fetch is True

    def test_no_fetch_flag(self):
        parser = build_parser()
        args = parser.parse_args(["install", "x", "--no-fetch"])
        assert args.no_fetch is True

    def test_fetch_command(self):
        parser = build_parser()
        args = parser.parse_args(["fetch"])
        assert args.command == "fetch"

    def test_list_no_fetch(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--no-fetch"])
        assert args.no_fetch is True

    def test_sync_no_fetch(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "--no-fetch"])
        assert args.no_fetch is True

    def test_update_no_fetch(self):
        parser = build_parser()
        args = parser.parse_args(["update", "x", "--no-fetch"])
        assert args.no_fetch is True

    def test_debug_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--debug", "list"])
        assert args.debug is True


# ===================================================================
# _best_version_str
# ===================================================================

class TestBestVersionStr:
    def test_found(self, make_record):
        records = [make_record(name="x", version_str="1.0.0")]
        assert _best_version_str("x", records) == "1.0.0"

    def test_not_found(self):
        assert _best_version_str("x", []) == "—"


# ===================================================================
# _suggest_similar
# ===================================================================

class TestSuggestSimilar:
    def test_suggests(self, make_record, capsys):
        records = [
            make_record(name="create-jira-story"),
            make_record(name="create-presentation"),
        ]
        _suggest_similar("create", records)
        out = capsys.readouterr().out
        assert "create-jira-story" in out

    def test_no_suggestions(self, capsys):
        _suggest_similar("zzz", [])
        out = capsys.readouterr().out
        assert out == ""


# ===================================================================
# cmd_install (integration-lite)
# ===================================================================

class TestCmdInstall:
    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli.resolve", return_value=None)
    def test_skill_not_found(self, mock_resolve, mock_local,
                             mock_global, mock_scan_inst,
                             mock_local_paths,
                             mock_git, capsys):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")

        result = main(["install", "nonexistent-skill"])
        assert result == 1


# ===================================================================
# Command dispatch
# ===================================================================

class TestDispatch:
    def test_unknown_command(self):
        """Unknown command should cause argparse to exit."""
        with pytest.raises(SystemExit):
            main(["unknown-command"])

    @patch("aom.cli.cmd_env")
    def test_env_dispatches(self, mock_env):
        mock_env.return_value = 0
        result = main(["env"])
        assert result == 0
        mock_env.assert_called_once()

    @patch("aom.cli.cmd_view")
    def test_view_dispatches(self, mock_view):
        mock_view.return_value = 0
        result = main(["view", "my-skill", "versions"])
        assert result == 0
        mock_view.assert_called_once()


# ===================================================================
# view command
# ===================================================================

class TestBuildParserView:
    def test_view_versions(self):
        parser = build_parser()
        args = parser.parse_args(["view", "my-skill", "versions"])
        assert args.command == "view"
        assert args.name == "my-skill"
        assert args.view_command == "versions"

    def test_view_json(self):
        parser = build_parser()
        args = parser.parse_args(["view", "my-skill", "versions", "--json"])
        assert args.json is True

    def test_view_fetch(self):
        parser = build_parser()
        args = parser.parse_args(["view", "my-skill", "versions", "--fetch"])
        assert args.fetch is True

    def test_view_no_fetch(self):
        parser = build_parser()
        args = parser.parse_args(["view", "my-skill", "versions", "--no-fetch"])
        assert args.no_fetch is True

    def test_view_invalid_subcommand(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["view", "my-skill", "invalid"])


class TestCmdView:
    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    def test_no_versions_found(self, mock_local, mock_global,
                               mock_scan, mock_local_paths,
                               mock_git, capsys):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")
        result = main(["view", "nonexistent", "versions"])
        assert result == 1
        assert "No versions found" in capsys.readouterr().out

    @patch("aom.cli._fetch_if_requested")
    @patch("aom.cli._get_git_repos")
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli._get_repo_records", return_value=[])
    def test_no_versions_suggests_fetch(self, mock_repo_records, mock_local,
                                        mock_global, mock_scan,
                                        mock_local_paths, mock_git,
                                        mock_fetch, capsys):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")
        # Simulate having repos configured (so the tip is shown)
        mock_git.return_value = ["fake-repo"]
        result = main(["view", "nonexistent", "versions"])
        assert result == 1
        out = capsys.readouterr().out
        assert "No versions found" in out
        assert "--fetch" in out

    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli._get_repo_records")
    def test_versions_found(self, mock_repo_records, mock_local, mock_global,
                            mock_scan, mock_local_paths,
                            mock_git, make_record, capsys):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")
        mock_repo_records.return_value = [
            make_record(name="my-skill", version_str="1.0.0"),
            make_record(name="my-skill", version_str="2.0.0"),
            make_record(name="my-skill", version_str="2.1.0-SNAPSHOT"),
        ]
        result = main(["view", "my-skill", "versions"])
        assert result == 0
        out = capsys.readouterr().out
        assert "1.0.0" in out
        assert "2.0.0" in out
        assert "2.1.0-SNAPSHOT" in out
        assert "3 version(s) found" in out

    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli._get_repo_records")
    def test_versions_json(self, mock_repo_records, mock_local, mock_global,
                           mock_scan, mock_local_paths,
                           mock_git, make_record, capsys):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")
        mock_repo_records.return_value = [
            make_record(name="my-skill", version_str="1.0.0"),
            make_record(name="my-skill", version_str="2.0.0"),
        ]
        result = main(["view", "my-skill", "versions", "--json"])
        assert result == 0
        import json
        out = json.loads(capsys.readouterr().out)
        assert out["name"] == "my-skill"
        assert len(out["versions"]) == 2
        assert out["versions"][0]["version"] == "2.0.0"  # sorted desc
        assert out["versions"][1]["version"] == "1.0.0"

    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli._get_repo_records")
    def test_versions_case_insensitive(self, mock_repo_records, mock_local, mock_global,
                                       mock_scan, mock_local_paths,
                                       mock_git, make_record, capsys):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")
        mock_repo_records.return_value = [
            make_record(name="My-Skill", version_str="1.0.0"),
        ]
        result = main(["view", "my-skill", "versions"])
        assert result == 0
        assert "1.0.0" in capsys.readouterr().out

    def test_view_project_dir(self):
        parser = build_parser()
        args = parser.parse_args(["view", "x", "versions", "--project-dir", "/tmp/proj"])
        assert args.project_dir == Path("/tmp/proj")
