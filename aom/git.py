"""
Git-backed remote repository access.

Maintains a local bare clone of the remote skills repository in a per-URL
cache directory. Network access is isolated to explicit ``fetch()`` calls;
``list_skill_tags()`` and file reads operate against the local clone only.

Tag convention (set in the skills repository):
  skills/create-jira-story@1.0.0
  commands/deploy-skills@2.0.0
  agents/my-agent@1.0.0

Requirements:
  - git must be available on PATH
  - SSH key / agent must be configured for the remote host (for SSH URLs)

Cache location:
  Linux/macOS: ~/.cache/ai-operation-manager/<url-hash>/
  Windows:     %LOCALAPPDATA%/ai-operation-manager/<url-hash>/
"""
from __future__ import annotations

import hashlib
import io
import os
import platform
import re
import subprocess
import tarfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Tag pattern  (short form, without refs/tags/ prefix)
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(
    r"^(skills|commands|agents|hooks)/([A-Za-z0-9_\-./]+)@(\d+\.\d+\.\d+[^\s]*)$"
)


# ---------------------------------------------------------------------------
# Cache location helpers
# ---------------------------------------------------------------------------

def _cache_base() -> Path:
    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        base = Path(local_app) if local_app else Path.home() / "AppData" / "Local"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "ai-operation-manager"


def _url_hash(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# GitRepo
# ---------------------------------------------------------------------------

class GitRepo:
    """
    Local bare clone of a remote git repository used as an offline skill index.

    Lifecycle:
      1. ``ensure_cloned()``       — one-time clone (bare, partial, no blobs eagerly)
      2. ``fetch()``               — pull latest refs + tags on demand (requires network)
      3. ``list_skill_tags()``     — list available versions from local refs (no network)
      4. ``extract_path_at_tag()`` — fetch specific blobs lazily when installing

    All methods raise ``RuntimeError`` on git errors.
    """

    def __init__(self, url: str, cache_dir: Path | None = None) -> None:
        self.url = url
        self.cache_dir: Path = cache_dir or (_cache_base() / _url_hash(url))

    # ------------------------------------------------------------------
    # Clone / fetch
    # ------------------------------------------------------------------

    @property
    def is_cloned(self) -> bool:
        return (self.cache_dir / "HEAD").exists()

    def ensure_cloned(self, verbose: bool = True) -> None:
        """Clone the repo (bare, partial) if the local cache does not exist yet."""
        if self.is_cloned:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"  Cloning {self.url} …", flush=True)
        self._run(
            ["git", "clone", "--bare", "--filter=blob:none", self.url, str(self.cache_dir)],
            cwd=None,
            capture=False,
        )

    def fetch(self, verbose: bool = True) -> None:
        """Fetch all refs and tags from the remote (requires network access)."""
        self.ensure_cloned(verbose=verbose)
        if verbose:
            print(f"  Fetching {self.url} …", flush=True)
        self._run(
            ["git", "fetch", "--tags", "--prune", "origin"],
            cwd=self.cache_dir,
            capture=False,
        )

    # ------------------------------------------------------------------
    # Tag listing  (reads local refs — no network)
    # ------------------------------------------------------------------

    def list_skill_tags(self) -> list[tuple[str, str, str]]:
        """
        Return ``(artifact_type, name, version_str)`` for every skill tag
        present in the local clone.  No network access.

        Example result:
          [("skills", "create-jira-story", "1.0.0"),
           ("skills", "create-jira-story", "1.2.0"),
           ("commands", "deploy-skills",   "1.0.0")]
        """
        self.ensure_cloned(verbose=False)
        output = self._run(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/tags/"],
            cwd=self.cache_dir,
            capture=True,
        )
        results: list[tuple[str, str, str]] = []
        for tag in output.splitlines():
            tag = tag.strip()
            m = _TAG_RE.match(tag)
            if m:
                results.append((m.group(1), m.group(2), m.group(3)))
        return results

    # ------------------------------------------------------------------
    # Object introspection
    # ------------------------------------------------------------------

    def get_object_type(self, tag: str, path: str) -> str | None:
        """
        Return the git object type ('tree', 'blob') for *path* at *tag*,
        or None if the path does not exist at that tag.
        """
        try:
            return self._run(
                ["git", "cat-file", "-t", f"{tag}:{path}"],
                cwd=self.cache_dir,
                capture=True,
            ).strip()
        except RuntimeError:
            return None

    # ------------------------------------------------------------------
    # File / tree access  (fetches blobs lazily from remote)
    # ------------------------------------------------------------------

    def read_file_at_tag(self, tag: str, file_path: str) -> str:
        """Return the UTF-8 content of *file_path* at *tag*."""
        self.ensure_cloned(verbose=False)
        return self._run(
            ["git", "show", f"{tag}:{file_path}"],
            cwd=self.cache_dir,
            capture=True,
        )

    def extract_path_at_tag(self, tag: str, src_path: str, dest: Path) -> None:
        """
        Extract *src_path* (file or directory) from *tag* into *dest*.

        - If *src_path* is a blob (file): writes content directly to *dest*.
        - If *src_path* is a tree (directory): uses ``git archive`` + tarfile
          to extract the entire subtree, stripping the *src_path* prefix so
          files land directly under *dest*.
        """
        self.ensure_cloned(verbose=False)

        obj_type = self.get_object_type(tag, src_path)
        if obj_type is None:
            raise RuntimeError(
                f"Path {src_path!r} does not exist at tag {tag!r}. "
                "Run 'aom list --fetch' to refresh the tag index."
            )

        if obj_type == "tree":
            self._extract_tree(tag, src_path, dest)
        else:
            content = self.read_file_at_tag(tag, src_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    def _extract_tree(self, tag: str, src_path: str, dest: Path) -> None:
        """Extract a directory tree via ``git archive`` + Python tarfile."""
        dest.mkdir(parents=True, exist_ok=True)

        raw = self._run_bytes(
            ["git", "archive", tag, f"{src_path}/"],
            cwd=self.cache_dir,
        )

        prefix = src_path.rstrip("/") + "/"
        dest_resolved = dest.resolve()
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            for member in tf.getmembers():
                # Skip symlinks and special file types (security)
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    continue
                if member.name.startswith(prefix):
                    member.name = member.name[len(prefix):]
                if not member.name:
                    continue
                # Guard against path traversal (CVE-2007-4559)
                target = (dest / member.name).resolve()
                try:
                    target.relative_to(dest_resolved)
                except ValueError:
                    raise RuntimeError(f"Path traversal detected in tar entry: {member.name}")
                tf.extract(member, path=dest)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        cmd: list[str],
        cwd: Path | None,
        capture: bool = False,
    ) -> str:
        """
        Run a git command.

        stdout is captured and returned when *capture* is True; otherwise it
        flows to the terminal (so clone/fetch progress is visible).
        stderr is always captured and included in error messages.
        """
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
            return proc.stdout or ""
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise RuntimeError(
                f"git command failed: {' '.join(cmd)}\n{stderr}"
            ) from exc
        except FileNotFoundError:
            raise RuntimeError(
                "git not found on PATH. Please install git and ensure it is accessible."
            )

    def _run_bytes(self, cmd: list[str], cwd: Path | None) -> bytes:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                check=True,
            )
            return proc.stdout
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode(errors="replace").strip()
            raise RuntimeError(
                f"git command failed: {' '.join(cmd)}\n{stderr}"
            ) from exc
