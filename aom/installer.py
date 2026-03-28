"""
Installer — copy skill files from the repository to a target install directory
and update the corresponding registry.

Install layout mirrors the source:
  ~/.ai-skills/skills/complex-evaluator/    (module)
  ~/.ai-skills/commands/deploy-skills.md    (flat file)

Uninstall removes the copied files and the registry entry.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config import get_type_subdir
from .models import SkillRecord
from .registry import Registry

if TYPE_CHECKING:
    from .git import GitRepo


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install(
    record: SkillRecord,
    install_dir: Path,
    registry: Registry,
    overwrite: bool = True,
    git_repo: GitRepo | None = None,
) -> Path:
    """
    Install *record* into *install_dir*/<artifact_type>/ and update *registry*.

    For git-backed records (``record.git_tag`` is set), files are extracted
    from the local git clone via *git_repo*.  For local records, files are
    copied from ``record.path``.

    Returns the destination path.
    """
    if record.git_tag and git_repo is not None:
        dest = _install_from_git(record, install_dir, git_repo, overwrite)
    else:
        if record.path is None:
            raise RuntimeError(
                f"Cannot install {record.name}: no local path and no git_repo provided."
            )
        dest = _destination(record, install_dir)
        if dest.exists() and not overwrite:
            return dest
        _copy(record.path, dest)

    registry.set_version(
        full_name=record.full_name,
        version=record.version.raw if record.version else "unknown",
    )
    return dest


def _install_from_git(
    record: SkillRecord,
    install_dir: Path,
    git_repo: GitRepo,
    overwrite: bool,
) -> Path:
    """Extract a git-backed skill from the local clone into *install_dir*."""
    type_dir = install_dir / get_type_subdir(record.artifact_type)
    tag = record.git_tag

    # Try directory layout first (e.g. skills/create-jira-story/)
    src_dir = f"{record.artifact_type}/{record.name}"
    obj_type = git_repo.get_object_type(tag, src_dir)

    if obj_type == "tree":
        dest = type_dir / record.name
        if dest.exists() and not overwrite:
            return dest
        if dest.exists():
            shutil.rmtree(dest)
        git_repo.extract_path_at_tag(tag, src_dir, dest)
        return dest

    # Fall back to flat file (e.g. skills/create-jira-story.md)
    src_flat = f"{record.artifact_type}/{record.name}.md"
    dest = type_dir / f"{record.name}.md"
    if dest.exists() and not overwrite:
        return dest
    content = git_repo.read_file_at_tag(tag, src_flat)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def uninstall(
    artifact_type: str,
    name: str,
    install_dir: Path,
    registry: Registry,
) -> bool:
    """
    Remove a skill from *install_dir* and from *registry*.

    Returns True if anything was removed.
    """
    full_name = f"{artifact_type}/{name}"
    # Resolve the agent-specific subdir (e.g. "skills" → "commands" for ClaudeCode)
    type_dir = install_dir / get_type_subdir(artifact_type)

    removed = False

    # Module directory
    module_path = type_dir / name
    if module_path.is_dir():
        try:
            shutil.rmtree(module_path)
            removed = True
        except PermissionError as e:
            print(f"Warning: could not fully remove {module_path}: {e}", file=sys.stderr)

    # Flat file
    flat_path = type_dir / f"{name}.md"
    if flat_path.is_file():
        flat_path.unlink(missing_ok=True)
        removed = True

    if removed:
        registry.remove(full_name)

    return removed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _destination(record: SkillRecord, install_dir: Path) -> Path:
    """Compute the destination path for *record* inside *install_dir*.

    The subdirectory name is agent-specific (e.g. ClaudeCode maps
    "skills" → "commands", so a skill lands in install_dir/commands/).
    """
    if record.path is None:
        raise RuntimeError(
            f"Cannot compute destination for {record.name}: no local path"
        )
    type_dir = install_dir / get_type_subdir(record.artifact_type)

    if record.path.is_dir():
        # Module layout: keep the directory structure
        return type_dir / record.name
    else:
        # Flat file: place .md at type_dir/name.md
        # (name may contain slashes for nested: "child/page-painter")
        name_path = Path(record.name)
        if len(name_path.parts) > 1:
            parent = type_dir.joinpath(*name_path.parts[:-1])
            parent.mkdir(parents=True, exist_ok=True)
            return parent / (name_path.name + record.path.suffix)
        return type_dir / (record.name + record.path.suffix)


def _copy(source: Path, dest: Path) -> None:
    """Copy *source* (file or directory tree) to *dest*."""
    if source.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
