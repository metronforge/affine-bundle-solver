#!/usr/bin/env python3
"""
compare_builds.py -- check that two builds of the router agree on everything
that is supposed to be build-independent.

Why this exists
---------------
build.sh defaults to -march=native, which fixes the instruction set to the
build machine and enables FMA contraction.  Last-bit floating-point results
may therefore legitimately differ between a portable and a native build.

What must NOT differ is the semantic output: the status classification, the
supported rank interval, and the reported rank.  Those are the quantities the
manuscript makes claims about.  If they diverge between builds, the claims are
build-dependent and the paper would need to say so.

Usage:
    python3 tests/compare_builds.py DIR_A DIR_B

Each directory must contain libaffine_bundle_solver.so.
Exit status: 0 = semantic agreement, 1 = divergence.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import numpy as np

DP = ctypes.POINTER(ctypes.c_double)

# Output layout of bsolve_router_meta_api.  Index 7 is wall-clock seconds and
# is excluded from every comparison for obvious reasons.
IDX_STATUS, IDX_CERTAINTY = 0, 1
IDX_RANK, IDX_RANK_LO, IDX_RANK_HI = 2, 3, 4
IDX_RELRES, IDX_RELX = 5, 6
IDX_TIME = 7

SEMANTIC = [IDX_STATUS, IDX_CERTAINTY, IDX_RANK, IDX_RANK_LO, IDX_RANK_HI]
NUMERIC = [IDX_RELRES, IDX_RELX]

STATUS = {0: "UNDETERMINED", 1: "UNIQUE", 2: "INFINITE",
          3: "INCONSISTENT", 4: "FAIL", 5: "UNDECIDABLE"}


def load(directory: str):
    path = Path(directory) / "libaffine_bundle_solver.so"
    if not path.is_file():
        raise SystemExit(f"not found: {path}")
    lib = ctypes.CDLL(str(path))
    lib.bsolve_router_meta_api.argtypes = [
        DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, DP]
    lib.bsolve_router_meta_api.restype = None
    return lib


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def run(lib, A, b, xt, seed):
    m, n = A.shape
    out = np.zeros(11, dtype=np.float64)
    lib.bsolve_router_meta_api(ptr(A), ptr(b), ptr(xt), m, n,
                               1, 2, 2, seed, 0, ptr(out))
    return out


def build_cases(seed=20260907):
    rng = np.random.default_rng(seed)
    cases = []

    def add(name, A, b, x):
        cases.append((name,
                      np.ascontiguousarray(A, dtype=np.float64),
                      np.ascontiguousarray(b, dtype=np.float64),
                      np.ascontiguousarray(x, dtype=np.float64)))

    # overdetermined, full rank
    for m, n in [(2048, 32), (4096, 64), (8192, 128)]:
        A = rng.standard_normal((m, n)); x = rng.standard_normal(n)
        add(f"full_{m}x{n}", A, A @ x, x)

    # overdetermined, rank deficient
    for m, n, r in [(2048, 32, 20), (4096, 64, 40), (8192, 128, 90)]:
        U = rng.standard_normal((m, r)); V = rng.standard_normal((r, n))
        A = U @ V; x = rng.standard_normal(n)
        add(f"rankdef_{m}x{n}r{r}", A, A @ x, x)

    # heavy row redundancy
    for m, n, g in [(4096, 64, 64), (8192, 128, 128)]:
        base = rng.standard_normal((g, n))
        A = base[rng.integers(0, g, m)] * rng.uniform(0.5, 2.0, m)[:, None]
        x = rng.standard_normal(n)
        add(f"grouped_{m}x{n}", A, A @ x, x)

    # inconsistent
    for m, n in [(2048, 32), (4096, 64)]:
        A = rng.standard_normal((m, n)); x = rng.standard_normal(n)
        b = A @ x; b[m // 3] += 1.0
        add(f"inconsistent_{m}x{n}", A, b, x)

    # square and underdetermined -- shapes absent from the manuscript tables
    for m, n in [(256, 256), (512, 512), (128, 512), (256, 1024)]:
        A = rng.standard_normal((m, n)); x = rng.standard_normal(n)
        add(f"shape_{m}x{n}", A, A @ x, x)

    # wide dynamic range in row scaling
    m, n = 4096, 64
    A = rng.standard_normal((m, n))
    A *= np.power(10.0, rng.uniform(-8, 8, m))[:, None]
    x = rng.standard_normal(n)
    add(f"scaled_{m}x{n}", A, A @ x, x)

    return cases


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    a_dir, b_dir = sys.argv[1], sys.argv[2]
    lib_a, lib_b = load(a_dir), load(b_dir)

    cases = build_cases()
    seeds = (12345, 777)

    print("=" * 82)
    print(f"Semantic agreement: {a_dir}  vs  {b_dir}")
    print("=" * 82)
    print("Compared: status, certainty, rank, rank interval (must be identical).")
    print("Reported but not compared: residuals (FMA contraction may move last")
    print("bits), wall-clock time.")
    print()
    print(f"  {'case':<24s} {'status':>12s} {'rank':>5s} "
          f"{'semantic':>9s} {'max |rel diff|':>15s}")
    print("  " + "-" * 72)

    divergences = []
    worst = 0.0

    for name, A, b, x in cases:
        for seed in seeds:
            oa = run(lib_a, A, b, x, seed)
            ob = run(lib_b, A, b, x, seed)

            sem_ok = all(oa[i] == ob[i] for i in SEMANTIC)
            if not sem_ok:
                divergences.append((name, seed, oa.copy(), ob.copy()))

            for i in NUMERIC:
                va, vb = oa[i], ob[i]
                if np.isfinite(va) and np.isfinite(vb):
                    denom = max(abs(va), abs(vb), 1e-300)
                    worst = max(worst, abs(va - vb) / denom)

        print(f"  {name:<24s} {STATUS.get(int(oa[IDX_STATUS]), '?'):>12s} "
              f"{int(oa[IDX_RANK]):>5d} {'yes' if sem_ok else 'NO':>9s} "
              f"{worst:>15.3e}")

    print()
    if divergences:
        print(f"SEMANTIC DIVERGENCE in {len(divergences)} run(s):")
        for name, seed, oa, ob in divergences[:5]:
            print(f"  {name} (seed {seed})")
            print(f"    {a_dir}: status={int(oa[0])} rank={int(oa[2])} "
                  f"interval=[{int(oa[3])},{int(oa[4])}]")
            print(f"    {b_dir}: status={int(ob[0])} rank={int(ob[2])} "
                  f"interval=[{int(ob[3])},{int(ob[4])}]")
        print()
        print("The manuscript's classification claims would be build-dependent.")
        return 1

    print(f"semantic agreement on all {len(cases)} cases x {len(seeds)} seeds")
    print(f"largest relative difference in reported residuals: {worst:.3e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
