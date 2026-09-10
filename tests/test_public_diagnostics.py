#!/usr/bin/env python3
"""
test_public_diagnostics.py -- the public entry points nothing else calls.

Eight functions are declared in include/affine_bundle/router.h and one in
include/affine_bundle/stream.h that no test, example or experiment in this
repository calls:

    bsolve_router_api                   (the seven-field compatibility layout)
    bsolve_router_diag_api
    bsolve_last_grey_total_api
    bsolve_last_orth_eta_api
    bsolve_last_core_rank_interval_api
    bsolve_last_core_qr_rank_api
    bsolve_fg_counters_api              (called from experiments/, not tests)
    bsolve_fg_counters_reset_api
    abs_stream_solution

Coverage of each is zero.  That is not a coverage problem, it is an unanswered
question: a function declared in a public header and invoked by nothing has
never been shown to work at all, and a caller reading the header is the first
to find out.

The properties checked here are the ones the headers actually promise, not the
fact that the calls return.  Where a promise turned out not to hold, the check
says so rather than being weakened to fit.
"""
import ctypes
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))

DP = ctypes.POINTER(ctypes.c_double)
IP = ctypes.POINTER(ctypes.c_int)
ULLP = ctypes.POINTER(ctypes.c_ulonglong)

ROUTER_ARGS = [DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int,
               ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, DP]

lib.bsolve_router_meta_api.argtypes = ROUTER_ARGS
lib.bsolve_router_api.argtypes = ROUTER_ARGS
lib.bsolve_router_diag_api.argtypes = ROUTER_ARGS + [IP, ctypes.c_int]
lib.bsolve_router_diag_api.restype = ctypes.c_int
lib.bsolve_last_grey_total_api.restype = ctypes.c_int
lib.bsolve_last_orth_eta_api.restype = ctypes.c_double
lib.bsolve_last_core_rank_interval_api.argtypes = [IP]
lib.bsolve_last_core_qr_rank_api.restype = ctypes.c_int
lib.bsolve_fg_counters_api.argtypes = [ULLP]
lib.bsolve_fg_counters_reset_api.argtypes = []

lib.abs_stream_create.argtypes = [ctypes.c_int]
lib.abs_stream_create.restype = ctypes.c_void_p
lib.abs_stream_destroy.argtypes = [ctypes.c_void_p]
lib.abs_stream_insert.argtypes = [ctypes.c_void_p, DP, ctypes.c_double]
lib.abs_stream_insert.restype = ctypes.c_int
lib.abs_stream_status.argtypes = [ctypes.c_void_p, DP]
lib.abs_stream_solution.argtypes = [ctypes.c_void_p, DP]
lib.abs_stream_solution.restype = ctypes.c_int

# router.h layouts
STATUS, CERTAINTY, RANK, RANK_LO, RANK_HI = 0, 1, 2, 3, 4
RELRES, RELX, SECONDS, FALLBACK, CLS, BERR = 5, 6, 7, 8, 9, 10
OUT_LEN = 11
# fill_out: {cls, rank, fallback, accepted_random, seconds, relres, relx}
L_CLS, L_RANK, L_FALLBACK, L_RANDOM, L_SECONDS, L_RELRES, L_RELX = range(7)

UNIQUE, INFINITE, INCONSISTENT, FAIL, UNDECIDABLE = 1, 2, 3, 4, 5
GREY_STORE_MAX = 64          # BS_GREY_STORE_MAX in src/bsolver.c

ABSORB, GROW, DEFER, CONTRA = 0, 1, 2, -1

failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
    print(f"  [{'ok' if ok else 'FAIL'}] {what}")


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def meta(A, b, seed=7, xt=None):
    out = np.zeros(OUT_LEN, dtype=np.float64)
    lib.bsolve_router_meta_api(ptr(A), ptr(b), ptr(xt) if xt is not None else None,
                               A.shape[0], A.shape[1], 1, 2, 2, seed, 0, ptr(out))
    return out


def legacy(A, b, seed=7, xt=None):
    out = np.zeros(7, dtype=np.float64)
    lib.bsolve_router_api(ptr(A), ptr(b), ptr(xt) if xt is not None else None,
                          A.shape[0], A.shape[1], 1, 2, 2, seed, 0, ptr(out))
    return out


def diag(A, b, seed=7, cap=GREY_STORE_MAX):
    out = np.zeros(OUT_LEN, dtype=np.float64)
    rows = (ctypes.c_int * max(cap, 1))()
    rc = lib.bsolve_router_diag_api(ptr(A), ptr(b), None,
                                    A.shape[0], A.shape[1], 1, 2, 2, seed, 0,
                                    ptr(out), rows if cap > 0 else None, cap)
    return out, rc, list(rows)[:min(rc, cap)] if cap > 0 else []


def counters():
    c = (ctypes.c_ulonglong * 3)()
    lib.bsolve_fg_counters_api(c)
    return tuple(c)


def core_interval():
    v = (ctypes.c_int * 2)()
    lib.bsolve_last_core_rank_interval_api(v)
    return v[0], v[1]


def systems():
    """Named systems spanning the three shapes and the refusal band."""
    rng = np.random.default_rng(20260910)
    out = {}

    A = rng.standard_normal((60, 6))
    out["overdetermined full rank"] = (A, A @ np.ones(6))

    A = rng.standard_normal((60, 6))
    A[:, 5] = A[:, 0] + A[:, 1]
    out["overdetermined rank deficient"] = (A, A @ np.ones(6))

    A = rng.standard_normal((40, 5))
    b = A @ np.ones(5)
    b[7] += 1.0
    out["inconsistent"] = (A, b)

    A = rng.standard_normal((12, 12))
    out["square"] = (A, A @ np.ones(12))

    A = rng.standard_normal((6, 20))
    out["underdetermined"] = (A, A @ np.ones(20))

    # A near-dependent row inside the four-decade refusal band, placed in the
    # opening prefix, which is where the router probes the source rows.
    n, m = 8, 40
    A = rng.standard_normal((m, n))
    A[2] = A[0] + 1e-11 * rng.standard_normal(n)
    out["near the band"] = (A, A @ np.ones(n))

    return out


print("bsolve_router_api agrees with bsolve_router_meta_api")
for name, (A, b) in systems().items():
    mo, lo_ = meta(A, b), legacy(A, b)
    agree = (mo[CLS] == lo_[L_CLS] and mo[RANK] == lo_[L_RANK]
             and mo[FALLBACK] == lo_[L_FALLBACK])
    # certainty 2 is exactly the randomised acceptance the legacy layout
    # reports in its own field, outside the two statuses that have no
    # certainty at all.
    if mo[STATUS] not in (FAIL, UNDECIDABLE):
        agree = agree and ((mo[CERTAINTY] == 2) == (lo_[L_RANDOM] == 1))
    check(agree, f"same class, rank, fallback and randomised flag: {name}")

print()
print("non-finite input is rejected at both boundaries, in the right layout")
A = np.ones((10, 3))
A[4, 1] = np.nan
b = np.ones(10)
mo, lo_ = meta(A, b), legacy(A, b)
check(mo[STATUS] == FAIL and lo_[L_CLS] == FAIL, "both entry points return FAIL")
check(mo[CLS] == FAIL and mo[CERTAINTY] == 3,
      "meta FAIL fills out[1] and out[9] with valid codes")
check(mo[RANK] == 0 and mo[RANK_LO] == 0 and mo[RANK_HI] == 0 and mo[SECONDS] == 0,
      "meta FAIL leaves no elapsed time in a rank field")
check(all(math.isnan(mo[i]) for i in (RELRES, RELX, BERR)),
      "meta FAIL exports no residual, error or backward error")

print()
print("bsolve_router_diag_api: same classification, plus the grey buffer")
grey_seen = 0
for name, (A, b) in systems().items():
    mo = meta(A, b)
    do, rc, rows = diag(A, b)
    same = all(mo[i] == do[i] or (math.isnan(mo[i]) and math.isnan(do[i]))
               for i in range(OUT_LEN) if i != SECONDS)
    check(same, f"diag writes the meta vector unchanged: {name}")
    check(0 <= rc <= GREY_STORE_MAX, f"grey count within the buffer: {name} ({rc})")
    check(len(rows) == len(set(rows)), f"grey indices are distinct: {name}")
    check(all(0 <= r < A.shape[0] for r in rows), f"grey indices are source rows: {name}")
    check(lib.bsolve_last_grey_total_api() >= rc,
          f"total grey events include the repeats: {name}")
    grey_seen += rc

A, b = systems()["near the band"]
_, rc_full, _ = diag(A, b, cap=GREY_STORE_MAX)
_, rc_zero, _ = diag(A, b, cap=0)
check(rc_full == rc_zero, "the count does not depend on the caller's buffer")
_, rc_two, rows_two = diag(A, b, cap=2)
check(len(rows_two) == min(rc_two, 2), "at most grey_cap indices are copied")

print()
print("last-call diagnostics are in range")
for name, (A, b) in systems().items():
    meta(A, b)
    lo_i, hi_i = core_interval()
    ok = (lo_i, hi_i) == (-1, -1) or (0 <= lo_i <= hi_i <= min(A.shape))
    check(ok, f"core rank interval ordered and bounded: {name} ({lo_i}, {hi_i})")
    qr = lib.bsolve_last_core_qr_rank_api()
    check(qr == -1 or 0 <= qr <= min(A.shape), f"core QR rank in range: {name} ({qr})")
    eta = lib.bsolve_last_orth_eta_api()
    check(math.isfinite(eta) and eta >= 0.0, f"orthogonality eta finite and >= 0: {name}")

print()
print("formation-guard counters")
lib.bsolve_fg_counters_reset_api()
check(counters() == (0, 0, 0), "reset zeroes all three")
A, b = systems()["overdetermined rank deficient"]
meta(A, b)
c1 = counters()
check(c1[1] <= c1[0], f"escalations do not exceed checks {c1}")
meta(A, b)
c2 = counters()
check(all(c2[i] >= c1[i] for i in range(3)), f"counters accumulate {c1} -> {c2}")
lib.bsolve_fg_counters_reset_api()
check(counters() == (0, 0, 0), "reset works a second time")

print()
print("diagnostics describe the most recent router call")
noisy, quiet = systems()["near the band"], systems()["square"]

meta(*quiet)
reference = lib.bsolve_last_grey_total_api()
meta(*noisy)
after_noisy = lib.bsolve_last_grey_total_api()
meta(*quiet)
check(lib.bsolve_last_grey_total_api() == reference,
      "meta reports the quiet system the same way whatever preceded it "
      f"({after_noisy} then {lib.bsolve_last_grey_total_api()}, reference {reference})")

meta(*noisy)
legacy(*quiet)
after_legacy = lib.bsolve_last_grey_total_api()
check(after_legacy == reference,
      "bsolve_router_api leaves the same grey total as meta on the same system "
      f"(got {after_legacy}, meta gives {reference})")

wide = systems()["near the band"]          # 40 x 8
narrow = systems()["overdetermined full rank"]   # 60 x 6
meta(*wide)
wide_qr = lib.bsolve_last_core_qr_rank_api()
meta(*narrow)
narrow_qr = lib.bsolve_last_core_qr_rank_api()
check(narrow_qr <= min(narrow[0].shape),
      "the core QR rank belongs to the system just classified "
      f"(width-{wide[0].shape[1]} call gave {wide_qr}, "
      f"width-{narrow[0].shape[1]} call gave {narrow_qr})")

print()
print("abs_stream_solution")
rng = np.random.default_rng(4242)
n = 6
rows = rng.standard_normal((n, n))
xstar = rng.standard_normal(n)

s = lib.abs_stream_create(n)
x = np.zeros(n, dtype=np.float64)
for i in range(n):
    lib.abs_stream_insert(s, ptr(rows[i]), float(rows[i] @ xstar))
got = lib.abs_stream_solution(s, ptr(x))
check(got == 1, "an open full-rank stream exports a solution")
res = np.max(np.abs(rows @ x - rows @ xstar)) / (1.0 + np.max(np.abs(rows @ xstar)))
check(res < 1e-10, f"the exported solution satisfies the inserted rows ({res:.2e})")
lib.abs_stream_destroy(s)

s = lib.abs_stream_create(n)
for i in range(3):
    lib.abs_stream_insert(s, ptr(rows[i]), float(rows[i] @ xstar))
got_rank_deficient = lib.abs_stream_solution(s, ptr(x))
check(got_rank_deficient == 1, "a consistent stream of rank < n still exports a point")
sub = rows[:3]
res = np.max(np.abs(sub @ x - sub @ xstar)) / (1.0 + np.max(np.abs(sub @ xstar)))
check(res < 1e-10, f"that point satisfies the rows inserted so far ({res:.2e})")
lib.abs_stream_destroy(s)

s = lib.abs_stream_create(n)
for i in range(n - 1):
    lib.abs_stream_insert(s, ptr(rows[i]), float(rows[i] @ xstar))
rc = lib.abs_stream_insert(s, ptr(rows[0]), float(rows[0] @ xstar) + 1.0)
check(rc == CONTRA, "a contradictory row closes the stream")
x[:] = 12345.0
check(lib.abs_stream_solution(s, ptr(x)) == 0,
      "a closed stream exports no solution")
check(np.all(x == 12345.0), "and does not write into the caller's buffer")
lib.abs_stream_destroy(s)

s = lib.abs_stream_create(n)
for i in range(3):
    lib.abs_stream_insert(s, ptr(rows[i]), float(rows[i] @ xstar))
band = rows[0] + 1e-11 * rng.standard_normal(n)
rc = lib.abs_stream_insert(s, ptr(band), float(band @ xstar))
if rc == DEFER:
    st = np.zeros(OUT_LEN, dtype=np.float64)
    lib.abs_stream_status(s, ptr(st))
    check(st[STATUS] == UNDECIDABLE, "a deferred row makes the status UNDECIDABLE")
    check(lib.abs_stream_solution(s, ptr(x)) == 0,
          "a stream with a deferred row exports no solution")
else:
    print(f"  [skip] the band row was not deferred (rc={rc}); "
          "no deferred-state check made")
lib.abs_stream_destroy(s)

print()
if failures:
    print(f"FAILED: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ok: every public diagnostic entry point behaves as its header states")
