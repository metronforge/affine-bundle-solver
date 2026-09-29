#!/usr/bin/env python3
"""Fail closed if Linux CI's loaded LP64 BLAS is not the selected provider.

Inspect ldd's resolved files, not CMake variables or alternatives symlink names.
This is a CI identity assertion for Ubuntu's package layout, not a portable
end-user provider detector.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def validate_provider(paths, expected):
    kinds = set()
    for value in paths:
        p = Path(value)
        if "openblas" in p.name:
            kinds.add("openblas")
        elif p.parent.name == "blas" and p.name.startswith("libblas.so"):
            kinds.add("blas")
        elif p.parent.name == "lapack" and p.name.startswith("liblapack.so"):
            kinds.add("lapack")
        else:
            raise ValueError(f"unrecognized numerical dependency: {p}")
    required = {"openblas"} if expected == "openblas" else {"blas", "lapack"}
    if expected not in ("openblas", "reference") or kinds != required:
        raise ValueError(f"expected {expected}, resolved provider kinds {sorted(kinds)}")


def main():
    build, expected = sys.argv[1:]
    libraries = sorted(Path(build).glob("lib*.so"))
    if len(libraries) != 3:
        raise ValueError("expected three built solver libraries")
    paths = set()
    for lib in libraries:
        output = subprocess.check_output(["ldd", str(lib.resolve())], text=True)
        if "not found" in output:
            raise ValueError(output)
        for raw in re.findall(r"=> (/\S+)", output):
            resolved = Path(raw).resolve(strict=True)
            if "blas" in resolved.name or "lapack" in resolved.name:
                paths.add(str(resolved))
    validate_provider(paths, expected)
    print(json.dumps({"expected": expected, "resolved": [
        {"path": p, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()}
        for p in sorted(paths)]}, indent=2))


if __name__ == "__main__":
    main()
