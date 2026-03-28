"""
aom — CLI version management system for AI skills.

Entry point: bin/aom (bash/WSL) or bin/aom.ps1 (PowerShell)
"""

try:
    from aom._version import version as __version__
except ImportError:
    # Fallback for editable installs without setuptools-scm or running
    # directly from source without `pip install -e .`
    __version__ = "0.0.0-dev"
