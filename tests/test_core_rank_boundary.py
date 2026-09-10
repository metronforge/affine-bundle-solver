#!/usr/bin/env python3
"""
test_core_rank_boundary.py -- the escalation route through the compressed core.

core_qr_state calls core_has_rank_boundary and core_svd_state only when the
QRCP of the compressed core is itself ambiguous: the smallest accepted
diagonal, or the first rejected one, sits inside the window the core rank
tolerance opens.  Random well-conditioned systems never land there, so both
routines had zero coverage, and bsolve_last_core_rank_interval_api -- their
only writer -- returned (-1, -1) on everything.

Reaching them takes a controlled spectral gap rather than a perturbed row: a
system built as U diag(1, ..., 1, g) V^T with g placed decade by decade.  What
is checked here is the separation this route is for, not that the routines
run:

    g well above the window   ->  UNIQUE, a point rank
    g inside the window       ->  UNDECIDABLE, an interval, no point rank
    g well below the window   ->  the direction is absent, rank n-1

plus the invariance and refusal properties that make the middle verdict worth
having.  A route that answered UNIQUE throughout would satisfy any test that
only asked whether the code was entered.
"""
import ctypes
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))

DP = ctypes.POINTER(ctypes.c_double)
IP = ctypes.POINTER(ctypes.c_int)
lib.bsolve_router_meta_api.argtypes = ([DP, DP, DP] + [ctypes.c_int] * 5
                                       + [ctypes.c_ulonglong, ctypes.c_int, DP])
lib.bsolve_last_core_rank_interval_api.argtypes = [IP]

STATUS, CERTAINTY, RANK, RANK_LO, RANK_HI = 0, 1, 2, 3, 4
UNIQUE, INFINITE, INCONSISTENT, FAIL, UNDECIDABLE = 1, 2, 3, 4, 5
DETERMINISTIC = 1
NAME = {UNIQUE: "UNIQUE", INFINITE: "INFINITE", INCONSISTENT: "INCONSISTENT",
        FAIL: "FAIL", UNDECIDABLE: "UNDECIDABLE"}

# src/bsolver.c: the core routes pass ranktol = 1e-11 and open the ambiguity
# window at 0.01*ranktol and 100*ranktol, which is the same four decades the
# published dependence and growth thresholds span.
BAND = (1e-12, 1e-11, 1e-10)
ABOVE = (1e-4, 1e-6, 1e-8)
# 1e-13 is the window edge itself (0.01 * ranktol) and the comparison there is
# strict, so whether a given shape lands inside or outside is decided by the
# last bits of the computed ratio.  A test that straddles the edge measures
# rounding, not the separation, so the below-window gaps start a decade down.
BELOW = (1e-14, 1e-16, 0.0)

SHAPES = [(200, 16), (400, 32), (1000, 64), (256, 256)]

failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
    print(f"  [{'ok' if ok else 'FAIL'}] {what}")


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def classify(A, b, seed=3):
    out = np.zeros(11, dtype=np.float64)
    m, n = A.shape
    lib.bsolve_router_meta_api(ptr(A), ptr(b), None, m, n, 1, 2, 2, seed, 0,
                               ptr(out))
    iv = (ctypes.c_int * 2)()
    lib.bsolve_last_core_rank_interval_api(iv)
    return out, (iv[0], iv[1])


def gapped(m, n, gap, seed=0):
    """U diag(1, ..., 1, gap) V^T -- one singular value placed on purpose."""
    rng = np.random.default_rng(1000 + seed)
    U, _ = np.linalg.qr(rng.standard_normal((m, n)))
    V, _ = np.linalg.qr(rng.standard_normal((n, n)))
    s = np.ones(n)
    s[-1] = gap
    return U @ np.diag(s) @ V.T


print("a singular value above the window leaves a point rank")
for m, n in SHAPES:
    for gap in ABOVE:
        A = gapped(m, n, gap)
        out, _ = classify(A, A @ np.ones(n))
        check(out[STATUS] == UNIQUE and out[RANK] == n
              and out[RANK_LO] == n and out[RANK_HI] == n
              and out[CERTAINTY] == DETERMINISTIC,
              f"{m}x{n} gap {gap:.0e}: deterministic UNIQUE at rank {n} "
              f"(got {NAME[int(out[STATUS])]} [{int(out[RANK_LO])},"
              f"{int(out[RANK_HI])}])")

print()
print("a singular value inside the window is refused, with an interval")
for m, n in SHAPES:
    for gap in BAND:
        A = gapped(m, n, gap)
        out, iv = classify(A, A @ np.ones(n))
        st = int(out[STATUS])
        lo, hi = int(out[RANK_LO]), int(out[RANK_HI])
        check(st == UNDECIDABLE,
              f"{m}x{n} gap {gap:.0e}: UNDECIDABLE (got {NAME[st]})")
        check(lo <= n - 1 and hi >= n and hi <= min(m, n),
              f"{m}x{n} gap {gap:.0e}: interval [{lo},{hi}] brackets "
              f"both candidate ranks")
        check(hi > lo, f"{m}x{n} gap {gap:.0e}: no point rank is claimed")
        check(iv != (-1, -1) and 0 <= iv[0] <= iv[1] <= min(m, n),
              f"{m}x{n} gap {gap:.0e}: core interval reported and ordered {iv}")

print()
print("a singular value below the window makes the direction absent")
for m, n in SHAPES:
    for gap in BELOW:
        A = gapped(m, n, gap)
        out, _ = classify(A, A @ np.ones(n))
        st = int(out[STATUS])
        check(st == INFINITE and out[RANK] == n - 1,
              f"{m}x{n} gap {gap:.0e}: INFINITE at rank {n - 1} "
              f"(got {NAME[st]} rank {int(out[RANK])})")

print()
print("the verdict does not depend on the scale of the system")
for gap in ABOVE[:1] + BAND + BELOW[:1]:
    A = gapped(400, 32, gap)
    b = A @ np.ones(32)
    base = int(classify(A, b)[0][STATUS])
    for e in (-40, -12, 12, 40):
        f = 2.0 ** e
        st = int(classify(A * f, b * f)[0][STATUS])
        check(st == base,
              f"gap {gap:.0e} scaled by 2^{e:+d}: {NAME[base]} unchanged "
              f"(got {NAME[st]})")

print()
print("the verdict does not depend on the sketch seed")
for gap in BAND:
    A = gapped(400, 32, gap)
    b = A @ np.ones(32)
    seen = {int(classify(A, b, seed=s)[0][STATUS]) for s in (1, 2, 3, 17, 99)}
    check(seen == {UNDECIDABLE},
          f"gap {gap:.0e}: five seeds agree "
          f"({', '.join(NAME[s] for s in sorted(seen))})")

print()
print("an unresolved rank never yields a consistency verdict")
for m, n in SHAPES:
    for gap in BAND:
        A = gapped(m, n, gap)
        b = A @ np.ones(n)
        b[5] += 1.0
        st = int(classify(A, b)[0][STATUS])
        check(st in (UNDECIDABLE, INCONSISTENT),
              f"{m}x{n} gap {gap:.0e} with a contradictory row: "
              f"{NAME[st]} is not a consistent verdict")

print()
print("the boundary is a property of the data, not of a row ordering")
for gap in BAND:
    A = gapped(400, 32, gap)
    b = A @ np.ones(32)
    perm = np.random.default_rng(7).permutation(400)
    st_a = int(classify(A, b)[0][STATUS])
    st_b = int(classify(A[perm], b[perm])[0][STATUS])
    check(st_a == st_b,
          f"gap {gap:.0e}: {NAME[st_a]} survives a row permutation "
          f"(got {NAME[st_b]})")

print()
if failures:
    print(f"FAILED: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ok: the compressed-core rank boundary separates decide, refuse and "
      "discard, and the refusal is stable under scale, seed and ordering")
