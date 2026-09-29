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
import argparse
import hashlib
import json
import sys
from pathlib import Path
from library_paths import library_path

import numpy as np

DP = ctypes.POINTER(ctypes.c_double)

# Output layout of bsolve_router_meta_api.  Index 7 is wall-clock seconds and
# is excluded from every comparison for obvious reasons.
IDX_STATUS, IDX_CERTAINTY = 0, 1
IDX_RANK, IDX_RANK_LO, IDX_RANK_HI = 2, 3, 4
IDX_RELRES, IDX_RELX = 5, 6
IDX_TIME = 7
IDX_FALLBACK, IDX_CLS = 8, 9

# IDX_CLS is compared even though it now equals IDX_STATUS.  While the two
# were allowed to disagree, a build difference that turned UNDECIDABLE into
# FAIL moved only IDX_CLS and this comparison did not look at it, so the one
# divergence that would matter most was the one it could not see.  Keeping it
# in the set costs nothing and makes the two fields required to stay in step.
SEMANTIC = [IDX_STATUS, IDX_CERTAINTY, IDX_RANK, IDX_RANK_LO, IDX_RANK_HI, IDX_CLS]
SEMANTIC_NAMES = ("status", "certainty", "rank", "rank_lo", "rank_hi", "classification")
NUMERIC = [IDX_RELRES, IDX_RELX]

STATUS = {0: "UNDETERMINED", 1: "UNIQUE", 2: "INFINITE",
          3: "INCONSISTENT", 4: "FAIL", 5: "UNDECIDABLE"}


def load(directory: str):
    path = library_path("affine_bundle_solver", directory)
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


def semantic_key(out):
    """The same contract is used for local builds and runner artifacts."""
    values = tuple(out[i] for i in SEMANTIC)
    if any(not np.isfinite(v) or v != int(v) for v in values):
        raise ValueError(f"invalid semantic output: {values}")
    return dict(zip(SEMANTIC_NAMES, map(int, values)))


def snapshot_cases():
    """Exact integer/dyadic inputs: no random distributions or BLAS generation."""
    cases = []
    for name, m, n, rank, inconsistent in [
        ("unique-tall", 48, 8, 8, False),
        ("unique-square", 8, 8, 8, False),
        ("infinite-tall", 48, 8, 6, False),
        ("infinite-wide", 6, 8, 6, False),
        ("inconsistent", 48, 8, 6, True),
        ("zero-compatible", 8, 4, 0, False),
        ("zero-inconsistent", 8, 4, 0, True),
    ]:
        A = np.zeros((m, n), dtype=np.float64)
        for i in range(m - int(inconsistent)):
            for j in range(rank):
                A[i, j] = int(i == j) if i < rank else ((i * 7 + j * 3) % 5 - 2)
        x = np.arange(1, n + 1, dtype=np.float64) / 8
        b = np.sum(A * x, axis=1)
        if inconsistent:
            b[-1] = 1
        cases.append((name, A, b, x))
    # Source-rank ambiguity is intentional; never tune thresholds for agreement.
    for exponent in (-30, -40):
        A = np.diag([1., 0.5, 2.**exponent])
        x = np.ones(3)
        cases.append((f"rank-boundary-{exponent}", A, np.sum(A, axis=1), x))
    return cases


SNAPSHOT_SEEDS = (12345, 777)


def corpus_hash():
    digest = hashlib.sha256()
    for name, *arrays in snapshot_cases():
        digest.update(name.encode())
        for array in arrays:
            digest.update(np.asarray(array, dtype="<f8").tobytes())
    return digest.hexdigest()


def snapshot(directory):
    # Reuse the existing certified ABI binding rather than defining another.
    from certified_binding import Certified
    fast = load(directory)
    cert = ctypes.CDLL(str(library_path("certified_solver", directory)))
    cert.bsolve_certified_api.argtypes = [DP, DP, DP, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int,
        ctypes.POINTER(Certified)]
    cert.bsolve_certified_api.restype = ctypes.c_int
    rows = []
    for name, A, b, x in snapshot_cases():
        for seed in SNAPSHOT_SEEDS:
            out = run(fast, A, b, x, seed)
            result = Certified()
            rc = cert.bsolve_certified_api(ptr(A), ptr(b), ptr(x), *A.shape,
                1, 2, 2, seed, 0, ctypes.byref(result))
            if rc:
                raise ValueError(f"{name}: certified API failed: {rc}")
            rows.append({"case": name, "seed": seed, "router": semantic_key(out),
                "certified_status": result.certified_status,
                "certified_rank": result.rank_estimate,
                "certified_rank_interval": [result.rank_lo, result.rank_hi],
                "accepted_status_mask": result.accepted_status_mask,
                "verification": [result.unique_verifier_code,
                    result.infinite_verifier_code, result.inconsistent_verifier_code],
                "generation": [result.unique_generator_code,
                    result.infinite_generator_code, result.inconsistent_generator_code]})
    return {"schema": 1, "corpus_sha256": corpus_hash(), "cases": rows}


def validate_snapshot(value):
    if set(value) != {"schema", "corpus_sha256", "cases"} or value["schema"] != 1:
        raise ValueError("unsupported snapshot schema")
    if value["corpus_sha256"] != corpus_hash():
        raise ValueError("snapshot corpus mismatch")
    expected = [(name, seed) for name, *_ in snapshot_cases() for seed in SNAPSHOT_SEEDS]
    if [(r["case"], r["seed"]) for r in value["cases"]] != expected:
        raise ValueError("snapshot cases missing, duplicated or reordered")
    for row in value["cases"]:
        if set(row) != {"case", "seed", "router", "certified_status", "certified_rank",
                        "certified_rank_interval", "accepted_status_mask", "verification", "generation"}:
            raise ValueError("snapshot fields mismatch")
        if set(row["router"]) != set(SEMANTIC_NAMES):
            raise ValueError("router contract fields missing")
        scalars = [row["seed"], row["certified_status"], row["certified_rank"],
                   row["accepted_status_mask"], *row["router"].values()]
        for key, size in [("certified_rank_interval", 2), ("verification", 3), ("generation", 3)]:
            if not isinstance(row[key], list) or len(row[key]) != size:
                raise ValueError(f"invalid {key}")
            scalars.extend(row[key])
        if any(type(v) is not int for v in scalars):
            raise ValueError("noninteger semantic field")
    return value


def compare_snapshots(paths):
    if len(paths) < 2:
        raise ValueError("at least two snapshots required")
    snapshots = [validate_snapshot(json.loads(Path(p).read_text())) for p in paths]
    for path, value in zip(paths[1:], snapshots[1:]):
        if value != snapshots[0]:
            for a, b in zip(snapshots[0]["cases"], value["cases"]):
                if a != b:
                    print(f"SEMANTIC DIVERGENCE {paths[0]} vs {path}:\n{a}\n{b}")
            return 1
    print(f"semantic snapshots: PASS ({len(paths)} platforms, {len(snapshots[0]['cases'])} case/seed pairs)")
    return 0


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
    if len(sys.argv) > 1 and sys.argv[1] == "--snapshot":
        parser = argparse.ArgumentParser()
        parser.add_argument("--snapshot", metavar="LIB_DIR", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        value = validate_snapshot(snapshot(args.snapshot))
        Path(args.output).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        print(f"semantic snapshot: {len(value['cases'])} case/seed pairs -> {args.output}")
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--compare-snapshots":
        return compare_snapshots(sys.argv[2:])
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
          f"{'semantic':>9s} {'max |abs diff|':>15s}")
    print("  " + "-" * 72)

    divergences = []
    worst_abs = 0.0
    worst_mag = 0.0

    for name, A, b, x in cases:
        case_abs = 0.0
        case_mag = 0.0
        for seed in seeds:
            oa = run(lib_a, A, b, x, seed)
            ob = run(lib_b, A, b, x, seed)

            sem_ok = semantic_key(oa) == semantic_key(ob)
            if not sem_ok:
                divergences.append((name, seed, oa.copy(), ob.copy()))

            # Compare residuals in ABSOLUTE terms.  A relative comparison of
            # two quantities that are both at machine scale (~1e-15) is
            # meaningless: 1e-15 against 5e-16 is a 50% relative difference
            # and no difference at all in substance.
            for i in NUMERIC:
                va, vb = oa[i], ob[i]
                if np.isfinite(va) and np.isfinite(vb):
                    case_abs = max(case_abs, abs(va - vb))
                    case_mag = max(case_mag, abs(va), abs(vb))

        worst_abs = max(worst_abs, case_abs)
        worst_mag = max(worst_mag, case_mag)
        print(f"  {name:<24s} {STATUS.get(int(oa[IDX_STATUS]), '?'):>12s} "
              f"{int(oa[IDX_RANK]):>5d} {'yes' if sem_ok else 'NO':>9s} "
              f"{case_abs:>15.3e}")

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
    print(f"largest absolute difference in reported residuals: {worst_abs:.3e}")
    print(f"largest residual magnitude seen:                   {worst_mag:.3e}")
    # The magnitude column includes the diagnostic feasibility residual of the
    # inconsistent cases, which is O(1) by construction and not a solution
    # error.  What matters is that the DIFFERENCE between builds stays at
    # machine scale.
    if worst_abs <= 1e-12:
        print("differences are at machine scale; the builds agree numerically "
              "as well as semantically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
