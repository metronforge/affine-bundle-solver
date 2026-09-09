#!/usr/bin/env python3
"""
allocation_audit.py -- which allocations have no NULL check.

The handover for task 8 recorded "~15 LAPACK workspace sites". The number is
larger and the shape of the work is different, so this script exists to make
the count reproducible rather than remembered.

A site counts as checked when the allocated lvalue appears within the next 14
lines in a NULL test: !v, v == NULL, or as a conjunct of a combined guard such
as `if (An && bn && dmant && ...)`. That last form is why a narrower window or
a plain `!v` search overcounts: certified_api.c looks unchecked to a naive
scan and is in fact clean.

Run from the repository root.
"""
import pathlib
import re
import sys

ALLOC = re.compile(
    r'([A-Za-z_]\w*(?:\s*(?:->|\.)\s*\w+)*)\s*=\s*'
    r'(?:\([^;)]*\)\s*)?(?:malloc|calloc)\s*\(')
WINDOW = 14

# Everything from this line on in bsolver_core.c is the embedded benchmark
# driver and its main(), not a path the library takes.
BENCH_FROM = {"src/bsolver_core.c": 196}


def audit(path):
    lines = pathlib.Path(path).read_text().splitlines()
    bench_from = BENCH_FROM.get(path, 10 ** 9)
    lib, bench = [], []
    for i, line in enumerate(lines):
        for m in ALLOC.finditer(line):
            v = m.group(1).replace(" ", "")
            win = "\n".join(lines[i:i + WINDOW]).replace(" ", "")
            e = re.escape(v)
            if re.search(r'!%s\b|%s==NULL|%s&&|&&%s\b|if\(%s\)' % (e, e, e, e, e), win):
                continue
            (bench if i + 1 >= bench_from else lib).append((i + 1, v))
    return lib, bench


def main():
    total_lib = total_bench = 0
    for path in ("src/bsolver.c", "src/bsolver_core.c",
                 "src/certified_api.c", "src/formation_guard.c",
                 "src/status_certificate.c"):
        lib, bench = audit(path)
        total_lib += len(lib)
        total_bench += len(bench)
        print(f"{path}: {len(lib)} on library paths, {len(bench)} in the "
              f"benchmark driver")
        for ln, v in lib:
            print(f"    {ln:>5d}  {v}")
    print()
    print(f"unchecked on library paths: {total_lib}")
    print(f"unchecked in the benchmark driver: {total_bench}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
