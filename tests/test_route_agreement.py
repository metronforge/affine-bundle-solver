#!/usr/bin/env python3
"""
test_route_agreement.py -- routes selected by a measurement must not disagree.

The router picks its route from quantities computed on the data.  One of those
choices turns on a floating-point measurement rather than a structural
property: the square-LU shortcut is accepted directly when its solution's
backward error is at or below the quality threshold, and discarded in favour
of the global QR route when it is above.  Which side a given system lands on
is a property of that realisation, and near the threshold two systems that
differ by nothing meaningful take entirely different code paths.  It also
means the same system can take different routes on different BLAS builds.

That is only safe if the routes agree.  If crossing a witness-quality
threshold could change the classification, the threshold would have become a
classification rule, which is exactly what this design forbids everywhere
else.

So instead of waiting for the router to land on a route -- which is not
reproducible enough to test -- each route is called directly on the same
system and the verdicts are compared.  Refusal is not disagreement: a route
that returns UNDECIDABLE or FAIL is making a weaker statement, and any route
is entitled to make one.  What may not happen is two routes returning
different decided verdicts, or the same verdict at different ranks.

This also reaches solve_global_qr, which nothing else calls: the router
enters it only on the coin flip above.
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
SIG = [DP, DP, DP] + [ctypes.c_int] * 5 + [ctypes.c_ulonglong, ctypes.c_int, DP]
SIG_STALL = [DP, DP, DP] + [ctypes.c_int] * 6 + [ctypes.c_ulonglong, ctypes.c_int, DP]
for _name in ("bsolve_router_meta_api", "bsolve_global_qr_api",
              "bsolve_block_api", "bsolve_fast_api"):
    getattr(lib, _name).argtypes = SIG
lib.bsolve_auto_qr_api.argtypes = SIG_STALL

# The route wrappers write the seven-field fill_out layout, not the meta one.
L_CLS, L_RANK = 0, 1
STATUS, RANK = 0, 2
UNIQUE, INFINITE, INCONSISTENT, FAIL, UNDECIDABLE = 1, 2, 3, 4, 5
DECIDED = {UNIQUE, INFINITE, INCONSISTENT}
NAME = {UNIQUE: "UNIQUE", INFINITE: "INFINITE", INCONSISTENT: "INCONSISTENT",
        FAIL: "FAIL", UNDECIDABLE: "UNDECIDABLE"}

ROUTES = ["bsolve_global_qr_api", "bsolve_block_api", "bsolve_fast_api",
          "bsolve_auto_qr_api"]

failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
    print(f"  [{'ok' if ok else 'FAIL'}] {what}")


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def router(A, b, seed=3):
    out = np.zeros(11, dtype=np.float64)
    m, n = A.shape
    lib.bsolve_router_meta_api(ptr(A), ptr(b), None, m, n, 1, 2, 2, seed, 0,
                               ptr(out))
    return int(out[STATUS]), int(out[RANK])


def route(name, A, b, seed=3):
    out = np.zeros(7, dtype=np.float64)
    m, n = A.shape
    fn = getattr(lib, name)
    if name == "bsolve_auto_qr_api":
        fn(ptr(A), ptr(b), None, m, n, 1, 2, 2, 1, seed, 0, ptr(out))
    else:
        fn(ptr(A), ptr(b), None, m, n, 1, 2, 2, seed, 0, ptr(out))
    return int(out[L_CLS]), int(out[L_RANK])


def spectrum(m, n, cond, data_seed):
    rng = np.random.default_rng(data_seed)
    U, _ = np.linalg.qr(rng.standard_normal((m, n)))
    V, _ = np.linalg.qr(rng.standard_normal((n, n)))
    return U @ np.diag(np.logspace(0, -np.log10(cond), n)) @ V.T


def one_gap(m, n, gap, data_seed):
    rng = np.random.default_rng(data_seed)
    U, _ = np.linalg.qr(rng.standard_normal((m, n)))
    V, _ = np.linalg.qr(rng.standard_normal((n, n)))
    s = np.ones(n)
    s[-1] = gap
    return U @ np.diag(s) @ V.T


def systems():
    for ds in (1, 2, 3):
        for m, n in [(300, 64), (200, 200), (64, 64), (800, 192)]:
            for cond in (1e1, 1e3, 1e6):
                yield f"cond {cond:.0e} {m}x{n} d{ds}", spectrum(m, n, cond, ds)
            for gap in (1e-10, 1e-13, 0.0):
                yield f"gap {gap:.0e} {m}x{n} d{ds}", one_gap(m, n, gap, ds)
    # The shape where the router's own square-LU shortcut is measured to fall
    # on both sides of the quality threshold depending on the realisation.
    for ds in (2, 9):
        yield f"cond 1e+03 1024x512 d{ds}", spectrum(1024, 512, 1e3, ds)


checked = 0
for name, A in systems():
    n = A.shape[1]
    for tag, b in (("consistent", A @ np.ones(n)),
                   ("contradictory", A @ np.ones(n) + np.eye(A.shape[0])[0])):
        verdicts = {"router": router(A, b)}
        for r in ROUTES:
            verdicts[r] = route(r, A, b)
        decided = {k: v for k, v in verdicts.items() if v[0] in DECIDED}
        checked += 1

        shown = "  ".join(
            f"{k.replace('bsolve_', '').replace('_api', '')}="
            f"{NAME.get(v[0], v[0])}/{v[1]}" for k, v in verdicts.items())
        statuses = {v[0] for v in decided.values()}
        ranks = {v[1] for v in decided.values()}
        check(len(statuses) <= 1 and len(ranks) <= 1,
              f"{name} {tag}: {len(decided)} decided verdicts agree  [{shown}]")

print()
print(f"{checked} systems x {len(ROUTES) + 1} routes")
if failures:
    print(f"FAILED: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ok: no two routes return contradictory decided verdicts, so the "
      "measurement that selects a route cannot select a classification")
