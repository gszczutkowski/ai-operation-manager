"""Tests for aom.resolver — version resolution logic."""
from __future__ import annotations

from aom.models import VersionRequirement, parse_version
from aom.resolver import resolve, resolve_latest, resolve_all, latest_available


class TestResolve:
    def test_exact_match_from_repo(self, make_record):
        req = VersionRequirement("my-skill", "1.0.0")
        repo = [make_record(name="my-skill", version_str="1.0.0")]
        result = resolve(req, repo, [], [])
        assert result is not None
        assert result.version == parse_version("1.0.0")

    def test_latest_picks_highest(self, make_record):
        req = VersionRequirement("x", "latest")
        repo = [
            make_record(name="x", version_str="1.0.0"),
            make_record(name="x", version_str="2.0.0"),
            make_record(name="x", version_str="1.5.0"),
        ]
        result = resolve(req, repo, [], [])
        assert result.version == parse_version("2.0.0")

    def test_minimum_picks_highest_satisfying(self, make_record):
        req = VersionRequirement("x", ">=1.5.0")
        repo = [
            make_record(name="x", version_str="1.0.0"),
            make_record(name="x", version_str="1.5.0"),
            make_record(name="x", version_str="2.0.0"),
        ]
        result = resolve(req, repo, [], [])
        assert result.version == parse_version("2.0.0")

    def test_no_match(self, make_record):
        req = VersionRequirement("x", "99.0.0")
        repo = [make_record(name="x", version_str="1.0.0")]
        assert resolve(req, repo, [], []) is None

    def test_local_preferred_over_global(self, make_record):
        req = VersionRequirement("x", "latest")
        local = [make_record(name="x", version_str="1.0.0")]
        global_ = [make_record(name="x", version_str="2.0.0")]
        repo = [make_record(name="x", version_str="3.0.0")]
        result = resolve(req, repo, global_, local)
        # Local is checked first — should pick the local version
        assert result.version == parse_version("1.0.0")

    def test_global_preferred_over_repo(self, make_record):
        req = VersionRequirement("x", "latest")
        global_ = [make_record(name="x", version_str="2.0.0")]
        repo = [make_record(name="x", version_str="3.0.0")]
        result = resolve(req, repo, global_, [])
        assert result.version == parse_version("2.0.0")

    def test_case_insensitive_name(self, make_record):
        req = VersionRequirement("My-Skill", "latest")
        repo = [make_record(name="my-skill", version_str="1.0.0")]
        result = resolve(req, repo, [], [])
        assert result is not None

    def test_not_found_returns_none(self, make_record):
        req = VersionRequirement("nonexistent", "latest")
        assert resolve(req, [], [], []) is None


class TestResolveLatest:
    def test_stable_only(self, make_record):
        records = [
            make_record(name="x", version_str="1.0.0"),
            make_record(name="x", version_str="2.0.0-SNAPSHOT"),
        ]
        r = resolve_latest("x", records, stable_only=True)
        assert r.version == parse_version("1.0.0")

    def test_include_prerelease(self, make_record):
        records = [
            make_record(name="x", version_str="1.0.0"),
            make_record(name="x", version_str="2.0.0-SNAPSHOT"),
        ]
        r = resolve_latest("x", records, stable_only=False)
        assert r.version == parse_version("2.0.0-SNAPSHOT")

    def test_no_records(self):
        assert resolve_latest("x", []) is None


class TestResolveAll:
    def test_batch(self, make_record):
        reqs = [
            VersionRequirement("a", "1.0.0"),
            VersionRequirement("b", "latest"),
        ]
        repo = [
            make_record(name="a", version_str="1.0.0"),
            make_record(name="b", version_str="2.0.0"),
        ]
        results = resolve_all(reqs, repo, [], [])
        assert results["a"] is not None
        assert results["b"] is not None
        assert results["b"].version == parse_version("2.0.0")

    def test_missing_in_batch(self, make_record):
        reqs = [VersionRequirement("missing", "1.0.0")]
        results = resolve_all(reqs, [], [], [])
        assert results["missing"] is None


class TestLatestAvailable:
    def test_returns_version(self, make_record):
        records = [
            make_record(name="x", version_str="1.0.0"),
            make_record(name="x", version_str="2.0.0"),
        ]
        v = latest_available(records, "x")
        assert v == parse_version("2.0.0")

    def test_returns_none(self):
        assert latest_available([], "x") is None
