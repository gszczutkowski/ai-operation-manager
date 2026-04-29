"""Tests for aom.cli — argument parsing and command dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aom.cli import (
    build_parser,
    main,
    _c,
    _best_version_str,
    _suggest_similar,
    _guess_type,
    _cmd_sync_requirements,
    cmd_init,
    _prompt_agent_selection,
    _prompt_repo_urls,
    _prompt_local_paths,
)

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

    def test_sync_agents_mode(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "agents"])
        assert args.sync_command == "agents"

    def test_sync_clean_mode(self):
        parser = build_parser()
        args = parser.parse_args(["sync", "clean"])
        assert args.sync_command == "clean"

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
    def test_skill_not_found(
        self,
        mock_resolve,
        mock_local,
        mock_global,
        mock_scan_inst,
        mock_local_paths,
        mock_git,
        capsys,
    ):
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")

        result = main(["install", "nonexistent-skill"])
        assert result == 1

    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    @patch("aom.cli.scan_installed", return_value=[])
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli.resolve", return_value=None)
    def test_install_resolves_from_repo_only(
        self,
        mock_resolve,
        mock_local,
        mock_global,
        mock_scan_inst,
        mock_local_paths,
        mock_git,
        capsys,
    ):
        """Install should ignore local/global records so it always picks the
        latest version from the repo, not an already-installed older version."""
        mock_global.return_value = Path("/nonexistent")
        mock_local.return_value = Path("/nonexistent")

        main(["install", "my-skill"])

        mock_resolve.assert_called_once()
        _, kwargs = mock_resolve.call_args
        assert kwargs.get("global_records") == []
        assert kwargs.get("local_records") == []


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
    def test_no_versions_found(
        self, mock_local, mock_global, mock_scan, mock_local_paths, mock_git, capsys
    ):
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
    def test_no_versions_suggests_fetch(
        self,
        mock_repo_records,
        mock_local,
        mock_global,
        mock_scan,
        mock_local_paths,
        mock_git,
        mock_fetch,
        capsys,
    ):
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
    def test_versions_found(
        self,
        mock_repo_records,
        mock_local,
        mock_global,
        mock_scan,
        mock_local_paths,
        mock_git,
        make_record,
        capsys,
    ):
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
    def test_versions_json(
        self,
        mock_repo_records,
        mock_local,
        mock_global,
        mock_scan,
        mock_local_paths,
        mock_git,
        make_record,
        capsys,
    ):
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
    def test_versions_case_insensitive(
        self,
        mock_repo_records,
        mock_local,
        mock_global,
        mock_scan,
        mock_local_paths,
        mock_git,
        make_record,
        capsys,
    ):
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


# ===================================================================
# Deploy / Undeploy
# ===================================================================


class TestBuildParserDeploy:
    def test_deploy_command(self):
        parser = build_parser()
        args = parser.parse_args(["deploy"])
        assert args.command == "deploy"

    def test_undeploy_command(self):
        parser = build_parser()
        args = parser.parse_args(["undeploy"])
        assert args.command == "undeploy"


class TestDeployHelpers:
    def test_get_exe_name_windows(self):
        from aom.cli import _get_exe_name

        with patch("aom.cli.sys") as mock_sys:
            mock_sys.platform = "win32"
            assert _get_exe_name() == "aom.exe"

    def test_get_exe_name_unix(self):
        from aom.cli import _get_exe_name

        with patch("aom.cli.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert _get_exe_name() == "aom"

    def test_find_source_exe_not_frozen(self):
        from aom.cli import _find_source_exe

        # Running from source — no frozen attr
        assert _find_source_exe() is None

    def test_find_source_exe_frozen(self):
        from aom.cli import _find_source_exe

        with patch("aom.cli.sys") as mock_sys:
            mock_sys.frozen = True
            mock_sys.executable = "/usr/local/bin/aom"
            result = _find_source_exe()
            assert result == Path("/usr/local/bin/aom")

    def test_get_deploy_dir_windows(self):
        from aom.cli import _get_deploy_dir

        with (
            patch("aom.cli.sys") as mock_sys,
            patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}),
        ):
            mock_sys.platform = "win32"
            result = _get_deploy_dir()
            expected = Path("C:\\Users\\test\\AppData\\Local") / "ai-operation-manager" / "bin"
            assert result == expected

    def test_get_deploy_dir_unix(self):
        from aom.cli import _get_deploy_dir

        with (
            patch("aom.cli.sys") as mock_sys,
            patch("aom.cli.Path.home", return_value=Path("/home/user")),
        ):
            mock_sys.platform = "linux"
            result = _get_deploy_dir()
            assert result == Path("/home/user/.local/bin")


class TestCmdDeploy:
    def test_deploy_not_frozen(self, capsys):
        """Running from source should fail gracefully."""
        result = main(["deploy"])
        assert result == 1
        out = capsys.readouterr()
        assert "only available when running from a built executable" in out.out

    @patch("aom.cli._find_source_exe")
    @patch("aom.cli._get_deploy_dir")
    @patch("aom.cli._get_exe_name", return_value="aom")
    @patch("shutil.copy2")
    @patch("aom.cli._add_to_path_unix", return_value=True)
    def test_deploy_success_unix(
        self,
        mock_add_path,
        mock_copy,
        mock_exe_name,
        mock_deploy_dir,
        mock_source,
        tmp_path,
        capsys,
    ):
        source = tmp_path / "aom"
        source.touch()
        mock_source.return_value = source
        target_dir = tmp_path / "deploy"
        target_dir.mkdir()
        mock_deploy_dir.return_value = target_dir

        with patch("aom.cli.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_sys.stdout = __import__("sys").stdout
            mock_sys.stderr = __import__("sys").stderr
            result = main(["deploy"])

        assert result == 0
        mock_copy.assert_called_once()
        out = capsys.readouterr().out
        assert "Deployed" in out

    def test_undeploy_nothing(self, tmp_path, capsys):
        with (
            patch("aom.cli._get_deploy_dir", return_value=tmp_path),
            patch("aom.cli._get_exe_name", return_value="aom"),
        ):
            result = main(["undeploy"])
        assert result == 0
        assert "Nothing to remove" in capsys.readouterr().out

    def test_undeploy_removes_file(self, tmp_path, capsys):
        target = tmp_path / "aom"
        target.touch()
        with (
            patch("aom.cli._get_deploy_dir", return_value=tmp_path),
            patch("aom.cli._get_exe_name", return_value="aom"),
            patch("aom.cli._remove_from_path_windows", return_value=False),
            patch("aom.cli.sys") as mock_sys,
        ):
            mock_sys.platform = "win32"
            mock_sys.stdout = __import__("sys").stdout
            mock_sys.stderr = __import__("sys").stderr
            result = main(["undeploy"])
        assert result == 0
        assert not target.exists()
        assert "Removed" in capsys.readouterr().out

    def test_undeploy_purge_removes_cache_and_settings(self, tmp_path, capsys):
        """--purge removes repository cache, settings, and global operations."""
        # Set up fake directories
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "somerepo").mkdir()
        (cache_dir / "somerepo" / "HEAD").touch()

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text("{}")

        global_agent_dir = tmp_path / ".claude"
        global_agent_dir.mkdir()
        (global_agent_dir / "skills").mkdir()
        (global_agent_dir / "skills" / "my-skill.md").write_text("# skill")
        (global_agent_dir / "commands").mkdir()
        (global_agent_dir / "agents").mkdir()
        (global_agent_dir / "hooks").mkdir()
        (global_agent_dir / "registry.json").write_text("{}")

        deploy_dir = tmp_path / "deploy"
        deploy_dir.mkdir()

        agent_map = {
            "ClaudeCode": {
                "dir_name": global_agent_dir.name,
                "config_file": "CLAUDE.md",
                "type_dirs": {
                    "skills": "skills",
                    "commands": "commands",
                    "agents": "agents",
                    "hooks": "hooks",
                },
            }
        }
        with (
            patch("aom.cli._get_deploy_dir", return_value=deploy_dir),
            patch("aom.cli._get_exe_name", return_value="aom"),
            patch("aom.cli.get_cache_base", return_value=cache_dir),
            patch("aom.cli.get_settings_dir", return_value=settings_dir),
            patch("aom.cli.AGENT_MAP", agent_map),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = main(["undeploy", "--purge"])

        assert result == 0
        out = capsys.readouterr().out
        assert not cache_dir.exists()
        assert not settings_dir.exists()
        assert not (global_agent_dir / "registry.json").exists()
        assert not (global_agent_dir / "skills").exists()
        assert "Purging" in out
        assert "repository cache" in out.lower()

    def test_undeploy_purge_no_binary_still_purges(self, tmp_path, capsys):
        """--purge continues even when the binary is not deployed."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        deploy_dir = tmp_path / "deploy"
        deploy_dir.mkdir()

        with (
            patch("aom.cli._get_deploy_dir", return_value=deploy_dir),
            patch("aom.cli._get_exe_name", return_value="aom"),
            patch("aom.cli.get_cache_base", return_value=cache_dir),
            patch("aom.cli.get_settings_dir", return_value=tmp_path / "no-settings"),
            patch("aom.cli.AGENT_MAP", {}),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = main(["undeploy", "--purge"])

        assert result == 0
        out = capsys.readouterr().out
        assert not cache_dir.exists()
        assert "Binary not found" in out


# ===================================================================
# list command
# ===================================================================


class TestCmdList:
    @patch("aom.cli._active_agents", return_value=["ClaudeCode"])
    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli._fetch_if_requested")
    @patch("aom.cli._get_repo_records", return_value=[])
    @patch("aom.cli.get_global_dir", return_value=Path("/nonexistent"))
    @patch("aom.cli.get_local_dir", return_value=Path("/nonexistent"))
    def test_no_skills_found(
        self,
        mock_local,
        mock_global,
        mock_repo_records,
        mock_fetch,
        mock_repos,
        mock_agents,
        capsys,
    ):
        result = main(["list"])
        assert result == 0
        assert "No skills found." in capsys.readouterr().out

    @patch("aom.cli._active_agents", return_value=["ClaudeCode", "Kiro"])
    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli._fetch_if_requested")
    @patch("aom.cli.get_global_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli.scan_installed")
    @patch("aom.cli._get_repo_records")
    def test_json_with_partial_versions(
        self,
        mock_repo_records,
        mock_scan_installed,
        mock_local_dir,
        mock_global_dir,
        mock_fetch,
        mock_repos,
        mock_agents,
        make_record,
        tmp_path,
        capsys,
    ):
        mock_global_dir.return_value = tmp_path
        mock_local_dir.return_value = tmp_path
        mock_repo_records.return_value = [
            make_record(name="shared-skill", version_str="2.0.0"),
            make_record(name="shared-skill", version_str="2.1.0-SNAPSHOT"),
        ]
        mock_scan_installed.side_effect = [
            [make_record(name="shared-skill", version_str="1.0.0")],  # global ClaudeCode
            [make_record(name="shared-skill", version_str="1.0.0")],  # local ClaudeCode
            [make_record(name="shared-skill", version_str="1.0.0")],  # global Kiro
            [make_record(name="shared-skill", version_str="2.0.0")],  # local Kiro
        ]

        result = main(["list", "--json"])
        assert result == 0

        import json

        out = json.loads(capsys.readouterr().out)
        assert out["shared-skill"]["latest"] == "2.0.0"
        assert out["shared-skill"]["partial"]["local"] is True
        assert out["shared-skill"]["partial"]["global"] is False
        assert out["shared-skill"]["local"].endswith("*")


# ===================================================================
# sync routing
# ===================================================================


class TestSyncRouting:
    @patch("aom.cli._cmd_sync_agents", return_value=7)
    def test_sync_agents_mode(self, mock_sync_agents):
        result = main(["sync", "agents"])
        assert result == 7
        mock_sync_agents.assert_called_once()

    @patch("aom.cli._cmd_sync_requirements", return_value=5)
    def test_sync_clean_mode(self, mock_sync_requirements):
        result = main(["sync", "clean"])
        assert result == 5
        _, kwargs = mock_sync_requirements.call_args
        assert kwargs["clean"] is True

    @patch("aom.cli._cmd_sync_requirements", return_value=3)
    def test_sync_default_mode(self, mock_sync_requirements):
        result = main(["sync"])
        assert result == 3
        _, kwargs = mock_sync_requirements.call_args
        assert kwargs["clean"] is False


# ===================================================================
# env command
# ===================================================================


class TestCmdEnv:
    @patch("aom.config.get_agent", return_value="ClaudeCode")
    @patch("aom.settings.get_settings_path", return_value=Path("/tmp/settings.json"))
    @patch("aom.cli.get_repo_urls", return_value=[])
    @patch("aom.cli.get_local_paths", return_value=[])
    def test_check_fails_when_no_repository_configured(
        self, mock_local_paths, mock_repo_urls, mock_settings_path, mock_agent
    ):
        result = main(["env", "--check"])
        assert result == 1

    @patch("aom.config.get_agent", return_value="ClaudeCode")
    @patch("aom.settings.get_settings_path", return_value=Path("/tmp/settings.json"))
    @patch("aom.cli.get_fetch_ttl", return_value=60)
    @patch("time.time", return_value=120)
    @patch("aom.cli.get_global_dir", return_value=Path("/tmp/global"))
    @patch("aom.cli.get_local_dir", return_value=Path("/tmp/local"))
    @patch("aom.cli.GitRepo")
    def test_prints_repository_and_local_path_status(
        self,
        mock_repo_cls,
        mock_local_dir,
        mock_global_dir,
        mock_time,
        mock_ttl,
        mock_settings_path,
        mock_agent,
        tmp_path,
        capsys,
    ):
        missing = tmp_path / "missing"
        with (
            patch(
                "aom.cli.get_repo_urls",
                return_value=["ssh://cloned/repo.git", "ssh://new/repo.git"],
            ),
            patch("aom.cli.get_local_paths", return_value=[str(tmp_path), str(missing)]),
        ):
            repo_cloned = mock_repo_cls.return_value
            repo_cloned.is_cloned = True
            repo_cloned.cache_dir = Path("/tmp/cache/repo")
            repo_cloned.list_skill_tags.return_value = [("skills", "x", "1.0.0")]
            repo_cloned._load_last_fetched.return_value = 0

            # Build distinct mock for second repo to exercise "not yet cloned" path
            repo_new = type(
                "Repo",
                (),
                {
                    "is_cloned": False,
                    "cache_dir": Path("/tmp/cache/new"),
                    "list_skill_tags": lambda self: [],
                    "_load_last_fetched": lambda self: None,
                },
            )()
            mock_repo_cls.side_effect = [repo_cloned, repo_new]

            result = main(["env"])

        assert result == 0
        out = capsys.readouterr().out
        assert "Skills Repositories (remote)" in out
        assert "tagged versions" in out
        assert "last fetched" in out
        assert "not yet cloned" in out
        assert "Skills Repositories (local paths)" in out
        assert "path missing" in out


# ===================================================================
# main error handling
# ===================================================================


class TestMainErrorHandling:
    @patch("aom.cli.cmd_list", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_returns_130(self, mock_cmd, capsys):
        result = main(["list"])
        assert result == 130
        assert "Aborted." in capsys.readouterr().err

    @patch("aom.cli.cmd_list", side_effect=RuntimeError("boom"))
    def test_runtime_error_returns_1(self, mock_cmd, capsys):
        result = main(["list"])
        assert result == 1
        assert "Error: boom" in capsys.readouterr().err

    @patch("traceback.print_exc")
    @patch("aom.cli.cmd_list", side_effect=RuntimeError("boom"))
    def test_runtime_error_with_debug_prints_traceback(self, mock_cmd, mock_print_exc):
        result = main(["--debug", "list"])
        assert result == 1
        mock_print_exc.assert_called_once()


# ===================================================================
# _guess_type
# ===================================================================


class TestGuessType:
    def test_uses_repo_records_first(self, make_record):
        records = [
            make_record(name="nested/build-docs", artifact_type="commands", version_str="1.0.0")
        ]
        artifact_type = _guess_type("build-docs", git_repos=[], repo_records=records)
        assert artifact_type == "commands"

    @patch("aom.cli.get_local_paths")
    def test_fallback_scans_local_paths(self, mock_local_paths, tmp_path):
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "build-docs.md").write_text("# docs", encoding="utf-8")
        mock_local_paths.return_value = [str(tmp_path)]

        artifact_type = _guess_type("build-docs", git_repos=[], repo_records=[])
        assert artifact_type == "commands"

    @patch("aom.cli.get_local_paths", return_value=[])
    def test_defaults_to_skills(self, mock_local_paths):
        artifact_type = _guess_type("unknown-item", git_repos=[], repo_records=[])
        assert artifact_type == "skills"


# ===================================================================
# sync requirements (risk paths)
# ===================================================================


class TestCmdSyncRequirements:
    @patch("aom.cli._active_agents", return_value=["ClaudeCode"])
    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli._fetch_if_requested")
    @patch("aom.cli._get_repo_records", return_value=[])
    @patch("aom.cli.get_config_file", return_value="CLAUDE.md")
    @patch("aom.cli.parse_manifest", return_value=[])
    def test_no_requirements_non_clean(
        self,
        mock_manifest,
        mock_cfg,
        mock_records,
        mock_fetch,
        mock_repos,
        mock_agents,
        tmp_path,
        capsys,
    ):
        args = build_parser().parse_args(["sync", "--project-dir", str(tmp_path)])
        result = _cmd_sync_requirements(args, clean=False)
        assert result == 0
        out = capsys.readouterr().out
        assert "No skills requirements found" in out

    @patch("aom.cli._active_agents", return_value=["ClaudeCode"])
    @patch("aom.cli._get_git_repos", return_value=["repo"])
    @patch("aom.cli._fetch_if_requested")
    @patch("aom.cli._get_repo_records", return_value=[])
    @patch("aom.cli.get_config_file", return_value="CLAUDE.md")
    @patch("aom.cli.parse_manifest")
    @patch("aom.cli.get_global_dir", return_value=Path("/nonexistent"))
    @patch("aom.cli.ensure_local_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli.get_local_registry")
    @patch("aom.cli.resolve_all")
    @patch("aom.cli.uninstall")
    def test_clean_skips_on_resolution_errors(
        self,
        mock_uninstall,
        mock_resolve_all,
        mock_local_registry,
        mock_local_dir,
        mock_ensure_local,
        mock_global_dir,
        mock_manifest,
        mock_cfg,
        mock_records,
        mock_fetch,
        mock_repos,
        mock_agents,
        make_record,
        tmp_path,
        capsys,
    ):
        req = type("Req", (), {"name": "missing-skill", "constraint": "latest"})()
        mock_manifest.return_value = [req]
        local_dir = tmp_path / ".Codex"
        local_dir.mkdir()
        mock_local_dir.return_value = local_dir
        mock_local_registry.return_value = tmp_path / "registry.json"
        mock_resolve_all.return_value = {"missing-skill": None}

        args = build_parser().parse_args(["sync", "clean", "--project-dir", str(tmp_path)])
        result = _cmd_sync_requirements(args, clean=True)

        assert result == 1
        out = capsys.readouterr().out
        assert "not found" in out
        assert "--fetch" in out
        assert "Skipping clean for ClaudeCode" in out
        mock_uninstall.assert_not_called()

    @patch("aom.cli._active_agents", return_value=["ClaudeCode"])
    @patch("aom.cli._get_git_repos", return_value=[])
    @patch("aom.cli._fetch_if_requested")
    @patch("aom.cli._get_repo_records", return_value=[])
    @patch("aom.cli.get_config_file", return_value="CLAUDE.md")
    @patch("aom.cli.parse_manifest")
    @patch("aom.cli.get_global_dir", return_value=Path("/nonexistent"))
    @patch("aom.cli.ensure_local_dir")
    @patch("aom.cli.get_local_dir")
    @patch("aom.cli.get_local_registry")
    @patch("aom.cli.resolve_all")
    @patch("aom.cli.install")
    @patch("aom.cli._find_git_repo_for_record", return_value=None)
    @patch("aom.cli.Registry")
    def test_installs_and_cleans_extras(
        self,
        mock_registry_cls,
        mock_find_repo,
        mock_install,
        mock_resolve_all,
        mock_local_registry,
        mock_local_dir,
        mock_ensure_local,
        mock_global_dir,
        mock_manifest,
        mock_cfg,
        mock_records,
        mock_fetch,
        mock_repos,
        mock_agents,
        make_record,
        tmp_path,
        capsys,
    ):
        req = type("Req", (), {"name": "keep-skill", "constraint": "latest"})()
        mock_manifest.return_value = [req]
        record = make_record(name="keep-skill", artifact_type="skills", version_str="1.2.3")
        mock_resolve_all.return_value = {"keep-skill": record}

        local_dir = tmp_path / ".Codex"
        local_dir.mkdir()
        mock_local_dir.return_value = local_dir
        mock_local_registry.return_value = tmp_path / "registry.json"
        mock_install.return_value = local_dir / "skills" / "keep-skill.md"

        registry_obj = mock_registry_cls.return_value
        registry_obj.get_version.return_value = "0.9.0"
        registry_obj.all_installed.return_value = {
            "skills/keep-skill": "1.2.3",
            "commands/old-cmd": "1.0.0",
            "garbage": "x",
        }

        args = build_parser().parse_args(["sync", "clean", "--project-dir", str(tmp_path)])
        with patch("aom.cli.uninstall", return_value=True) as mock_uninstall:
            result = _cmd_sync_requirements(args, clean=True)

        assert result == 0
        out = capsys.readouterr().out
        assert "Sync clean complete" in out
        assert "Removed commands/old-cmd" in out
        mock_install.assert_called_once()
        mock_uninstall.assert_called_once()


# ===================================================================
# init and prompt helpers
# ===================================================================


class TestCmdInit:
    @patch("aom.settings.get_settings_path", return_value=Path("/tmp/settings.json"))
    @patch("aom.cli.detect_supported_agents", return_value=[])
    @patch("aom.cli._prompt_agent_selection", return_value=["ClaudeCode"])
    @patch("aom.cli.write_selected_agents")
    @patch("aom.cli.get_global_repo_urls", return_value=[])
    @patch("aom.cli._prompt_repo_urls", return_value=["ssh://repo-1.git"])
    @patch("aom.cli.set_global_repo_urls")
    @patch("aom.cli.get_global_local_paths", return_value=[])
    @patch("aom.cli.set_global_local_paths")
    @patch("aom.cli.parse_repo_url", return_value=None)
    @patch("aom.cli.write_repo_url")
    def test_init_no_detected_agents_skips_fetch_and_local_paths(
        self,
        mock_write_repo_url,
        mock_parse_repo_url,
        mock_set_local_paths,
        mock_get_local_paths,
        mock_set_repo_urls,
        mock_prompt_urls,
        mock_get_urls,
        mock_write_selected,
        mock_prompt_agents,
        mock_detect,
        mock_settings_path,
        tmp_path,
    ):
        args = build_parser().parse_args(["init", "--project-dir", str(tmp_path)])
        with patch("builtins.input", side_effect=["n", "n"]):
            result = cmd_init(args)

        assert result == 0
        mock_write_selected.assert_called_once()
        mock_set_repo_urls.assert_called_once_with(["ssh://repo-1.git"])
        mock_set_local_paths.assert_not_called()
        mock_write_repo_url.assert_called_once()

    @patch("aom.settings.get_settings_path", return_value=Path("/tmp/settings.json"))
    @patch("aom.cli.detect_supported_agents", return_value=["ClaudeCode"])
    @patch("aom.cli._prompt_agent_selection", return_value=["Kiro"])
    @patch("aom.cli.write_selected_agents")
    @patch("aom.cli.get_global_repo_urls", return_value=["ssh://old.git"])
    @patch("aom.cli._prompt_repo_urls", return_value=["ssh://new.git", "ssh://bad.git"])
    @patch("aom.cli.set_global_repo_urls")
    @patch("aom.cli.get_global_local_paths", return_value=["/does/not/exist"])
    @patch("aom.cli._prompt_local_paths")
    @patch("aom.cli.set_global_local_paths")
    @patch("aom.cli.parse_repo_url", return_value=None)
    @patch("aom.cli.write_repo_url")
    @patch("aom.cli.scan_repository", return_value=[object(), object()])
    @patch("aom.cli.GitRepo")
    def test_init_changes_repo_and_local_paths_and_fetches(
        self,
        mock_gitrepo_cls,
        mock_scan_repo,
        mock_write_repo_url,
        mock_parse_repo_url,
        mock_set_local_paths,
        mock_prompt_local_paths,
        mock_get_local_paths,
        mock_set_repo_urls,
        mock_prompt_urls,
        mock_get_urls,
        mock_write_selected,
        mock_prompt_agents,
        mock_detect,
        mock_settings_path,
        tmp_path,
    ):
        existing_local = tmp_path / "local-skills"
        existing_local.mkdir()
        missing_local = tmp_path / "missing-skills"
        mock_prompt_local_paths.return_value = [str(existing_local), str(missing_local)]

        repo_ok = mock_gitrepo_cls.return_value
        repo_ok.fetch.return_value = None
        repo_ok.list_skill_tags.return_value = [("skills", "x", "1.0.0")]

        repo_fail = type("RepoFail", (), {})()
        repo_fail.fetch = lambda verbose=True: (_ for _ in ()).throw(RuntimeError("network"))
        repo_fail.list_skill_tags = lambda: []
        mock_gitrepo_cls.side_effect = [repo_ok, repo_fail]

        args = build_parser().parse_args(["init", "--project-dir", str(tmp_path)])
        # use this agent? n -> choose other; change repos y; change local y; fetch now Enter
        with patch("builtins.input", side_effect=["n", "y", "y", ""]):
            result = cmd_init(args)

        assert result == 0
        mock_prompt_agents.assert_called_once()
        mock_set_repo_urls.assert_called_once_with(["ssh://new.git", "ssh://bad.git"])
        mock_set_local_paths.assert_called_once_with([str(existing_local), str(missing_local)])
        assert mock_gitrepo_cls.call_count == 2
        mock_scan_repo.assert_called_once_with(existing_local)
        mock_write_repo_url.assert_called_once()


class TestPromptHelpers:
    def test_prompt_agent_selection_retries_then_accepts_index(self, capsys):
        with patch("builtins.input", side_effect=["?", "2"]):
            selected = _prompt_agent_selection(["ClaudeCode", "Kiro"], prompt_label="agent")
        assert selected == ["Kiro"]
        assert "Invalid selection." in capsys.readouterr().err

    def test_prompt_repo_urls_rejects_then_accepts(self, capsys):
        # empty -> invalid URL + no -> valid URL
        with patch(
            "builtins.input", side_effect=["", "not-a-url", "n", "https://example.com/repo.git"]
        ):
            urls = _prompt_repo_urls()
        assert urls == ["https://example.com/repo.git"]
        err = capsys.readouterr().err
        assert "At least one URL is required." in err

    def test_prompt_local_paths_rejects_missing_then_accepts_existing(self, tmp_path, capsys):
        existing = tmp_path / "skills"
        existing.mkdir()
        # empty -> missing + no -> existing
        with patch(
            "builtins.input", side_effect=["", str(tmp_path / "missing"), "n", str(existing)]
        ):
            paths = _prompt_local_paths()
        assert paths == [str(existing.resolve())]
        assert "At least one path is required." in capsys.readouterr().err
