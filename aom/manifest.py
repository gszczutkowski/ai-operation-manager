"""
CLAUDE.md manifest parser.

Reads the "Skills Requirements" section from CLAUDE.md (or any Markdown file)
and returns a list of VersionRequirement objects.

Expected CLAUDE.md format (anywhere in the file):

  ## Skills Requirements

  ```yaml
  required:
    complex-evaluator: "1.0.0"
    child/page-painter: ">=1.2.0"
    create-jira-story: "latest"
  ```

The section header is case-insensitive and the YAML block may use either
backtick fences (```) or indented YAML (4+ spaces).  The parser is intentionally
lenient — it does not require a full YAML library.
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import VersionRequirement

# Matches the "## Skills Requirements" header (flexible spacing/capitalisation)
_HEADER_RE = re.compile(
    r"^#{1,6}\s*skills\s+requirements?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches the "## Skills Source" header
_SOURCE_HEADER_RE = re.compile(
    r"^#{1,6}\s*skills?\s+source\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches a fenced YAML block: ```yaml ... ``` or ``` ... ```
_FENCE_RE = re.compile(
    r"```(?:yaml)?\s*\n(.*?)```",
    re.DOTALL,
)

# One requirement line:  name: "constraint"  or  name: constraint
_REQ_LINE_RE = re.compile(
    r"^\s{2,}([A-Za-z0-9_\-/]+)\s*:\s*[\"']?([^\"'\n]+)[\"']?\s*$"
)


def parse_manifest(path: Path) -> list[VersionRequirement]:
    """
    Parse *path* (typically CLAUDE.md) and return all skill version requirements.
    Returns an empty list if the section is absent or the file does not exist.
    """
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    section = _extract_section(text)
    if section is None:
        return []

    return _parse_requirements(section)


def write_manifest(
    path: Path,
    requirements: list[VersionRequirement],
) -> None:
    """
    Upsert the Skills Requirements section in *path*.

    Creates the file if absent, appends the section if not present,
    or replaces the YAML block if the section already exists.
    """
    yaml_lines = ["required:"]
    for req in requirements:
        yaml_lines.append(f'  {req.name}: "{req.constraint}"')
    yaml_block = "\n".join(yaml_lines)

    section_text = f"\n## Skills Requirements\n\n```yaml\n{yaml_block}\n```\n"
    _upsert_fenced_section(path, _HEADER_RE, section_text)


# ---------------------------------------------------------------------------
# Skills Source — repository URL
# ---------------------------------------------------------------------------

_URL_LINE_RE = re.compile(r'^\s*url\s*:\s*["\']?([^\s"\'#]+)["\']?\s*$')


def parse_repo_url(path: Path) -> str | None:
    """
    Read the skills repository URL from the ``## Skills Source`` section of
    *path*.  Returns None if the section or URL key is absent.
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _SOURCE_HEADER_RE.search(text)
    if m is None:
        return None
    after = text[m.end():]
    next_header = re.search(r"^#{1,6}\s", after, re.MULTILINE)
    bounded = after[:next_header.start()] if next_header else after
    fence_m = _FENCE_RE.search(bounded)
    if fence_m:
        for line in fence_m.group(1).splitlines():
            lm = _URL_LINE_RE.match(line)
            if lm:
                return lm.group(1)
    return None


def write_repo_url(path: Path, url: str) -> None:
    """
    Upsert the ``## Skills Source`` section in *path* with the given *url*.

    Creates the file if absent, appends the section if not present,
    or replaces the YAML block if the section already exists.
    """
    section_text = f"\n## Skills Source\n\n```yaml\nurl: \"{url}\"\n```\n"
    _upsert_fenced_section(path, _SOURCE_HEADER_RE, section_text)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _upsert_fenced_section(
    path: Path, header_re: re.Pattern[str], section_text: str,
) -> None:
    """Shared upsert logic for fenced YAML sections in Markdown files."""
    if not path.is_file():
        path.write_text(section_text.lstrip(), encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8", errors="replace")
    m = header_re.search(text)

    if m is None:
        with path.open("a", encoding="utf-8") as f:
            f.write(section_text)
        return

    header_start = m.start()
    next_header = re.search(r"^#{1,6}\s", text[m.end():], re.MULTILINE)
    search_end = m.end() + next_header.start() if next_header else len(text)
    fence_m = _FENCE_RE.search(text, header_start, search_end)
    if fence_m:
        end = fence_m.end()
        new_text = text[:header_start] + section_text.lstrip() + text[end:]
    else:
        new_text = text[:header_start] + section_text.lstrip() + text[search_end:]

    path.write_text(new_text, encoding="utf-8")


def _extract_section(text: str) -> str | None:
    """Return the text of the YAML block following the Skills Requirements header."""
    m = _HEADER_RE.search(text)
    if m is None:
        return None

    after_header = text[m.end():]
    # Bound search to region before the next ## header
    next_header = re.search(r"^#{1,6}\s", after_header, re.MULTILINE)
    bounded = after_header[:next_header.start()] if next_header else after_header
    fence_m = _FENCE_RE.search(bounded)
    if fence_m:
        return fence_m.group(1)

    # Fallback: collect indented lines after the header
    lines = bounded.splitlines()
    indented = []
    for line in lines:
        if line.startswith("    ") or line.startswith("\t"):
            indented.append(line)
        elif line.strip() == "":
            continue
        else:
            break
    return "\n".join(indented) if indented else None


def _parse_requirements(yaml_text: str) -> list[VersionRequirement]:
    """Extract requirement lines from a YAML block string."""
    reqs: list[VersionRequirement] = []
    in_required = False

    for line in yaml_text.splitlines():
        stripped = line.strip()

        if stripped == "required:":
            in_required = True
            continue

        if in_required and stripped and not stripped.startswith("#"):
            # Stop if we hit a new top-level key (no leading spaces)
            if line and line[0] not in (" ", "\t") and ":" in stripped:
                in_required = False
                continue

            m = _REQ_LINE_RE.match(line)
            if m:
                name, constraint = m.group(1).strip(), m.group(2).strip()
                reqs.append(VersionRequirement(name=name, constraint=constraint))

    return reqs
