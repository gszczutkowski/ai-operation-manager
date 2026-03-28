# aom — AI Operation Manager

A zero-dependency Python CLI that installs and manages versioned AI skills (Claude Code slash commands, agents, hooks) across projects. Skills are versioned by **git tag** in a remote repository; each project independently pins the versions it needs.

## How it works

- Skills live in a remote git repository (SSH or HTTPS)
- Each released version is tagged: `skills/create-jira-story@1.0.0`
- The CLI maintains a local bare clone and fetches specific versions on demand
- Each project declares its requirements in its AI agent config file (e.g. `CLAUDE.md`)
- Different projects can use different versions of the same skill simultaneously

---

## Requirements

- Python 3.6+ (no third-party packages)
- `git` on PATH
- SSH key configured for the remote repository (for SSH URLs)

---

## Installation

### Option A — Pre-built binary (recommended)

Download the latest binary for your platform from the [Releases](../../releases) page:

| Platform | File |
|----------|------|
| Linux (x86-64) | `aom-linux-amd64` |
| Windows (x86-64) | `aom-windows-amd64.exe` |

```bash
# Linux / macOS
chmod +x aom-linux-amd64
sudo mv aom-linux-amd64 /usr/local/bin/aom
aom --help
```

```powershell
# Windows — copy to a directory on your PATH, e.g. C:\tools\
Move-Item aom-windows-amd64.exe C:\tools\aom.exe
aom --help
```

### Option B — From source (script-based)

Clone the repository and add `bin/` to your PATH:

```bash
# Unix / macOS / WSL
git clone git@github.com:yourorg/ai-operation-manager.git ~/ai-operation-manager
export PATH="$HOME/ai-operation-manager/bin:$PATH"   # add to ~/.bashrc or ~/.zshrc
```

```powershell
# Windows PowerShell
git clone git@github.com:yourorg/ai-operation-manager.git $HOME\ai-operation-manager
# Add $HOME\ai-operation-manager\bin to your system PATH, then use aom.ps1
```

---

## Quick start

### Initialize a project

```bash
cd ~/my-project
aom init
```

The wizard detects your AI agent config file (e.g. `CLAUDE.md`), asks for the skills repository URL, and saves it. On first use it clones the remote repo into a local cache.

```
aom init

  Found: CLAUDE.md  ->  ClaudeCode
  Use this config file? [Y/n]:

  Enter the SSH (or HTTPS) URL of your skills repository:
    git@gitlab.com:myorg/ai-grimoire.git

  Saved to CLAUDE.md
  Fetch skill index from repository now? [Y/n]:
  Fetched. 12 skill version(s) available.

Next steps:
  aom list            -- view available skills
  aom install NAME    -- install a skill
  aom sync            -- install all required skills from config
```

### Declare requirements in CLAUDE.md

````markdown
## Skills Source

```yaml
url: "git@gitlab.com:myorg/ai-grimoire.git"
```

## Skills Requirements

```yaml
required:
  create-jira-story: "1.0.0"
  design-workflow: ">=1.1.0"
  evaluate-workflow: "latest"
```
````

Then install everything:

```bash
aom sync
```

Any teammate who checks out the project runs the same command — the tool clones the remote on first use automatically.

---

## Commands

| Command | Description |
|---------|-------------|
| `aom init` | Interactive setup: detect agent, save repository URL |
| `aom install NAME[:VERSION]` | Install a skill (local scope by default) |
| `aom list` | Show available and installed versions |
| `aom sync` | Install all requirements from the config file |
| `aom update NAME` | Update a skill to the latest stable version |
| `aom remove NAME` | Remove an installed skill |
| `aom env` | Show repository and environment configuration |

### aom init

Interactive setup wizard. Detects AI agent config files in the project directory, asks for the repository SSH/HTTPS URL, writes it to the config file, and optionally fetches the tag index.

```
aom init

  Scanning current directory...
  Found: CLAUDE.md → ClaudeCode
  Use this config file? [Y/n]: Y

  Enter the SSH (or HTTPS) URL of your skills repository.
    git@gitlab.com:myorg/ai-grimoire.git

  ✓ Saved to CLAUDE.md
  Fetch skill index from repository now? [Y/n]: Y
    Fetching git@gitlab.com:myorg/ai-grimoire.git …
  ✓ Fetched. 12 skill version(s) available.
```

### aom install

```bash
aom install create-jira-story          # latest stable, local scope
aom install create-jira-story:1.0.0    # exact version, local scope
aom install design-workflow:>=1.0.0 --global
aom install create-jira-story --no-overwrite  # skip if already installed
aom install create-jira-story --fetch  # refresh tag index first
```

### aom list

```
SKILL                    LOCAL    GLOBAL   LATEST
-------------------------------------------------
create-jira-story        —        1.0.0    1.2.0
design-workflow          1.0.0    —        1.1.0
evaluate-skill           —        —        1.0.0
```

`--fetch` pulls the latest tags from the remote before listing.

### aom sync

```bash
aom sync                      # install from local CLAUDE.md
aom sync --dry-run            # preview without installing
aom sync --force              # reinstall even if already installed
aom sync --fetch              # fetch latest tags before syncing
aom sync --project-dir /path  # specify project directory
```

### aom remove

```bash
aom remove create-jira-story          # remove from local scope
aom remove create-jira-story --global # remove from global scope
```

### aom update

Reinstalls the latest stable repository version (delegates to `install :latest`).

### aom env

```
AI Agent
----------------------------------------
  Agent                          ClaudeCode
  dir_name                       .claude
  config_file                    CLAUDE.md

Skills Repository
----------------------------------------
  url                            git@gitlab.com:myorg/ai-grimoire.git
  cache                          ~/.cache/ai-operation-manager/a3f9b2c1d4e5  [✓ cloned]
  tagged versions                12

Install locations
----------------------------------------
  global : /home/user/.claude
  local  : /home/user/my-project/.claude
```

`--check` exits with code 1 if no repository URL is configured.

### Version constraints

| Syntax | Meaning |
|--------|---------|
| `1.0.0` | Exact version |
| `>=1.2.0` | Minimum version (highest satisfying) |
| `latest` or `*` | Highest stable version |

---

## Supported AI agents

The tool detects the active agent automatically from config files in the project directory. No environment variables required after `aom init`.

| Config file | Agent |
|-------------|-------|
| `CLAUDE.md` | ClaudeCode |
| `.cursorrules` | Cursor |
| `opencode.json` | OpenCode |
| `AGENTS.md` | Codex |
| `.aider.conf.yml` | Aider |

If multiple are found, the wizard asks which to use.

---

## Installation scopes

| Scope | Location | Use case |
|-------|----------|----------|
| Local | `<project>/.claude/` | Project-specific, pinned via `aom sync` |
| Global | `~/.claude/` | Available in all projects |

Local takes precedence over global when both are installed.

Different projects can pin different versions of the same skill simultaneously:

| Scope | Installed version |
|-------|-----------------|
| Remote repo (source) | `1.2.0` (HEAD) |
| Global `~/.claude/` | `1.1.0` |
| Project A `.claude/` | `1.0.0` |
| Project B `.claude/` | `1.2.0` |

---

## Versioning skills in the remote repository

Skills are versioned with git tags. Every time a skill's frontmatter version is bumped, a matching tag must be pushed:

```bash
# 1. Bump version in frontmatter
#    skills/create-jira-story/SKILL.md: version: 1.3.0

git add skills/create-jira-story/SKILL.md
git commit -m "Bump create-jira-story to 1.3.0"

# 2. Tag the commit — REQUIRED for the version to be installable
git tag skills/create-jira-story@1.3.0
git push && git push --tags
```

If the tag is omitted, the version exists in the frontmatter but cannot be resolved or installed.

Different skills have independent tag histories:

```
Commit A  ← tag: skills/create-jira-story@1.0.0
           ← tag: skills/design-workflow@1.0.0
Commit B  ← tag: skills/design-workflow@1.1.0
Commit C  ← tag: skills/create-jira-story@1.1.0
Commit D  ← tag: skills/create-jira-story@1.2.0  (HEAD)
```

Installing `create-jira-story:1.2.0` and `design-workflow:1.0.0` in the same project works — each tag is resolved independently.

---

## Environment variables

All environment variables are optional. The repository URL is stored in the project config file by `aom init`.

| Variable | Description |
|----------|-------------|
| `AI_SKILLS_REPO_PATH` | Fallback: local filesystem path to the repository root. Used when no URL is configured (e.g. local development inside the grimoire repo). |
| `AI_SKILLS_SCRIPTS_PATH` | Auto-detected from the script's own location. |
| `AI_AGENT_DEFAULT` | Fallback: active AI agent name. Overridden by config file detection in CWD. |

---

## Usage scenarios

### Scenario 1 — First-time project setup

```bash
cd ~/my-project
aom init
# → detects CLAUDE.md → asks for SSH URL → fetches tag index

aom list                   # see all available versions
aom install create-jira-story:1.0.0
aom install design-workflow
```

### Scenario 2 — Team shares requirements via CLAUDE.md

Any developer clones the project and runs:

```bash
aom sync
# → clones the remote repo (first time), installs required skills
```

### Scenario 3 — Per-project version pinning

```bash
# Project A — CLAUDE.md
required:
  create-jira-story: "1.0.0"
  design-workflow: "1.0.0"

# Project B — CLAUDE.md
required:
  create-jira-story: "latest"
  design-workflow: ">=1.1.0"
```

Both projects pull from the same remote repo but install independently.

### Scenario 4 — System-wide shared skills

```bash
aom install evaluate-workflow:1.0.0 --global
# → available in all projects; local scope takes precedence
```

### Scenario 5 — Refresh and preview

```bash
aom sync --fetch --dry-run
# → fetches latest tags, shows what would be installed without doing it
```

---

## Development

### Running tests locally

The test suite uses **pytest** with coverage reporting. Install the dev dependencies in a virtual environment:

```bash
# Create a virtual environment and install dev dependencies
python -m venv .venv

# Activate (Linux / macOS)
source .venv/bin/activate

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install the package with dev extras
pip install -e ".[dev]"
```

Run the full suite:

```bash
# Tests with coverage report
pytest

# Tests without coverage (faster)
pytest --no-cov

# Run a specific test file
pytest tests/test_models.py -v

# Run a single test
pytest tests/test_models.py::TestParseVersion::test_basic_semver
```

Via GNU make:

```bash
make test       # run pytest
make lint       # flake8 + black --check
make format     # auto-format with black
```

The CI pipeline runs the same tests across Python 3.10/3.11/3.12 on both Ubuntu and Windows — see [`.github/workflows/build.yml`](.github/workflows/build.yml).

---

## Building from source

The project uses [PyInstaller](https://pyinstaller.org) to produce a single self-contained executable — no Python installation required on the target machine.

### Prerequisites

- Python 3.8+
- `pip` (to install PyInstaller as a build-only dependency)
- `git` on PATH

### Quick build

**Linux / macOS:**

```bash
bash build.sh
# output: dist/aom
```

**Windows (PowerShell):**

```powershell
.\build.ps1
# output: dist\aom.exe
```

**Cross-platform via GNU make:**

```bash
make build        # build the executable
make clean        # remove dist/, build/ artefacts
make dev-install  # pip install -e . (editable mode for development)
```

> On Windows, GNU make is available via `winget install GnuWin32.Make` or `choco install make`.

### What gets built

PyInstaller packages the following into a single binary using `aom.spec`:

| Bundled item | Destination inside bundle |
|---|---|
| `aom/` Python package | `aom/` |
| `bin/aom` (bash) | `bin/aom` |
| `bin/aom.ps1` (PowerShell) | `bin/aom.ps1` |
| All alias scripts (`aom-install`, `aom-list`, `aom-sync`) | `bin/` |

At runtime the binary extracts to a temporary directory (`sys._MEIPASS`). `main.py` exposes that path via the `AOM_BUNDLE_DIR` environment variable and adds `bin/` to `PATH` so subprocesses can locate the platform scripts.

### How path resolution works in the bundle

`config.py` auto-detects the project root at runtime using `Path(__file__).resolve().parent.parent`. Inside the PyInstaller bundle `__file__` points to `sys._MEIPASS/aom/config.py`, so the parent chain resolves to `sys._MEIPASS` — which contains `aom/` and `bin/`. No code changes are needed; the detection logic works identically in both development and bundled modes.

### Build script options

```bash
# Clean previous artefacts before building
bash build.sh --clean

# PowerShell equivalent
.\build.ps1 -Clean
```

### PyInstaller spec highlights (`aom.spec`)

- **`--onefile` mode** — single executable, no loose files to distribute
- **`datas`** — bundles the entire `bin/` directory
- **`hiddenimports`** — explicitly lists all adapter sub-modules (required because they are registered dynamically)
- **`excludes`** — strips unused stdlib modules (`tkinter`, `http`, `email`, etc.) to minimise binary size
- **`console=True`** — always attaches to a terminal (CLI tool)
- **`strip=True` on Linux** — reduces binary size; disabled on Windows where it can cause issues

---

## GitHub Actions CI/CD

The workflow file is at [.github/workflows/build.yml](.github/workflows/build.yml).

### What it does

On every push to `main` and on every pull request targeting `main`, the pipeline runs two parallel jobs:

| Job | Runner | Output |
|-----|--------|--------|
| `build-linux` | `ubuntu-latest` | `dist/aom` |
| `build-windows` | `windows-latest` | `dist\aom.exe` |

Each job:
1. Checks out the repository
2. Sets up Python 3.11 with pip caching
3. Installs PyInstaller
4. Runs the platform build script (`build.sh` / `build.ps1`)
5. Runs a smoke test (`aom --help`)
6. Uploads the binary as a GitHub Actions artifact (retained for 30 days)

### Creating a release

Push a version tag to trigger a GitHub Release automatically:

```bash
git tag v1.2.0
git push origin v1.2.0
```

The `release` job runs after both build jobs succeed. It:
1. Downloads both platform artifacts
2. Renames them to `aom-linux-amd64` and `aom-windows-amd64.exe`
3. Generates a `checksums.txt` (SHA-256)
4. Creates a GitHub Release with all three files attached and auto-generated release notes

Tags containing a hyphen (e.g. `v1.2.0-beta`) are automatically marked as pre-releases.

### Workflow triggers summary

| Event | Jobs run |
|-------|---------|
| Push to `main` | `build-linux`, `build-windows` |
| Pull request to `main` | `build-linux`, `build-windows` |
| Push tag `v*` | `build-linux`, `build-windows`, `release` |

---

## Architecture

### Scopes

| Scope | Location (ClaudeCode) |
|-------|----------------------|
| Repository | Remote git repo (SSH/HTTPS) — source of truth |
| Global | `~/.claude/` |
| Local | `<project>/.claude/` |

### Git-backed repository (`git.py`)

`GitRepo` maintains a local bare clone of the remote skills repository:

```
Cache location:
  Linux/macOS: ~/.cache/ai-operation-manager/<url-hash>/
  Windows:     %LOCALAPPDATA%/ai-operation-manager/<url-hash>/
```

Cloned once with `--filter=blob:none` (no file contents downloaded upfront). Blobs are fetched lazily when a skill is installed.

| Method | Network? | Description |
|--------|----------|-------------|
| `ensure_cloned()` | First time only | `git clone --bare --filter=blob:none` |
| `fetch()` | Yes | `git fetch --tags --prune origin` |
| `list_skill_tags()` | No | `git for-each-ref refs/tags/` — reads local refs |
| `read_file_at_tag(tag, path)` | Lazy | `git show TAG:path` — fetches blob on demand |
| `extract_path_at_tag(tag, path, dest)` | Lazy | `git archive` + Python `tarfile` for directories |

### Adapter pattern

Each `StructureAdapter` implements:

```
can_handle(path) → bool
extract_records(artifact_dir, artifact_type) → List[SkillRecord]
```

Adapters are chained in priority order: Suffix → Directory → Metadata. The Metadata adapter is the catch-all for the current repo layout.

| Adapter | On-disk layout | Notes |
|---------|---------------|-------|
| `suffix_adapter` | `name@1.0.0/` | Version visible in filesystem; requires renaming on release |
| `dir_adapter` | `name/1.0.0/` | Multiple versions can coexist; deeper nesting |
| `metadata_adapter` | version in frontmatter | **Recommended** — stable paths, version co-located with definition |

### SkillRecord

```python
@dataclass
class SkillRecord:
    name: str                  # "create-jira-story" or "child/page-painter"
    artifact_type: str         # "skills" | "commands" | "agents" | "hooks"
    path: Optional[Path]       # local path; None for git-only records
    version: Optional[Version]
    structure: str             # "suffix" | "directory" | "metadata" | "flat" | "git"
    git_tag: Optional[str]     # e.g. "skills/create-jira-story@1.0.0"
```

Records from local filesystem scans have `path` set and `git_tag=None`. Records from git tag scanning have `git_tag` set and `path=None`.

### Resolution priority

```
1. Local (<project>/.claude/)  — already installed in this project
2. Global (~/.claude/)         — available system-wide
3. Repository (remote git)     — source of truth
```

### Registry format

Stored inside the agent directory (`registry.json`):

```json
{
  "version": 1,
  "installed": {
    "skills/complex-evaluator": "1.0.2",
    "commands/deploy-skills":   "1.0.0"
  },
  "updated_at": "2026-03-27T12:00:00+00:00"
}
```

### CLAUDE.md integration

`aom init` writes two sections to the project config file:

**`## Skills Source`** — the remote repository URL:

```markdown
## Skills Source

```yaml
url: "git@gitlab.com:myorg/ai-grimoire.git"
```
```

**`## Skills Requirements`** — pinned versions:

```markdown
## Skills Requirements

```yaml
required:
  create-jira-story: "1.0.0"
  design-workflow: ">=1.0.0"
  evaluate-workflow: "latest"
  child/generate-handwriting-practice: "*"
```

The header is case-insensitive. The parser accepts fenced YAML blocks or 4-space-indented YAML.

### AI agent detection

The active agent is resolved via:

1. In-process cache (already resolved this session)
2. Config file detected in CWD (`CLAUDE.md` → `ClaudeCode`) — **no env var needed**
3. `AI_AGENT_DEFAULT` environment variable
4. Auto-select when only one agent is defined
5. Interactive prompt

`aom init` writes the config file, so after initialization the agent is detected automatically.

**Type directory mapping** — for ClaudeCode, grimoire `skills/` and `commands/` both install into the agent's `commands/` directory. A skill named `create-jira-story` installs to `~/.claude/commands/create-jira-story/`.

---

## Project structure

```
.github/
  workflows/
    build.yml               # CI/CD: build Linux + Windows, create releases
bin/
  aom                       # Bash / WSL entry point → python -m aom.cli
  aom.ps1                   # PowerShell entry point (handles Python discovery)
  aom-install               # Alias: aom install ...
  aom-list                  # Alias: aom list ...
  aom-sync                  # Alias: aom sync ...
  aom-install.ps1           # Windows aliases
  aom-list.ps1
  aom-sync.ps1
aom/
  __init__.py               # package version
  __main__.py               # python -m aom entry point
  cli.py                    # argparse command dispatcher
  config.py                 # agent detection, path resolution
  git.py                    # GitRepo: bare clone + tag-based file access
  models.py                 # Version, SkillRecord, VersionRequirement
  discovery.py              # scan local filesystem or git tags
  resolver.py               # version constraint resolution
  registry.py               # JSON registry (tracks installed versions)
  installer.py              # file copy / git extract + registry update
  manifest.py               # config file parser/writer (requirements + source URL)
  adapters/
    base.py                 # abstract StructureAdapter
    metadata_adapter.py     # recommended: version in frontmatter
    suffix_adapter.py       # option A: name@1.0.0/
    dir_adapter.py          # option B: name/1.0.0/
tests/
  conftest.py               # shared fixtures
  test_models.py            # Version, SkillRecord, VersionRequirement
  test_manifest.py          # CLAUDE.md parsing / writing
  test_registry.py          # JSON registry persistence
  test_resolver.py          # version constraint resolution
  test_discovery.py         # repository scanning, grouping
  test_installer.py         # install / uninstall logic
  test_config.py            # agent detection, path functions
  test_git.py               # GitRepo (mocked subprocess)
  test_cli.py               # argument parsing, command dispatch
  test_adapters.py          # all three structure adapters
main.py                     # PyInstaller entry point (frozen + source modes)
aom.spec                    # PyInstaller build configuration
build.sh                    # Linux / macOS build script
build.ps1                   # Windows build script
Makefile                    # Cross-platform build via GNU make
pyproject.toml              # project metadata + pip entry-point declaration
README.md                   # this file — user guide + architecture reference
```

---

## Portability

- Pure Python 3.6+ stdlib — no pip install required (when using source mode)
- Requires `git` on PATH (used for all remote operations)
- Works on Linux, macOS, Windows (PowerShell wrapper included)
- All paths resolved dynamically via `pathlib.Path`
- Git cache follows XDG on Linux/macOS, `%LOCALAPPDATA%` on Windows
- UTF-8 output enforced on Windows (`sys.stdout` wrapped at startup)
- Pre-built binaries are fully self-contained — no Python or git needed on the target machine for the binary itself (git is still needed for skill operations)
