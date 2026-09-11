#!/usr/bin/env python3
"""Rank-adaptive stream storage and allocation-failure atomicity."""

from __future__ import annotations

import ctypes
import os
import resource
import sys
from pathlib import Path


if not sys.platform.startswith("linux"):
    print("rank-adaptive stream storage: SKIP (Linux RLIMIT_AS test)")
    raise SystemExit(0)


ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
DP = ctypes.POINTER(ctypes.c_double)
ABS_INSERT_GROW = 1
ABS_INSERT_ENOMEM = -3


def virtual_bytes() -> int:
    pages = int(Path("/proc/self/statm").read_text().split()[0])
    return pages * os.sysconf("SC_PAGE_SIZE")


lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))
lib.abs_stream_create.argtypes = [ctypes.c_int]
lib.abs_stream_create.restype = ctypes.c_void_p
lib.abs_stream_destroy.argtypes = [ctypes.c_void_p]
lib.abs_stream_insert.argtypes = [ctypes.c_void_p, DP, ctypes.c_double]
lib.abs_stream_insert.restype = ctypes.c_int
lib.abs_stream_counts.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_longlong),
    ctypes.POINTER(ctypes.c_longlong),
]
lib.abs_stream_status.argtypes = [ctypes.c_void_p, DP]

# Large enough that the first eight-row basis allocation cannot fit in the
# one-megabyte headroom below, while the O(n) constructor remains modest.
n = 250_000
row = (ctypes.c_double * n)()
row[0] = 1.0
stream = lib.abs_stream_create(n)
assert stream, "O(n) stream construction failed"

old_soft, hard = resource.getrlimit(resource.RLIMIT_AS)
limited = virtual_bytes() + 1024 * 1024
if hard != resource.RLIM_INFINITY:
    assert limited < hard, "not enough RLIMIT_AS headroom for the test"
resource.setrlimit(resource.RLIMIT_AS, (limited, hard))
try:
    rc = lib.abs_stream_insert(stream, row, 1.0)
finally:
    resource.setrlimit(resource.RLIMIT_AS, (old_soft, hard))

seen = ctypes.c_longlong()
deferred = ctypes.c_longlong()
lib.abs_stream_counts(stream, ctypes.byref(seen), ctypes.byref(deferred))
status = (ctypes.c_double * 11)()
lib.abs_stream_status(stream, status)
assert rc == ABS_INSERT_ENOMEM, f"growth returned {rc}, expected ENOMEM"
assert seen.value == 0 and deferred.value == 0
assert int(status[2]) == 0, "failed growth changed the rank"

# The exact same row remains retryable once memory is available.
rc = lib.abs_stream_insert(stream, row, 1.0)
lib.abs_stream_counts(stream, ctypes.byref(seen), ctypes.byref(deferred))
assert rc == ABS_INSERT_GROW
assert seen.value == 1 and deferred.value == 0
lib.abs_stream_destroy(stream)

print("rank-adaptive stream storage: PASS")
print("allocation failure leaves row count and rank unchanged; retry succeeds")
