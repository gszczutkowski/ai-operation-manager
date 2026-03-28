# Makefile for ai-operation-manager
# Requires GNU make (available via Homebrew on macOS, apt on Linux,
# or `choco install make` / `winget install GnuWin32.Make` on Windows).
#
# Primary targets:
#   make build          — build the platform-native executable into dist/
#   make clean          — remove build artefacts
#   make build-deps     — install pyinstaller (build-only dependency)
#   make dev-install    — install the package in editable mode for development
#   make test           — run the test suite (if present)

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

ifeq ($(OS),Windows_NT)
    PYTHON    := python
    EXE_EXT   := .exe
    RM_RF     := rmdir /s /q
    # On Windows, GNU make may not have /dev/null; swallow errors differently
    DEVNULL   := NUL
else
    PYTHON    := python3
    EXE_EXT   :=
    RM_RF     := rm -rf
    DEVNULL   := /dev/null
endif

DIST_DIR  := dist
BUILD_DIR := build
SPEC_FILE := aom.spec
EXE_NAME  := aom$(EXE_EXT)

.PHONY: build clean build-deps dev-install test help

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------

help:
	@echo "Available targets:"
	@echo "  build        Build the platform-native executable (dist/$(EXE_NAME))"
	@echo "  clean        Remove build artefacts (dist/, build/, *.pyc)"
	@echo "  build-deps   Install PyInstaller (build-only dependency)"
	@echo "  dev-install  Install package in editable mode for development"
	@echo "  test         Run the test suite"

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

build: build-deps
	$(PYTHON) -m PyInstaller --clean $(SPEC_FILE)
	@echo ""
	@echo "==> Build complete: $(DIST_DIR)/$(EXE_NAME)"

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

build-deps:
	$(PYTHON) -m pip install --quiet --upgrade pyinstaller

dev-install:
	$(PYTHON) -m pip install -e .

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m flake8 aom/ tests/ --max-line-length=120 --extend-ignore=E203,W503
	$(PYTHON) -m black --check aom/ tests/

format:
	$(PYTHON) -m black aom/ tests/

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

clean:
ifeq ($(OS),Windows_NT)
	-$(RM_RF) $(DIST_DIR) 2>$(DEVNULL)
	-$(RM_RF) $(BUILD_DIR) 2>$(DEVNULL)
	-$(RM_RF) __pycache__ 2>$(DEVNULL)
	-del /q *.spec.bak 2>$(DEVNULL)
else
	$(RM_RF) $(DIST_DIR) $(BUILD_DIR) __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>$(DEVNULL) || true
	find . -name "*.pyc" -delete 2>$(DEVNULL) || true
endif
