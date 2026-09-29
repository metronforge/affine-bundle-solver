#!/usr/bin/env python3
"""Record source identity, exact CMake configuration, and tested DSO hashes."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
build, output = map(Path, sys.argv[1:])


def command(*argv):
    return subprocess.check_output(argv, cwd=root, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


dirty = command("git", "status", "--porcelain", "--untracked-files=no")
if dirty:
    raise SystemExit("portability evidence requires a clean tracked source tree")
libraries = sorted(build.glob("lib*.dylib" if sys.platform == "darwin" else "lib*.so"))
if len(libraries) != 3:
    raise SystemExit(f"expected three solver libraries, got {libraries}")
record = {
    "source": {"repository": str(root), "branch": command("git", "branch", "--show-current"),
               "commit": command("git", "rev-parse", "HEAD"),
               "tree": command("git", "rev-parse", "HEAD^{tree}"), "dirty": False},
    "runner": {k: os.environ.get(k) for k in
               ("RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "ImageOS", "ImageVersion", "GITHUB_RUN_ID")},
    "platform": platform.platform(), "machine": platform.machine(),
    "compiler": command(os.environ.get("CC", "cc"), "--version"),
    "cmake": command("cmake", "--version"),
    "cache": (build / "CMakeCache.txt").read_text(),
    "compile_commands": json.loads((build / "compile_commands.json").read_text()),
    "libraries": [{"path": str(p.resolve()), "sha256": sha(p),
                   "dependencies": command("otool", "-L", str(p.resolve())) if sys.platform == "darwin"
                       else command("ldd", str(p.resolve()))} for p in libraries],
}
output.write_text(json.dumps(record, indent=2) + "\n")
print(f"build provenance: {output} source={record['source']['commit']}")
