"""Native library paths for test tools; ABS_LIB_DIR selects the tested build."""
import os
import sys
from pathlib import Path


def library_path(name, directory=None):
    root = Path(directory) if directory is not None else Path(
        os.environ.get("ABS_LIB_DIR", Path(__file__).resolve().parents[1]))
    if sys.platform == "darwin":
        suffix = ".dylib"
    elif sys.platform.startswith("linux"):
        suffix = ".so"
    else:
        raise RuntimeError(f"unverified shared-library platform: {sys.platform}")
    return root.resolve() / ("lib" + name + suffix)
