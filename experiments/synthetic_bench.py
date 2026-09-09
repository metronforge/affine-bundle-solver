#!/usr/bin/env python3
"""
synthetic_bench.py -- the manuscript's own claims, checked one by one.

The SuiteSparse run (docs/suitesparse-findings.md) showed that a sparse
collection cannot test a claim about dense overdetermined systems: its dense
subset holds one such matrix, 32 x 14. Real data covers the classification;
the speed and conditioning claims need generated systems, and generated
systems invite the objection that whoever generated them chose the answer.

So this script does not report timings. It states each claim the manuscript
makes, generates the family that claim is about, measures, and says whether
the measurement lands inside the claimed range. A family that falls outside
is printed as a miss and counted, because a bench that can only confirm is
not a check.

The claims, from the performance table and the status model:

  tall            overdetermined m >> n           20-80x, median about 22x
  tall_grouped    overdetermined, grouped rows    may be slower; 0.56x seen
  square          square systems                  0.6-0.9x
  wide            underdetermined                 0.24-0.43x
  wide_extreme    underdetermined, n/m >> 1       no claim; 0.02x measured on
                                                  LPnetlib/lp_fit2d at n/m=420
  cond_*          prescribed condition number     UNIQUE with a witness at or
                                                  below ABS_QUALITY_THRESHOLD
  rank_deficient  exact rank r < n, consistent    INFINITE
  inconsistent    b off the column space          INCONSISTENT
  near_transition perturbation inside the band    UNDECIDABLE, rank interval
                  [1e-13, 1e-9]                   wider than a point

Usage:

    OMP_NUM_THREADS=1 python3 experiments/synthetic_bench.py \\
        --out results/synthetic.csv

Run from the repository root after build.sh, with BLAS pinned to one thread:
that is the comparison the manuscript makes.
"""
import argparse
import csv
import ctypes
import math
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))

DP = ctypes.POINTER(ctypes.c_double)
CLS = {0: "UNDETERMINED", 1: "UNIQUE", 2: "INFINITE", 3: "INCONSISTENT",
       4: "FAIL", 5: "UNDECIDABLE"}
QUALITY_THRESHOLD = 1e-14      # ABS_QUALITY_THRESHOLD in router.h


def load_router():
    lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))
    lib.bsolve_router_meta_api.argtypes = [
        DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, DP]
    lib.bsolve_router_meta_api.restype = None
    return lib


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def timed(fn, repeats):
    fn()
    ts = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts)


# ---------------------------------------------------------------------------
# Generators. Each returns (A, b, note).
# ---------------------------------------------------------------------------

def gen_tall(rng, m, n):
    A = rng.standard_normal((m, n))
    return A, A @ rng.standard_normal(n), ""


def gen_tall_grouped(rng, m, n):
    """Rows drawn from few directions with small spread.

    This is the family the performance table already reports as a loss. It is
    here so the loss is reproduced rather than assumed: a claimed weakness
    that quietly stopped being one would matter as much as a claimed strength
    that is not there.
    """
    k = max(4, n // 8)
    base = rng.standard_normal((k, n))
    idx = rng.integers(0, k, size=m)
    A = base[idx] + 1e-6 * rng.standard_normal((m, n))
    return A, A @ rng.standard_normal(n), f"{k} row groups"


def gen_square(rng, n, _unused=None):
    A = rng.standard_normal((n, n))
    return A, A @ rng.standard_normal(n), ""


def gen_wide(rng, m, n):
    A = rng.standard_normal((m, n))
    return A, A @ rng.standard_normal(n), ""


def gen_cond(rng, m, n, kappa):
    """A = U diag(s) V^T with singular values spanning exactly kappa."""
    U, _ = np.linalg.qr(rng.standard_normal((m, n)))
    V, _ = np.linalg.qr(rng.standard_normal((n, n)))
    s = np.logspace(0, -math.log10(kappa), n)
    A = (U * s) @ V.T
    return A, A @ rng.standard_normal(n), f"cond {kappa:.0e}"


def gen_rank_deficient(rng, m, n, r):
    A = rng.standard_normal((m, r)) @ rng.standard_normal((r, n))
    return A, A @ rng.standard_normal(n), f"exact rank {r}"


def gen_inconsistent(rng, m, n):
    A = rng.standard_normal((m, n))
    b = A @ rng.standard_normal(n)
    b[m // 3] += 1.0                    # m >> n: one row cannot be absorbed
    return A, b, "b pushed off the column space"


def gen_near_transition(rng, m, n, eps):
    """A column repeated with a perturbation inside the refusal band.

    Between ABS_DEPENDENCE_THRESHOLD and ABS_GROWTH_THRESHOLD neither
    dependence nor independence is established, and the answer is a rank
    interval rather than a point. That is the outcome the status model exists
    for, so it belongs in a table of the manuscript's claims.
    """
    A = rng.standard_normal((m, n))
    A[:, -1] = A[:, 0] * (1.0 + eps * rng.standard_normal(m))
    return A, A @ rng.standard_normal(n), f"eps {eps:.0e}"


# ---------------------------------------------------------------------------
# Cases: family, claim, generator, expectation.
# speed=(lo, hi) checks the ratio; status=... checks the classification.
# ---------------------------------------------------------------------------

def build_cases(rng, scale, large):
    s = scale
    C = []
    # Aspect stays high on purpose. The claim is about m >> n, and an earlier
    # version included a 6000 x 3000 case whose aspect is 2: measuring the
    # m >> n range against it says nothing about the claim.
    for n, aspect in ((32, 250), (64, 120), (128, 60)):
        m = int(n * aspect * s)
        C.append(dict(family="tall", claim="20-80x on m >> n",
                      gen=lambda r, m=m, n=n: gen_tall(r, m, n),
                      m=m, n=n, speed=(20.0, 80.0)))
    for n in (64, 128):
        m = int(n * 120 * s)
        # Recorded, not checked. The manuscript reports 0.56x on
        # "overdetermined with grouped rows" without saying how the grouping
        # was built, and this generator is a guess at it: rows drawn from a
        # few directions with small spread. It comes out FASTER than dgelsy,
        # so either the guess is wrong or the regression has a narrower cause.
        # Asserting a claim against a generator that may not be the one it was
        # measured on would make the bench lie in the confident direction.
        C.append(dict(family="tall_grouped",
                      claim="0.56x reported; generator unconfirmed",
                      gen=lambda r, m=m, n=n: gen_tall_grouped(r, m, n),
                      m=m, n=n, speed=None))
    for n in (256, 512):
        C.append(dict(family="square", claim="0.6-0.9x on square",
                      gen=lambda r, n=n: gen_square(r, n),
                      m=n, n=n, speed=(0.6, 0.9)))
    for m, n in ((128, 512), (256, 2048)):
        C.append(dict(family="wide", claim="0.24-0.43x underdetermined",
                      gen=lambda r, m=m, n=n: gen_wide(r, m, n),
                      m=m, n=n, speed=(0.24, 0.43)))
    C.append(dict(family="wide_extreme", claim="no claim; 0.02x seen at n/m=420",
                  gen=lambda r: gen_wide(r, 32, 12800),
                  m=32, n=12800, speed=None))
    for kappa in (1e2, 1e8, 1e14):
        m, n = int(4000 * s), 64
        C.append(dict(family=f"cond_{kappa:.0e}",
                      claim="UNIQUE with berr <= 1e-14, or declines",
                      gen=lambda r, m=m, n=n, k=kappa: gen_cond(r, m, n, k),
                      m=m, n=n, status="UNIQUE", quality=True))
    C.append(dict(family="rank_deficient", claim="INFINITE",
                  gen=lambda r: gen_rank_deficient(r, int(4000 * s), 64, 40),
                  m=int(4000 * s), n=64, status="INFINITE"))
    C.append(dict(family="inconsistent", claim="INCONSISTENT",
                  gen=lambda r: gen_inconsistent(r, int(4000 * s), 64),
                  m=int(4000 * s), n=64, status="INCONSISTENT"))
    # Large systems. Everything above keeps n at 128 or below for the timed
    # families, which leaves the regime a user is most likely to care about
    # untested: the manuscript's numbers were taken on narrow systems and
    # nothing said they carry to wide ones. These are 2000 equations and up,
    # with n in the thousands, and they dominate the runtime of this script.
    # Skip with --no-large when iterating on something else.
    if large:
        for m, n, fam, claim, sp in (
                (8000, 2000, "tall_large", "20-80x on m >> n", (20.0, 80.0)),
                (20000, 2000, "tall_large", "20-80x on m >> n", (20.0, 80.0)),
                (2000, 2000, "square_large", "0.6-0.9x on square", (0.6, 0.9)),
                (2000, 8000, "wide_large", "0.24-0.43x underdetermined",
                 (0.24, 0.43))):
            C.append(dict(family=fam, claim=claim,
                          gen=lambda r, m=m, n=n: (gen_square(r, n) if m == n
                                                   else gen_tall(r, m, n)),
                          m=m, n=n, speed=sp))
        # Conditioning at scale: the quality invariant is the one claim that
        # could plausibly weaken with n, since the backward error grows about
        # like n * eps and the threshold does not move.
        for kappa in (1e8, 1e14):
            C.append(dict(family=f"cond_large_{kappa:.0e}",
                          claim="UNIQUE with berr <= 1e-14, or declines",
                          gen=lambda r, k=kappa: gen_cond(r, 6000, 2000, k),
                          m=6000, n=2000, status="UNIQUE", quality=True))
        C.append(dict(family="rank_deficient_large", claim="INFINITE",
                      gen=lambda r: gen_rank_deficient(r, 6000, 2000, 1500),
                      m=6000, n=2000, status="INFINITE"))
        C.append(dict(family="near_transition_large",
                      claim="UNDECIDABLE with a rank interval",
                      gen=lambda r: gen_near_transition(r, 6000, 2000, 1e-11),
                      m=6000, n=2000, status="UNDECIDABLE", interval=True))

    for eps in (1e-12, 1e-10):
        C.append(dict(family="near_transition",
                      claim="UNDECIDABLE with a rank interval",
                      gen=lambda r, e=eps: gen_near_transition(r, 1500, 12, e),
                      m=1500, n=12, status="UNDECIDABLE", interval=True))
    return C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0,
                    help="shrink or grow the timed families")
    ap.add_argument("--no-large", action="store_true",
                    help="skip the 2000-equation families; they dominate the run")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20260909)
    ap.add_argument("--driver", default="gelsy", choices=["gelsy", "gelsd"])
    ap.add_argument("--out", default="results/synthetic.csv")
    args = ap.parse_args()

    from scipy.linalg import lstsq, solve

    lib = load_router()
    rng = np.random.default_rng(args.seed)

    # Process-level warm up, before anything is timed.
    #
    # The per-case warm-up inside timed() does not cover costs paid once per
    # process: the OpenMP thread pool, LAPACK workspace queries, the first
    # touch of freshly mapped pages. Without this the FIRST case measured
    # absurdly, and differently on different machines -- 0.43x on one and
    # 15.79x on another for the same 8000x32 system, which is not a spread any
    # algorithm produces. Whatever runs first was paying for the process.
    _A = np.ascontiguousarray(rng.standard_normal((512, 32)))
    _b = np.ascontiguousarray(_A @ rng.standard_normal(32))
    _o = np.zeros(11)
    for _ in range(3):
        lib.bsolve_router_meta_api(ptr(_A), ptr(_b), None, 512, 32,
                                   1, 2, 2, 1, 0, ptr(_o))
        lstsq(_A, _b, lapack_driver=args.driver, check_finite=False)
        solve(_A[:32], _b[:32], check_finite=False)

    rows = []

    for c in build_cases(rng, args.scale, not args.no_large):
        A, b, note = c["gen"](rng)
        A = np.ascontiguousarray(A)
        b = np.ascontiguousarray(b)
        m, n = A.shape
        out = np.zeros(11)

        def run_router():
            lib.bsolve_router_meta_api(ptr(A), ptr(b), None, m, n,
                                       1, 2, 2, 20260909, 0, ptr(out))

        t_r = timed(run_router, args.repeats)
        # The baseline is not the same routine for every shape, and using one
        # for all of them invalidates the comparison: an early run measured
        # square systems against gelsy and got 2.5x where the manuscript
        # claims 0.6-0.9x, purely because the manuscript compares square
        # against LU. gelsy is QR with column pivoting and costs far more.
        if m == n:
            baseline = "dgesv (LU)"
            run_baseline = lambda: solve(A, b, check_finite=False)
        else:
            baseline = args.driver
            run_baseline = lambda: lstsq(A, b, lapack_driver=args.driver,
                                         check_finite=False)
        t_l = timed(run_baseline, args.repeats)
        ratio = t_l / t_r if t_r > 0 else float("nan")
        status = CLS.get(int(out[0]), "?")
        lo, hi = int(out[3]), int(out[4])
        berr = out[10]

        verdict, measured = "-", ""
        if c.get("speed"):
            a, z = c["speed"]
            measured = f"{ratio:.2f}x"
            verdict = "within" if a <= ratio <= z else "OUTSIDE"
        elif c.get("status"):
            measured = status
            ok = status == c["status"]
            if c.get("quality"):
                # The invariant is one-sided. At extreme conditioning the
                # router is entitled to decline, and does: at kappa 1e14 it
                # returns UNDECIDABLE, which is the status model working
                # rather than a missed claim. What must never happen is
                # UNIQUE carrying a witness above the threshold.
                if status == "UNIQUE":
                    ok = np.isfinite(berr) and berr <= QUALITY_THRESHOLD
                    measured = f"UNIQUE, berr {berr:.2e}"
                else:
                    ok = status == "UNDECIDABLE"
                    measured = f"{status} (declined)"
            if ok and c.get("interval"):
                ok = hi > lo
                measured = f"{status} [{lo}, {hi}]"
            verdict = "holds" if ok else "MISSED"
        else:
            measured = f"{ratio:.2f}x"
            verdict = "recorded"

        rows.append(dict(family=c["family"], claim=c["claim"],
                         baseline=baseline, m=m, n=n,
                         note=note, status=status, rank=int(out[2]),
                         rank_lo=lo, rank_hi=hi, berr=berr,
                         router_s=t_r, lapack_s=t_l, speedup=ratio,
                         measured=measured, verdict=verdict))
        print(f"  {c['family']:<16s} {m:>7d}x{n:<6d} {measured:<26s} "
              f"{verdict}")

    outp = ROOT / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    misses = [r for r in rows if r["verdict"] in ("OUTSIDE", "MISSED")]
    checked = [r for r in rows if r["verdict"] != "recorded"]
    print()
    print(f"{len(checked)} claims checked, {len(misses)} not reproduced")
    for r in misses:
        print(f"  {r['family']}: claimed {r['claim']}, measured "
              f"{r['measured']}")
    print(f"written to {outp}")

    print()
    print("| family | claim | m | n | measured | verdict |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['family']} | {r['claim']} | {r['m']} | {r['n']} | "
              f"{r['measured']} | {r['verdict']} |")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
