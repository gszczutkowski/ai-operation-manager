"""
PyInstaller entry point for ai-operation-manager.

Handles path setup for bundled resources (sys._MEIPASS) and delegates to
aom.cli. Also works normally when run from source with:
    python main.py <command> [options]
"""
import os
import sys


def _setup_frozen_env() -> None:
    """Configure the environment when running as a PyInstaller --onefile bundle.

    PyInstaller extracts the bundle to a temporary directory (sys._MEIPASS) at
    runtime.  We need to make sure:
      - sys._MEIPASS is on sys.path so internal imports resolve correctly.
      - The bundled bin/ directory is on PATH so any subprocess that invokes a
        platform script can find it.
      - AOM_BUNDLE_DIR is exported so aom code can locate bundled
        files via os.environ['SKILL_BUNDLE_DIR'] when needed.
    """
    meipass: str = getattr(sys, "_MEIPASS", "")
    if not meipass:
        return  # running from source — nothing to do

    # Keep the bundle root first on sys.path
    if meipass not in sys.path:
        sys.path.insert(0, meipass)

    # Expose bundle root for any code that locates sibling resources at runtime
    os.environ.setdefault("AOM_BUNDLE_DIR", meipass)

    # Add bundled bin/ to PATH so subprocesses can find the platform scripts
    bin_dir = os.path.join(meipass, "bin")
    if os.path.isdir(bin_dir):
        current_path = os.environ.get("PATH", "")
        if bin_dir not in current_path.split(os.pathsep):
            os.environ["PATH"] = bin_dir + os.pathsep + current_path


if __name__ == "__main__":
    _setup_frozen_env()

    from aom.cli import main  # noqa: E402  (must be after path setup)

    sys.exit(main())
