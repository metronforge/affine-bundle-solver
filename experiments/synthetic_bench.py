#!/usr/bin/env python3
"""
synthetic_bench.py -- the manuscript's own claims, checked one by one.

The SuiteSparse run (docs/suitesparse-findings.md) showed that a sparse
collection cannot test a claim about dense overdetermined systems: its dense
subset holds one such matrix, 32 x 14. Real data covers the classification;
the speed and conditioning claims need generated systems, and generated
systems invite the objection that whoever generated them chose the answer.

This script separates two questions. Portable validation checks statuses,
rank intervals, solution quality, and iterative-solver termination. Timing
ratios are recorded against historical reference-machine ranges, but do not
affect the exit status on unrelated hardware.

The claims, from the performance table and the status model:

  tall            overdetermined m >> n           20-80x, median about 22x
  grouped         exact repeated Hadamard rows    DGELSY and LSMR observations
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

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
      VECLIB_MAXIMUM_THREADS=1 \\
      python3 experiments/synthetic_bench.py --out benchmark.csv \\
        --metadata-out benchmark.metadata.json --reference-machine HOST

Run from the repository root after build.sh. A publication result also needs
a clean checkout and a stable reference-machine name in the metadata sidecar.
"""
import argparse
import csv
import ctypes
import json
import math
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))

DP = ctypes.POINTER(ctypes.c_double)
CLS = {0: "UNDETERMINED", 1: "UNIQUE", 2: "INFINITE", 3: "INCONSISTENT",
       4: "FAIL", 5: "UNDECIDABLE"}
QUALITY_THRESHOLD = 1e-14      # ABS_QUALITY_THRESHOLD in router.h
LSMR_RELATIVE_RESIDUAL_TOLERANCE = 1e-10
# SciPy's documented compatible-system exits: zero is already a solution,
# the requested atol/btol test passed, or the same test passed at machine
# precision.  Codes 2/5 are least-squares exits, 3/6 are condition-limit
# exits, and 7 is the iteration limit; none establishes the Ax=b comparison
# made by this harness.
LSMR_ACCEPTED_ISTOP = frozenset((0, 1, 4))


def load_router():
    lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))
    lib.bsolve_router_meta_api.argtypes = [
        DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, DP]
    lib.bsolve_router_meta_api.restype = None
    return lib


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def timed(fn, repeats, warmups=1):
    result = None
    for _ in range(warmups):
        result = fn()
    ts = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        ts.append(time.perf_counter() - t0)
    return result, ts


def baseline_name(kind, driver):
    """Return an unambiguous public label for a comparison routine."""
    if kind == "lsmr":
        return "LSMR"
    if kind == "lu":
        return "DGESV"
    if kind == "lapack" and driver in ("gelsy", "gelsd"):
        return "D" + driver.upper()
    raise ValueError(f"unknown baseline kind/driver: {kind}/{driver}")


def validate_lsmr_result(result, A, b, *, maxiter,
                         residual_tolerance=LSMR_RELATIVE_RESIDUAL_TOLERANCE):
    """Validate SciPy LSMR as a solution of this compatible Ax=b case."""
    if not isinstance(result, (tuple, list)) or len(result) != 8:
        return {"valid": False, "reason": "LSMR returned a malformed tuple"}

    x, istop, itn, normr, normar, norma, conda, normx = result
    x = np.asarray(x, dtype=np.float64)
    diagnostics = np.asarray((normr, normar, norma, conda, normx),
                             dtype=np.float64)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(diagnostics)):
        return {"valid": False,
                "reason": "LSMR returned a non-finite solution or diagnostic"}
    if not isinstance(istop, (int, np.integer)):
        return {"valid": False, "reason": "LSMR istop is not an integer"}
    if not isinstance(itn, (int, np.integer)) or itn < 0 or itn > maxiter:
        return {"valid": False, "reason": "LSMR iteration count is invalid"}
    if istop == 7:
        return {"valid": False,
                "reason": "LSMR reached the iteration limit without convergence"}
    if int(istop) not in LSMR_ACCEPTED_ISTOP:
        return {"valid": False,
                "reason": f"LSMR istop={istop} is not a compatible-system exit"}

    residual = np.asarray(A @ x - b, dtype=np.float64)
    if not np.all(np.isfinite(residual)):
        return {"valid": False, "reason": "LSMR residual is non-finite"}
    denom = max(float(np.linalg.norm(b)), np.finfo(np.float64).tiny)
    relative_residual = float(np.linalg.norm(residual) / denom)
    if not math.isfinite(relative_residual) or \
            relative_residual > residual_tolerance:
        return {"valid": False,
                "reason": (f"LSMR relative residual {relative_residual:.3e} "
                           f"exceeds {residual_tolerance:.3e}")}
    return {"valid": True, "reason": "ok", "istop": int(istop),
            "iterations": int(itn), "relative_residual": relative_residual,
            "reported_normr": float(normr), "reported_normar": float(normar),
            "reported_norma": float(norma), "reported_conda": float(conda),
            "reported_normx": float(normx)}


def make_result_row(*, family, claim, baseline_name, m, n, note, status,
                    rank, rank_lo, rank_hi, berr, router_timings,
                    baseline_timings, numerical_valid, validation_reason,
                    historical_range=None, baseline_diagnostics=None):
    """Build the stable row schema; timing ranges are observations only."""
    router_s = float(statistics.median(router_timings))
    baseline_s = float(statistics.median(baseline_timings))
    router_mad_s = float(statistics.median(
        abs(value - router_s) for value in router_timings))
    baseline_mad_s = float(statistics.median(
        abs(value - baseline_s) for value in baseline_timings))
    ratio = baseline_s / router_s if router_s > 0 else float("nan")
    if historical_range is None or not math.isfinite(ratio):
        observation = "not-scoped"
    else:
        lo, hi = historical_range
        observation = ("inside-reference-range" if lo <= ratio <= hi
                       else "outside-reference-range")
    return {
        "schema_version": 1,
        "family": family, "claim": claim, "baseline_name": baseline_name,
        "m": int(m), "n": int(n), "note": note, "status": status,
        "rank": int(rank), "rank_lo": int(rank_lo), "rank_hi": int(rank_hi),
        "berr": float(berr), "numerical_valid": bool(numerical_valid),
        "validation_reason": validation_reason,
        "router_s": router_s, "baseline_s": baseline_s,
        "router_mad_s": router_mad_s, "baseline_mad_s": baseline_mad_s,
        "router_timings_s": list(router_timings),
        "baseline_timings_s": list(baseline_timings),
        "ratio_direction": "baseline_over_router",
        "baseline_over_router": ratio,
        "historical_ratio_min": (None if historical_range is None
                                 else float(historical_range[0])),
        "historical_ratio_max": (None if historical_range is None
                                 else float(historical_range[1])),
        "performance_observation": observation,
        "baseline_diagnostics": baseline_diagnostics,
    }


def portable_failures(rows):
    """Return correctness/schema failures, deliberately ignoring timings."""
    return [f"{row['family']}: {row['validation_reason']}" for row in rows
            if not row.get("numerical_valid", False)]


def build_metadata_document(*, timestamp_utc, source_git_sha, git_dirty,
                            argv, args, rows, machine, compiler, threadpools,
                            software, thread_control):
    """Assemble the path-free reference-machine sidecar schema."""
    clean_threadpools = []
    for pool in threadpools:
        clean_threadpools.append({key: value for key, value in pool.items()
                                  if key != "filepath"})
    machine = dict(machine)
    machine["reference_name"] = args.reference_machine
    document = {
        "schema_version": 1,
        "scope": "reference-machine-performance-observation",
        "timestamp_utc": timestamp_utc,
        "source": {
            "git_sha": source_git_sha,
            "git_dirty": (None if git_dirty is None else bool(git_dirty)),
        },
        "command": shlex.join(["python3", *argv]),
        "command_argv": list(argv),
        "benchmark": {
            "seed": int(args.seed), "router_seed": 20260909,
            "driver": args.driver, "scale": float(args.scale),
            "large_cases": not args.no_large,
            "process_warmups": 3, "case_warmups": 1,
            "repeats": int(args.repeats),
            "summary_statistic": "median",
            "dispersion_statistic": "median-absolute-deviation",
            "cases": [{"family": row["family"], "m": row["m"],
                       "n": row["n"]} for row in rows],
        },
        "machine": machine,
        "compiler": compiler,
        "linear_algebra": {"threadpools": clean_threadpools},
        "software": software,
        "thread_control": thread_control,
        "results": rows,
    }
    return _json_safe(document)


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return None
    return value


def _command_output(command):
    try:
        return subprocess.check_output(command, cwd=str(ROOT), text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _git_source_state():
    sha = _command_output(["git", "rev-parse", "HEAD"])
    status = _command_output(["git", "status", "--porcelain"])
    return sha, None if status is None else bool(status)


def _machine_info():
    cpu_model = platform.processor() or None
    if not cpu_model and Path("/proc/cpuinfo").is_file():
        for line in Path("/proc/cpuinfo").read_text(errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                cpu_model = line.split(":", 1)[1].strip() or None
                break
    logical = os.cpu_count()
    physical = None
    topology = _command_output(["lscpu", "-p=SOCKET,CORE"])
    if topology:
        cores = {tuple(line.split(",")[:2]) for line in topology.splitlines()
                 if line and not line.startswith("#") and "," in line}
        physical = len(cores) or None
    ram_bytes = None
    try:
        ram_bytes = int(os.sysconf("SC_PAGE_SIZE") *
                        os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        pass
    return {
        "cpu_model": cpu_model, "physical_cores": physical,
        "logical_cores": logical,
        "smt_enabled": (None if physical is None or logical is None
                        else logical > physical),
        "ram_bytes": ram_bytes, "os": platform.system() or None,
        "os_version": platform.version() or None,
        "kernel": platform.release() or None,
    }


def _compiler_info():
    command = os.environ.get("CC")
    identity = None
    if command:
        identity = _command_output([command, "--version"])
        if identity:
            identity = identity.splitlines()[0]
    return {
        "command": command, "identity": identity,
        "flags": {name: os.environ.get(name)
                  for name in ("CFLAGS", "CPPFLAGS", "LDFLAGS", "ARCH_FLAGS")},
    }


def collect_metadata(args, rows, threadpools, scipy_version, source_state):
    sha, dirty = source_state
    thread_names = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
    return build_metadata_document(
        timestamp_utc=datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
        source_git_sha=sha, git_dirty=dirty, argv=sys.argv,
        args=args, rows=rows, machine=_machine_info(),
        compiler=_compiler_info(), threadpools=threadpools,
        software={"python": platform.python_version(), "numpy": np.__version__,
                  "scipy": scipy_version},
        thread_control={name: os.environ.get(name) for name in thread_names})


# ---------------------------------------------------------------------------
# Generators. Each returns (A, b, note).
# ---------------------------------------------------------------------------

def gen_tall(rng, m, n):
    A = rng.standard_normal((m, n))
    return A, A @ rng.standard_normal(n), ""


def hadamard_row(idx, n):
    """Return the normalized Sylvester-Hadamard row used by the C driver."""
    j = np.arange(n, dtype=np.uint32)
    parity = np.bitwise_count(np.bitwise_and(np.uint32(idx), j)) & 1 \
        if hasattr(np, "bitwise_count") else \
        np.array([bin(int(idx) & int(value)).count("1") & 1 for value in j])
    return np.where(parity.astype(bool), -1.0, 1.0) / math.sqrt(n)

def gen_tall_grouped(rng, m, n):
    """Port gen_grouped() from bsolver_core.c: exact repeated directions."""
    group_size = (m + n - 1) // n
    directions = np.stack([hadamard_row(index, n) for index in range(n)])
    indices = np.minimum(np.arange(m) // group_size, n - 1)
    A = directions[indices]
    x = rng.standard_normal(n)
    return A, A @ x, f"{n} groups of {group_size} identical rows"


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
                      m=m, n=n, expected_status="UNIQUE",
                      historical_range=(20.0, 80.0)))
    # These are the shapes named by the current manuscript.  The ranges are
    # retained as reference-machine observations, never portable pass/fail
    # criteria.  All ratios are baseline/router: the manuscript's statement
    # that LSMR is 2.6--5.9x faster maps to [1/5.9, 1/2.6].
    for n, m in ((64, 16384), (64, 131072), (256, 16384)):
        m = int(m * s)
        C.append(dict(family="grouped_vs_lapack",
                      claim="reference-machine DGELSY/router observation",
                      gen=lambda r, m=m, n=n: gen_tall_grouped(r, m, n),
                      m=m, n=n, baseline_kind="lapack",
                      expected_status="UNIQUE",
                      historical_range=(12.0, 25.0)))
        C.append(dict(family="grouped_vs_lsmr",
                      claim="reference-machine LSMR/router observation",
                      gen=lambda r, m=m, n=n: gen_tall_grouped(r, m, n),
                      m=m, n=n, baseline_kind="lsmr",
                      expected_status="UNIQUE",
                      historical_range=(1.0 / 5.9, 1.0 / 2.6)))
    for n in (256, 512):
        C.append(dict(family="square", claim="0.6-0.9x on square",
                      gen=lambda r, n=n: gen_square(r, n),
                      m=n, n=n, expected_status="UNIQUE",
                      baseline_kind="lu", historical_range=(0.6, 0.9)))
    for m, n in ((128, 512), (256, 2048)):
        C.append(dict(family="wide", claim="0.24-0.43x underdetermined",
                      gen=lambda r, m=m, n=n: gen_wide(r, m, n),
                      m=m, n=n, expected_status="INFINITE",
                      historical_range=(0.24, 0.43)))
    C.append(dict(family="wide_extreme", claim="no claim; 0.02x seen at n/m=420",
                  gen=lambda r: gen_wide(r, 32, 12800),
                  m=32, n=12800, expected_status="INFINITE",
                  historical_range=None))
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
                          m=m, n=n,
                          expected_status=("INFINITE" if m < n else "UNIQUE"),
                          baseline_kind=("lu" if m == n else "lapack"),
                          historical_range=sp))
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
    ap.add_argument("--metadata-out",
                    help="write reference-machine metadata and raw timings")
    ap.add_argument("--reference-machine",
                    help="stable human-assigned name for the measured host")
    args = ap.parse_args()

    import scipy
    from scipy.linalg import lstsq, solve
    from scipy.sparse.linalg import lsmr
    from threadpoolctl import threadpool_info, threadpool_limits

    source_state = _git_source_state()
    lib = load_router()
    rng = np.random.default_rng(args.seed)

    # Process-level warm up, before anything is timed.
    _A = np.ascontiguousarray(rng.standard_normal((512, 32)))
    _b = np.ascontiguousarray(_A @ rng.standard_normal(32))
    _o = np.zeros(11)
    rows = []

    with threadpool_limits(limits=1, user_api="blas"):
        for _ in range(3):
            lib.bsolve_router_meta_api(ptr(_A), ptr(_b), None, 512, 32,
                                       1, 2, 2, 1, 0, ptr(_o))
            lstsq(_A, _b, lapack_driver=args.driver, check_finite=False)
            solve(_A[:32], _b[:32], check_finite=False)
            lsmr(_A, _b, atol=1e-12, btol=1e-12, maxiter=32)

        for case in build_cases(rng, args.scale, not args.no_large):
            A, b, note = case["gen"](rng)
            A = np.ascontiguousarray(A)
            b = np.ascontiguousarray(b)
            m, n = A.shape
            out = np.zeros(11)

            def run_router():
                lib.bsolve_router_meta_api(ptr(A), ptr(b), None, m, n,
                                           1, 2, 2, 20260909, 0, ptr(out))

            _, router_timings = timed(run_router, args.repeats)
            kind = case.get("baseline_kind", "lu" if m == n else "lapack")
            maxiter = min(m, n)
            if kind == "lsmr":
                run_baseline = lambda: lsmr(
                    A, b, atol=1e-12, btol=1e-12, maxiter=maxiter)
            elif kind == "lu":
                run_baseline = lambda: solve(A, b, check_finite=False)
            else:
                run_baseline = lambda: lstsq(
                    A, b, lapack_driver=args.driver, check_finite=False)
            baseline_result, baseline_timings = timed(run_baseline,
                                                       args.repeats)

            status = CLS.get(int(out[0]), "?")
            lo, hi = int(out[3]), int(out[4])
            berr = float(out[10])
            expected = case.get("expected_status", case.get("status"))
            valid = status == expected
            reason = "ok" if valid else f"expected {expected}, got {status}"
            if case.get("quality"):
                valid = ((status == "UNIQUE" and np.isfinite(berr)
                          and berr <= QUALITY_THRESHOLD)
                         or status == "UNDECIDABLE")
                reason = ("ok" if valid else
                          f"invalid quality verdict {status}, berr={berr}")
            if valid and case.get("interval") and hi <= lo:
                valid = False
                reason = f"expected a non-point rank interval, got [{lo}, {hi}]"

            diagnostics = None
            if kind == "lsmr":
                diagnostics = validate_lsmr_result(
                    baseline_result, A, b, maxiter=maxiter)
                if not diagnostics["valid"]:
                    valid = False
                    reason = diagnostics["reason"]

            historical_range = case.get("historical_range")
            if kind == "lapack" and args.driver != "gelsy":
                historical_range = None
            row = make_result_row(
                family=case["family"], claim=case["claim"],
                baseline_name=baseline_name(kind, args.driver), m=m, n=n,
                note=note, status=status, rank=int(out[2]), rank_lo=lo,
                rank_hi=hi, berr=berr, router_timings=router_timings,
                baseline_timings=baseline_timings, numerical_valid=valid,
                validation_reason=reason, historical_range=historical_range,
                baseline_diagnostics=diagnostics)
            rows.append(row)
            print(f"  {case['family']:<20s} {m:>7d}x{n:<6d} "
                  f"{row['baseline_name']:<7s}/router "
                  f"{row['baseline_over_router']:.2f}x  "
                  f"numerical={'ok' if valid else 'FAIL'}  "
                  f"timing={row['performance_observation']}")

        effective_threadpools = threadpool_info()

    outp = ROOT / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: (json.dumps(value, sort_keys=True)
                      if isinstance(value, (list, dict)) else value)
                for key, value in row.items()
            })

    failures = portable_failures(rows)
    print()
    print(f"{len(rows)} numerical contracts checked, {len(failures)} failed")
    for failure in failures:
        print(f"  {failure}")
    print(f"written to {outp}")

    if args.metadata_out:
        metadata = collect_metadata(args, rows, effective_threadpools,
                                    scipy.__version__, source_state)
        metadata_path = ROOT / args.metadata_out
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, indent=2,
                                            allow_nan=False) + "\n")
        print(f"metadata written to {metadata_path}")

    timing_misses = sum(row["performance_observation"] ==
                        "outside-reference-range" for row in rows)
    print(f"{timing_misses} timing observations outside historical reference "
          "ranges (informational only)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
