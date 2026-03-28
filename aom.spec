# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ai-operation-manager
#
# Produces a single self-contained executable:
#   Windows : dist/aom.exe
#   Linux   : dist/aom
#
# Build with:
#   pyinstaller --clean aom.spec
#   (or via the platform build scripts: build.sh / build.ps1 / make build)

import sys
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Data files bundled inside the executable
# ---------------------------------------------------------------------------
# bin/ scripts are included so that:
#   1. Users who prefer the script-based workflow can extract them.
#   2. aom code can locate platform scripts via AOM_BUNDLE_DIR.
# Tuple format: (source_path_glob_or_dir, destination_inside_bundle)
datas = [
    ("bin", "bin"),
]

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
# PyInstaller cannot detect imports made via importlib / __import__ at build
# time. The adapter sub-package uses dynamic registration, so all adapters
# must be listed explicitly.
hidden_imports = [
    # Core package
    "aom",
    "aom.cli",
    "aom.config",
    "aom.git",
    "aom.models",
    "aom.discovery",
    "aom.resolver",
    "aom.registry",
    "aom.installer",
    "aom.manifest",
    # Adapter sub-package (dynamically loaded at runtime)
    "aom.adapters",
    "aom.adapters.base",
    "aom.adapters.suffix_adapter",
    "aom.adapters.dir_adapter",
    "aom.adapters.metadata_adapter",
]

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy stdlib modules we never use (keeps the binary smaller)
    excludes=[
        "tkinter",
        "unittest",
        "email",
        "html",
        "http",
        "urllib",
        "xml",
        "xmlrpc",
        "pydoc",
        "doctest",
        "difflib",
        "calendar",
        "ftplib",
        "imaplib",
        "poplib",
        "smtplib",
        "telnetlib",
        "curses",
        "cgi",
        "cgitb",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="aom",
    debug=False,
    bootloader_ignore_signals=False,
    # strip=True reduces binary size on Linux but can cause issues on Windows
    strip=(sys.platform != "win32"),
    upx=True,           # compress with UPX if available (optional, safe to omit)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # CLI tool — always use a console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # None = current machine architecture
    codesign_identity=None,
    entitlements_file=None,
)
