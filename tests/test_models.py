"""Tests for aom.models — Version, SkillRecord, VersionRequirement."""
from __future__ import annotations

import warnings

from aom.models import VersionRequirement, SkillRecord, parse_version


# ===================================================================
# parse_version
# ===================================================================

class TestParseVersion:
    def test_basic_semver(self):
        v = parse_version("1.2.3")
        assert v is not None
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None
        assert v.raw == "1.2.3"

    def test_prerelease(self):
        v = parse_version("1.0.0-alpha.1")
        assert v is not None
        assert v.prerelease == "alpha.1"

    def test_snapshot(self):
        v = parse_version("2.0.0-SNAPSHOT")
        assert v is not None
        assert v.is_snapshot is True
        assert v.is_stable is False

    def test_stable(self):
        v = parse_version("1.0.0")
        assert v.is_stable is True
        assert v.is_snapshot is False

    def test_empty_string(self):
        assert parse_version("") is None

    def test_none_like(self):
        assert parse_version("  ") is None

    def test_invalid_format(self):
        assert parse_version("not-a-version") is None
        assert parse_version("1.2") is None
        assert parse_version("v1.2.3") is None  # no 'v' prefix support

    def test_whitespace_stripped(self):
        v = parse_version("  1.0.0  ")
        assert v is not None
        assert v.raw == "1.0.0"

    def test_zero_version(self):
        v = parse_version("0.0.0")
        assert v is not None
        assert v.major == 0


# ===================================================================
# Version comparison
# ===================================================================

class TestVersionComparison:
    def test_equal(self):
        assert parse_version("1.0.0") == parse_version("1.0.0")

    def test_not_equal(self):
        assert parse_version("1.0.0") != parse_version("1.0.1")

    def test_less_than(self):
        assert parse_version("1.0.0") < parse_version("1.0.1")
        assert parse_version("1.0.0") < parse_version("1.1.0")
        assert parse_version("1.0.0") < parse_version("2.0.0")

    def test_greater_than(self):
        assert parse_version("2.0.0") > parse_version("1.9.9")

    def test_stable_greater_than_prerelease(self):
        """Stable 1.0.0 should sort after 1.0.0-alpha."""
        stable = parse_version("1.0.0")
        pre = parse_version("1.0.0-alpha")
        assert stable > pre

    def test_le_ge(self):
        v1 = parse_version("1.0.0")
        v2 = parse_version("1.0.0")
        assert v1 <= v2
        assert v1 >= v2

    def test_hash_equal(self):
        v1 = parse_version("1.0.0")
        v2 = parse_version("1.0.0")
        assert hash(v1) == hash(v2)
        assert {v1} == {v2}

    def test_eq_non_version(self):
        v = parse_version("1.0.0")
        assert v != "1.0.0"
        assert v != 42

    def test_as_tuple(self):
        v = parse_version("3.2.1")
        assert v.as_tuple() == (3, 2, 1)


# ===================================================================
# Version __str__ / __repr__
# ===================================================================

class TestVersionRepr:
    def test_str(self):
        v = parse_version("1.2.3")
        assert str(v) == "1.2.3"

    def test_repr(self):
        v = parse_version("1.2.3")
        assert repr(v) == "Version('1.2.3')"


# ===================================================================
# SkillRecord
# ===================================================================

class TestSkillRecord:
    def test_full_name(self):
        r = SkillRecord(name="my-skill", artifact_type="skills", path=None,
                        version=parse_version("1.0.0"), structure="metadata")
        assert r.full_name == "skills/my-skill"

    def test_display_name(self):
        r = SkillRecord(name="my-skill", artifact_type="skills", path=None,
                        version=parse_version("2.1.0"), structure="metadata")
        assert r.display_name == "my-skill@2.1.0"

    def test_display_name_no_version(self):
        r = SkillRecord(name="my-skill", artifact_type="skills", path=None,
                        version=None, structure="metadata")
        assert r.display_name == "my-skill@unknown"

    def test_repr(self):
        r = SkillRecord(name="x", artifact_type="skills", path=None,
                        version=parse_version("1.0.0"), structure="metadata")
        assert "SkillRecord" in repr(r)
        assert "x" in repr(r)


# ===================================================================
# VersionRequirement
# ===================================================================

class TestVersionRequirement:
    def test_is_latest(self):
        assert VersionRequirement("x", "latest").is_latest()
        assert VersionRequirement("x", "*").is_latest()
        assert VersionRequirement("x", "").is_latest()
        assert not VersionRequirement("x", "1.0.0").is_latest()

    def test_is_exact(self):
        assert VersionRequirement("x", "1.0.0").is_exact()
        assert not VersionRequirement("x", ">=1.0.0").is_exact()
        assert not VersionRequirement("x", "latest").is_exact()

    def test_is_minimum(self):
        assert VersionRequirement("x", ">=1.0.0").is_minimum()
        assert not VersionRequirement("x", "1.0.0").is_minimum()

    def test_get_minimum_version(self):
        req = VersionRequirement("x", ">=1.2.0")
        v = req.get_minimum_version()
        assert v is not None
        assert v == parse_version("1.2.0")

    def test_get_minimum_version_from_exact(self):
        req = VersionRequirement("x", "1.2.0")
        v = req.get_minimum_version()
        assert v == parse_version("1.2.0")

    def test_get_minimum_version_latest(self):
        assert VersionRequirement("x", "latest").get_minimum_version() is None

    def test_get_exact_version(self):
        req = VersionRequirement("x", "1.0.0")
        assert req.get_exact_version() == parse_version("1.0.0")

    def test_get_exact_version_not_exact(self):
        assert VersionRequirement("x", ">=1.0.0").get_exact_version() is None

    # --- matches() ---

    def test_matches_latest(self):
        req = VersionRequirement("x", "latest")
        assert req.matches(parse_version("1.0.0"))
        assert req.matches(parse_version("99.0.0"))

    def test_matches_exact(self):
        req = VersionRequirement("x", "1.0.0")
        assert req.matches(parse_version("1.0.0"))
        assert not req.matches(parse_version("1.0.1"))

    def test_matches_minimum(self):
        req = VersionRequirement("x", ">=1.2.0")
        assert req.matches(parse_version("1.2.0"))
        assert req.matches(parse_version("2.0.0"))
        assert not req.matches(parse_version("1.1.9"))

    def test_matches_unsupported_constraint(self):
        req = VersionRequirement("x", "~1.0.0")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = req.matches(parse_version("1.0.0"))
            assert result is False
            assert len(w) == 1
            assert "Unsupported" in str(w[0].message)

    def test_repr(self):
        req = VersionRequirement("x", "1.0.0")
        assert "VersionRequirement" in repr(req)
