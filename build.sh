#!/usr/bin/env bash
# build.sh — Build the aom executable for Linux / macOS
#
# Usage:
#   bash build.sh            # standard build
#   bash build.sh --clean    # remove previous artefacts before building
#
# Output: dist/aom  (no extension, executable bit set)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
CLEAN=false
for arg in "$@"; do
    case "$arg" in
        --clean|-c) CLEAN=true ;;
        --help|-h)
            echo "Usage: bash build.sh [--clean]"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(sys.version_info >= (3,8))")
        if [ "$version" = "True" ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.8+ is required but was not found." >&2
    echo "Install it via your package manager (e.g. apt install python3, brew install python)." >&2
    exit 1
fi

echo "==> Using Python: $($PYTHON --version)"

# ---------------------------------------------------------------------------
# Install build dependency
# ---------------------------------------------------------------------------
echo "==> Installing PyInstaller..."
"$PYTHON" -m pip install --quiet --upgrade pyinstaller

# ---------------------------------------------------------------------------
# Optional clean
# ---------------------------------------------------------------------------
if [ "$CLEAN" = "true" ]; then
    echo "==> Cleaning previous build artefacts..."
    rm -rf dist build
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
echo "==> Building aom (Linux/macOS)..."
"$PYTHON" -m PyInstaller --clean aom.spec

# ---------------------------------------------------------------------------
# Verify output
# ---------------------------------------------------------------------------
OUTPUT="dist/aom"
if [ ! -f "$OUTPUT" ]; then
    echo "ERROR: Build finished but expected output not found: $OUTPUT" >&2
    exit 1
fi

# Ensure the executable bit is set (PyInstaller sets it, but be explicit)
chmod +x "$OUTPUT"

echo ""
echo "==> Build complete!"
echo "    Executable : $SCRIPT_DIR/$OUTPUT"
echo "    Size       : $(du -sh "$OUTPUT" | cut -f1)"
echo ""
echo "Quick test:"
echo "    $OUTPUT --help"
