#!/usr/bin/env python3
"""
test_streaming_equivalence.py -- the incremental path against the batch one.

The handover asked that streaming m rows agree with "the batch call".  Which
batch call has to be named, because there are two and they are not the same
function:

  bsolve_seq_api          the loop over the threshold insertion routine
  bsolve_router_meta_api  the sketch/core route with escalation

The stream is built on the interval routine, which declines inside a band
where the threshold routine still answers.  So:

  - Where the stream defers nothing, its classification must agree with the
    router's whenever the router is itself decisive.  That is asserted.
  - Where the stream defers, it reports UNDECIDABLE with a rank interval.
    That is not a failure and is only recorded.

Also checks the property the API exists for: cost per insert must not grow
with the number of rows already inserted.
"""
import ctypes
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))

DP = ctypes.POINTER(ctypes.c_double)

lib.abs_stream_create.argtypes = [ctypes.c_int]
lib.abs_stream_create.restype = ctypes.c_void_p
lib.abs_stream_destroy.argtypes = [ctypes.c_void_p]
lib.abs_stream_insert.argtypes = [ctypes.c_void_p, DP, ctypes.c_double]
lib.abs_stream_insert.restype = ctypes.c_int
lib.abs_stream_status.argtypes = [ctypes.c_void_p, DP]
lib.abs_stream_counts.argtypes = [ctypes.c_void_p,
                                  ctypes.POINTER(ctypes.c_longlong),
                                  ctypes.POINTER(ctypes.c_longlong)]
lib.bsolve_router_meta_api.argtypes = [
    DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, DP]

CLS = {1: "UNIQUE", 2: "INFINITE", 3: "INCONSISTENT",
       4: "FAIL", 5: "UNDECIDABLE"}
DECISIVE = {1, 2, 3}


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def stream_classify(A, b):
    m, n = A.shape
    st = lib.abs_stream_create(n)
    assert st, "abs_stream_create returned NULL"
    A = np.ascontiguousarray(A, dtype=np.float64)
    for i in range(m):
        lib.abs_stream_insert(st, ptr(A[i]), float(b[i]))
    out = np.zeros(11)
    lib.abs_stream_status(st, ptr(out))
    seen = ctypes.c_longlong(0)
    deferred = ctypes.c_longlong(0)
    lib.abs_stream_counts(st, ctypes.byref(seen), ctypes.byref(deferred))
    lib.abs_stream_destroy(st)
    return out, seen.value, deferred.value


def router_classify(A, b):
    m, n = A.shape
    out = np.zeros(11)
    lib.bsolve_router_meta_api(ptr(A), ptr(b), None, m, n,
                               1, 2, 2, 12345, 0, ptr(out))
    return out


def cases():
    rng = np.random.default_rng(20260908)
    out = []
    for m, n in [(400, 12), (800, 24), (1500, 32)]:
        A = rng.standard_normal((m, n))
        x = rng.standard_normal(n)
        out.append((f"full_{m}x{n}", A, A @ x))
    for m, n, r in [(600, 20, 12), (1200, 32, 20)]:
        A = rng.standard_normal((m, r)) @ rng.standard_normal((r, n))
        x = rng.standard_normal(n)
        out.append((f"rankdef_{m}x{n}r{r}", A, A @ x))
    for m, n in [(500, 16), (900, 24)]:
        A = rng.standard_normal((m, n))
        b = A @ rng.standard_normal(n)
        b[m // 3] += 1.0
        out.append((f"inconsistent_{m}x{n}", A, b))
    for m, n in [(64, 128), (100, 300)]:
        A = rng.standard_normal((m, n))
        x = rng.standard_normal(n)
        out.append((f"under_{m}x{n}", A, A @ x))
    return out


def main():
    failures = []
    deferred_cases = 0

    print(f"  {'case':<24s} {'stream':>13s} {'router':>13s} "
          f"{'interval':>12s} {'deferred':>9s}")
    print("  " + "-" * 78)

    for name, A, b in cases():
        s_out, seen, deferred = stream_classify(A, b)
        r_out = router_classify(A, b)
        s_cls, r_cls = int(s_out[9]), int(r_out[9])

        # A closed stream stops examining rows, so the processed count is
        # allowed to fall short only when a contradiction was established.
        if s_cls == 3:
            if seen > A.shape[0]:
                failures.append(f"{name}: processed {seen} > {A.shape[0]} rows")
        elif seen != A.shape[0]:
            failures.append(
                f"{name}: processed {seen} of {A.shape[0]} rows without closing")

        if deferred:
            deferred_cases += 1
            if s_cls != 5 and s_cls != 3:
                failures.append(
                    f"{name}: {deferred} rows deferred but status is "
                    f"{CLS.get(s_cls)}, expected UNDECIDABLE or INCONSISTENT")
        else:
            if s_cls in DECISIVE and r_cls in DECISIVE and s_cls != r_cls:
                failures.append(
                    f"{name}: stream {CLS.get(s_cls)} vs router {CLS.get(r_cls)}")

        lo, hi = int(s_out[3]), int(s_out[4])
        if not (lo <= int(s_out[2]) <= hi):
            failures.append(f"{name}: rank {int(s_out[2])} outside [{lo}, {hi}]")

        print(f"  {name:<24s} {CLS.get(s_cls, '?'):>13s} "
              f"{CLS.get(r_cls, '?'):>13s} {f'[{lo}, {hi}]':>12s} "
              f"{deferred:>9d}")

    # Cost per insert must not depend on how many rows came before.
    n = 32
    rng = np.random.default_rng(7)
    rows = np.ascontiguousarray(rng.standard_normal((4000, n)))
    st = lib.abs_stream_create(n)
    per_block = []
    for block in range(4):
        t0 = time.perf_counter()
        for i in range(block * 1000, (block + 1) * 1000):
            lib.abs_stream_insert(st, ptr(rows[i]), 1.0)
        per_block.append(time.perf_counter() - t0)
    lib.abs_stream_destroy(st)

    print()
    print("  cost of 1000 inserts, by position in the stream: " +
          ", ".join(f"{t*1e3:.1f} ms" for t in per_block))
    # Generous: a batch recompute would make the last block ~4x the first.
    if per_block[-1] > 2.5 * per_block[0] + 1e-3:
        failures.append(
            f"insert cost grows with stream length: "
            f"{per_block[0]*1e3:.1f} ms then {per_block[-1]*1e3:.1f} ms")

    print()
    if failures:
        print(f"FAIL ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"ok: {len(cases())} systems, {deferred_cases} with deferred rows, "
          f"insert cost flat across the stream")
    return 0


if __name__ == "__main__":
    sys.exit(main())
