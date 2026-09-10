#!/usr/bin/env python3
"""
test_blockprefix_guard.py -- the formation-guard rank gate.

certified_proof_rank_lo is the gate that decides whether a rank proposed from
compressed evidence may be accepted as a source rank.  It re-derives the
bound from the retained proof rows and returns 0 when it cannot certify the
proposal, which is conservative by construction: compressed evidence may not
raise source rank.  Three of its four call sites are inside
solve_blockprefix_qr.

Nothing reached it.  The route needs all of:

  * the opening source prefix growing at every row, and
  * a leading square block too ill-conditioned for the square-LU shortcut
    (rcond < 1e-8), so that shortcut declines rather than answering, and
  * n >= 192, which is where solve_router prefers the block-prefix route.

A single spectral gap satisfies the middle condition and the width supplies
the rest.  These systems are large, so the shapes here are the smallest that
still take the route.

What is checked is the separation the gate exists to enforce, not that it
runs: the router must not claim a rank the guard cannot certify, and must not
convert an unresolved rank into a verdict about consistency in either
direction.
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
lib.bsolve_router_meta_api.argtypes = ([DP, DP, DP] + [ctypes.c_int] * 5
                                       + [ctypes.c_ulonglong, ctypes.c_int, DP])

STATUS, CERTAINTY, RANK, RANK_LO, RANK_HI = 0, 1, 2, 3, 4
UNIQUE, INFINITE, INCONSISTENT, FAIL, UNDECIDABLE = 1, 2, 3, 4, 5
DETERMINISTIC, RANDOMISED, NO_CERTAINTY = 1, 2, 3
NAME = {UNIQUE: "UNIQUE", INFINITE: "INFINITE", INCONSISTENT: "INCONSISTENT",
        FAIL: "FAIL", UNDECIDABLE: "UNDECIDABLE"}

# n >= 192 is the width at which solve_router prefers the block-prefix route.
SHAPES = [(800, 192), (2000, 256)]
ABOVE = (1e-6, 1e-8)
BAND = (1e-10, 1e-11, 1e-12)
BELOW = (1e-14, 0.0)

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
    return (int(out[STATUS]), int(out[CERTAINTY]), int(out[RANK]),
            int(out[RANK_LO]), int(out[RANK_HI]))


def gapped(m, n, gap, seed=0):
    rng = np.random.default_rng(100 + seed)
    U, _ = np.linalg.qr(rng.standard_normal((m, n)))
    V, _ = np.linalg.qr(rng.standard_normal((n, n)))
    s = np.ones(n)
    s[-1] = gap
    return U @ np.diag(s) @ V.T


def broken(A, b):
    c = b.copy()
    c[5] += 1.0
    return c


print("above the window the guard certifies the full rank")
for m, n in SHAPES:
    for gap in ABOVE:
        A = gapped(m, n, gap)
        b = A @ np.ones(n)
        st, ce, rk, lo, hi = classify(A, b)
        check(st == UNIQUE and ce == DETERMINISTIC and (lo, hi) == (n, n),
              f"{m}x{n} gap {gap:.0e}: deterministic UNIQUE at [{n},{n}] "
              f"(got {NAME[st]} c{ce} [{lo},{hi}])")
        st, ce, rk, lo, hi = classify(A, broken(A, b))
        check(st == INCONSISTENT and ce == DETERMINISTIC,
              f"{m}x{n} gap {gap:.0e} contradictory: deterministic "
              f"INCONSISTENT (got {NAME[st]} c{ce})")

print()
print("inside the window the guard declines and no rank is claimed")
for m, n in SHAPES:
    for gap in BAND:
        A = gapped(m, n, gap)
        b = A @ np.ones(n)
        st, ce, rk, lo, hi = classify(A, b)
        check(st == UNDECIDABLE and ce == NO_CERTAINTY,
              f"{m}x{n} gap {gap:.0e}: UNDECIDABLE with no certainty "
              f"(got {NAME[st]} c{ce})")
        check(lo <= n - 1 and hi >= n and hi <= min(m, n) and hi > lo,
              f"{m}x{n} gap {gap:.0e}: interval [{lo},{hi}] brackets both "
              f"candidate ranks and is not a point")

print()
print("an unresolved rank blocks a consistency verdict in both directions")
for m, n in SHAPES:
    for gap in BAND:
        A = gapped(m, n, gap)
        b = A @ np.ones(n)
        st, _, _, _, _ = classify(A, broken(A, b))
        check(st == UNDECIDABLE,
              f"{m}x{n} gap {gap:.0e} contradictory: still UNDECIDABLE, "
              f"compressed evidence does not certify a source contradiction "
              f"(got {NAME[st]})")

print()
print("below the window the direction is absent and the verdict is decided")
for m, n in SHAPES:
    for gap in BELOW:
        A = gapped(m, n, gap)
        b = A @ np.ones(n)
        st, ce, rk, lo, hi = classify(A, b)
        check(st == INFINITE and rk == n - 1,
              f"{m}x{n} gap {gap:.0e}: INFINITE at rank {n - 1} "
              f"(got {NAME[st]} rank {rk})")
        st, ce, rk, lo, hi = classify(A, broken(A, b))
        check(st == INCONSISTENT and ce == DETERMINISTIC and (lo, hi) == (rk, rk),
              f"{m}x{n} gap {gap:.0e} contradictory: deterministic "
              f"INCONSISTENT at a point rank (got {NAME[st]} c{ce} [{lo},{hi}])")

print()
print("the refusal is a property of the data")
m, n = SHAPES[0]
rng = np.random.default_rng(7)
for gap in BAND:
    A = gapped(m, n, gap)
    b = A @ np.ones(n)
    base = classify(A, b)[0]

    seen = {classify(A, b, seed=s)[0] for s in (1, 5, 23)}
    check(seen == {base},
          f"gap {gap:.0e}: three sketch seeds agree "
          f"({', '.join(NAME[s] for s in sorted(seen))})")

    perm = rng.permutation(m)
    check(classify(A[perm], b[perm])[0] == base,
          f"gap {gap:.0e}: {NAME[base]} survives a row permutation")

    for e in (-30, 30):
        f = 2.0 ** e
        check(classify(A * f, b * f)[0] == base,
              f"gap {gap:.0e} scaled by 2^{e:+d}: {NAME[base]} unchanged")

print()
if failures:
    print(f"FAILED: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ok: the formation-guard gate refuses an uncertifiable rank and keeps "
      "an unresolved rank out of every consistency verdict")
