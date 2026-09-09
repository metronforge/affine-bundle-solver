#!/usr/bin/env python3
"""
suitesparse_bench.py -- the router against LAPACK on real matrices.

Every timing in the manuscript comes from generated systems, which invites the
obvious objection. This runs the same comparison on matrices from the
SuiteSparse Matrix Collection, whose entries carry a recorded problem domain.

Three things this script is careful about, each because an earlier version of
it was not:

  SELECTION.  Taking whatever the index returned first gave 34 of 40 matrices
  from one family of simplicial boundary maps.  Capping per collection group
  did not help: JGD_Homology, JGD_Relat, JGD_GL7d and JGD_Taha are four groups
  holding that same family.  Selection now asks the collection for its own
  dense entries, falling back to density measured from nnz.

  SHAPE.  The solver assumes neither consistency, nor full rank, nor
  uniqueness, so it classifies tall, square and wide systems alike.  All three
  are run.  Only the SPEED claim is restricted to overdetermined systems, and
  the summary keeps that separate rather than averaging over shapes the
  manuscript makes no timing claim about.

  COMPARABILITY.  An INCONSISTENT verdict can be reached after a handful of
  rows: the router stops once a contradiction is established, while dgelsy
  goes on to compute a least-squares minimizer.  Those are different
  questions.  Seen on HB/well1033, where rank 3 of 320 came back at 36.85x.
  Such rows are marked and excluded from the speed summary.

Losing cases stay in the table, sorted first.  A benchmark that reports only
the wins is not evidence, and the grouped-row regression is already known.

Usage:

    pip install ssgetpy
    python3 experiments/suitesparse_bench.py --survey        # index only
    OMP_NUM_THREADS=1 python3 experiments/suitesparse_bench.py \\
        --limit 60 --out results/suitesparse.csv

Run from the repository root after build.sh.  Single-threaded BLAS is the
comparison the manuscript makes; SciPy's BLAS must be pinned from the
environment, which is why the command line above does it explicitly.
"""
import argparse
import csv
import ctypes
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
    fn()                                # warm up; the first call pays faults
    ts = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts)


def density_of(e):
    return e.nnz / max(e.rows * e.cols, 1)


def shape_of(m, n):
    return ("overdetermined" if m > n else
            "square" if m == n else "underdetermined")


def select(limit, max_cells, min_density, min_lean, per_kind):
    """Dense matrices of any shape, big enough to time and small enough to
    hold densely.

    The collection's own dense filter is asked for first: it reflects how the
    collection classifies its entries rather than a threshold picked here.  If
    that yields nothing, density is computed from nnz and the threshold
    applies.  Which of the two produced the sample is printed, because they
    are not the same statement about the data.
    """
    try:
        import ssgetpy
    except ImportError:
        sys.exit("ssgetpy is not installed: pip install ssgetpy")

    source = "kind='dense'"
    try:
        pool = list(ssgetpy.search(kind="dense", limit=10000))
    except Exception as exc:                                # noqa: BLE001
        print(f"  kind='dense' not usable ({exc}); measuring density instead")
        pool = []
    pool = [e for e in pool if not getattr(e, "is_sparse", False)]

    if not pool:
        source = f"density >= {min_density:g} measured from nnz"
        pool = [e for e in ssgetpy.search(limit=20000, dtype="real")
                if density_of(e) >= min_density]

    seen = {}
    out = []
    for e in sorted(pool, key=lambda x: -density_of(x)):
        m, n = e.rows, e.cols
        if m < 8 or n < 8 or m * n > max_cells:
            continue
        if m != n and max(m / n, n / m) < min_lean:
            continue
        kind = (getattr(e, "kind", "") or "").lower()
        if seen.get(kind, 0) >= per_kind:
            continue
        seen[kind] = seen.get(kind, 0) + 1
        out.append(e)
        if len(out) >= limit:
            break

    shapes = {}
    for e in out:
        s = shape_of(e.rows, e.cols)
        shapes[s] = shapes.get(s, 0) + 1
    print(f"  selected {len(out)} matrices by {source}")
    if shapes:
        print("  by shape: " + ", ".join(f"{k} {v}"
                                         for k, v in sorted(shapes.items())))
    if len(out) < 20:
        print("  small sample; lower --min-density or --min-lean, or raise "
              "--max-cells, before reading anything into the summary")
    return out


def dense_system(entry):
    from scipy.io import mmread
    paths = entry.download(format="MM", extract=True)
    d = Path(paths[0] if isinstance(paths, (list, tuple)) else paths)
    d = d if d.is_dir() else d.parent
    mtx = sorted(d.glob("*.mtx"))
    main = [p for p in mtx if not p.name.endswith(("_b.mtx", "_x.mtx"))]
    if not main:
        return None
    raw = mmread(main[0])
    A = np.asarray(raw.todense() if hasattr(raw, "todense") else raw,
                   dtype=np.float64)
    if A.ndim != 2:
        return None

    b = None
    origin = "supplied b"
    bfile = [p for p in mtx if p.name.endswith("_b.mtx")]
    if bfile:
        b = np.asarray(mmread(bfile[0]), dtype=np.float64).ravel()
        if b.size != A.shape[0]:
            b = None
    if b is None:
        # No right-hand side ships with the problem.  A consistent b is built
        # so the classification has a defined answer, and the table records
        # that this was a choice made here rather than a property of the
        # matrix: on such rows the status says more about the construction
        # than about the data.
        rng = np.random.default_rng(20260909)
        b = A @ rng.standard_normal(A.shape[1])
        origin = "b = A x"
    return np.ascontiguousarray(A), np.ascontiguousarray(b), origin


def survey(max_cells, top):
    """What the collection actually holds: density against lean from square.

    A single filter returning nothing does not say which of its conditions was
    the empty one.  Dense matrices tend to be square, so requiring density and
    a tall aspect at once can come back empty while both hold separately, and
    those are different facts about the collection.
    """
    import ssgetpy
    try:
        marked = list(ssgetpy.search(kind="dense", limit=10000))
        print(f"entries the collection itself marks dense: {len(marked)}")
        if marked:
            sh = {}
            for e in marked:
                s = shape_of(e.rows, e.cols)
                sh[s] = sh.get(s, 0) + 1
            print("  by shape: " + ", ".join(f"{k} {v}"
                                             for k, v in sorted(sh.items())))
    except Exception as exc:                                # noqa: BLE001
        print(f"kind='dense' not usable: {exc}")
    print()

    cand = []
    for e in ssgetpy.search(limit=20000, dtype="real"):
        m, n = e.rows, e.cols
        if m < 8 or n < 8:
            continue
        cand.append((density_of(e), m / n, e, m * n <= max_cells))

    dens = (0.5, 0.25, 0.1, 0.05)
    leans = (1.0, 1.5, 2.0, 3.0, 5.0, 10.0)
    print(f"real matrices with m, n >= 8: {len(cand)}")
    print()
    print("counts by density (columns) and lean away from square (rows);")
    print("tall and wide together, since the solver classifies both")
    print("        " + "".join(f"{d:>10g}" for d in dens))
    for a in leans:
        row = [sum(1 for de, ar, _, _ in cand
                   if de >= d and ar != 1 and max(ar, 1 / ar) >= a)
               for d in dens]
        print(f"  >={a:<5g}" + "".join(f"{c:>10d}" for c in row))
    print()
    for d in dens:
        sq = sum(1 for de, ar, _, _ in cand if de >= d and ar == 1)
        print(f"square with density >= {d:<6g} {sq}")
    print()

    cand.sort(key=lambda t: -t[0])
    print(f"densest {top}, any shape:")
    print(f"  {'matrix':<30s} {'kind':<22s} {'m':>7s} {'n':>6s} "
          f"{'shape':<16s} {'density':>8s} {'fits':>5s}")
    for de, ar, e, fits in cand[:top]:
        print(f"  {e.group + '/' + e.name:<30s} "
              f"{(getattr(e, 'kind', '') or '')[:22]:<22s} "
              f"{e.rows:>7d} {e.cols:>6d} {shape_of(e.rows, e.cols):<16s} "
              f"{de:>8.3f} {'yes' if fits else 'no':>5s}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--max-cells", type=int, default=40_000_000)
    ap.add_argument("--min-density", type=float, default=0.25,
                    help="fallback threshold when kind='dense' yields nothing")
    ap.add_argument("--min-lean", type=float, default=1.5,
                    help="how far from square a non-square matrix must be")
    ap.add_argument("--per-kind", type=int, default=12,
                    help="cap on matrices from any one problem domain")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--driver", default="gelsy", choices=["gelsy", "gelsd"])
    ap.add_argument("--out", default="results/suitesparse.csv")
    ap.add_argument("--survey", action="store_true",
                    help="report what the collection holds, and exit")
    args = ap.parse_args()

    if args.survey:
        return survey(args.max_cells, 25)

    from scipy.linalg import lstsq

    lib = load_router()
    rows = []
    for e in select(args.limit, args.max_cells, args.min_density,
                    args.min_lean, args.per_kind):
        try:
            got = dense_system(e)
        except Exception as exc:                            # noqa: BLE001
            print(f"  skip {e.group}/{e.name}: {exc}")
            continue
        if got is None:
            continue
        A, b, origin = got
        m, n = A.shape
        out = np.zeros(11)

        def run_router():
            lib.bsolve_router_meta_api(ptr(A), ptr(b), None, m, n,
                                       1, 2, 2, 20260909, 0, ptr(out))

        def run_lapack():
            lstsq(A, b, lapack_driver=args.driver, check_finite=False)

        try:
            t_r = timed(run_router, args.repeats)
            t_l = timed(run_lapack, args.repeats)
        except Exception as exc:                            # noqa: BLE001
            print(f"  skip {e.group}/{e.name}: {exc}")
            continue

        rows.append({
            "matrix": f"{e.group}/{e.name}",
            "kind": getattr(e, "kind", ""),
            "shape": shape_of(m, n),
            "m": m, "n": n,
            "density": density_of(e),
            "rhs": origin,
            "status": CLS.get(int(out[0]), "?"),
            "rank": int(out[2]),
            "rank_lo": int(out[3]),
            "rank_hi": int(out[4]),
            "router_s": t_r,
            f"{args.driver}_s": t_l,
            "speedup": t_l / t_r if t_r > 0 else float("nan"),
            "comparable": not (int(out[0]) == 3 and int(out[2]) < n // 4),
        })
        r = rows[-1]
        print(f"  {r['matrix']:<30s} {r['shape']:<16s} {m:>7d}x{n:<6d} "
              f"{r['status']:<12s} x{r['speedup']:.2f}")

    if not rows:
        sys.exit("no matrices ran")

    rows.sort(key=lambda r: r["speedup"])
    outp = ROOT / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    comp = [r for r in rows if r["comparable"]]
    early = [r for r in rows if not r["comparable"]]
    supplied = [r for r in rows if r["rhs"] == "supplied b"]
    groups = {r["matrix"].split("/")[0] for r in rows}

    print()
    print(f"{len(rows)} matrices from {len(groups)} collection groups")
    print(f"  {len(supplied)} with a right-hand side supplied by the problem, "
          f"{len(rows) - len(supplied)} with b = A x built here")
    print(f"  {len(early)} excluded from the speed summary: INCONSISTENT "
          f"established early, which is not the question {args.driver} "
          f"answered")
    print()
    for shape in ("overdetermined", "square", "underdetermined"):
        rs = [r for r in comp if r["shape"] == shape]
        if not rs:
            continue
        v = [r["speedup"] for r in rs]
        slower = sum(1 for x in v if x < 1.0)
        note = "" if shape == "overdetermined" else \
            "  (outside the speed claim; run for classification)"
        print(f"{shape}: {len(rs)} matrices, {slower} slower than "
              f"{args.driver}; speedup min {min(v):.2f}, "
              f"median {statistics.median(v):.2f}, max {max(v):.2f}{note}")
    print()
    print("The manuscript claims 20-80x for overdetermined dense systems only.")
    print("Square and underdetermined rows are here because the classification")
    print("applies to them, not because a timing comparison is claimed.")
    print(f"written to {outp}")

    print()
    print("| matrix | kind | shape | m | n | density | rhs | status | rank "
          "| speedup |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        iv = (f"{r['rank']}" if r["rank_lo"] == r["rank_hi"]
              else f"[{r['rank_lo']}, {r['rank_hi']}]")
        sp = (f"{r['speedup']:.2f}" if r["comparable"]
              else f"{r['speedup']:.2f} (early exit)")
        print(f"| {r['matrix']} | {r['kind']} | {r['shape']} | {r['m']} | "
              f"{r['n']} | {r['density']:.2f} | {r['rhs']} | {r['status']} | "
              f"{iv} | {sp} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
