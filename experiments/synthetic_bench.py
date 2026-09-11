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
import hashlib
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
BUILD_MANIFEST_NAME = ".abs-build-manifest.json"
BUILD_MANIFEST_SCHEMA_VERSION = 1
ROW_SCHEMA_VERSION = 2
CANONICAL_SEED = 20260909
CANONICAL_DRIVER = "gelsy"
REQUIRED_THREAD_CONTROLS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS")

# Ordered protocol signature. Order is part of the reference configuration:
# it fixes warm-up, cache and thermal history as well as the set of cases.
CANONICAL_REFERENCE_SIGNATURE = (
    ("tall.8000x32", 8000, 32, "lapack"),
    ("tall.7680x64", 7680, 64, "lapack"),
    ("tall.7680x128", 7680, 128, "lapack"),
    ("grouped_vs_lapack.16384x64", 16384, 64, "lapack"),
    ("grouped_vs_lsmr.16384x64", 16384, 64, "lsmr"),
    ("grouped_vs_lapack.131072x64", 131072, 64, "lapack"),
    ("grouped_vs_lsmr.131072x64", 131072, 64, "lsmr"),
    ("grouped_vs_lapack.16384x256", 16384, 256, "lapack"),
    ("grouped_vs_lsmr.16384x256", 16384, 256, "lsmr"),
    ("square.256x256", 256, 256, "lu"),
    ("square.512x512", 512, 512, "lu"),
    ("wide.128x512", 128, 512, "lapack"),
    ("wide.256x2048", 256, 2048, "lapack"),
    ("wide_extreme.32x12800", 32, 12800, "lapack"),
    ("cond_1e+02.4000x64", 4000, 64, "lapack"),
    ("cond_1e+08.4000x64", 4000, 64, "lapack"),
    ("cond_1e+14.4000x64", 4000, 64, "lapack"),
    ("rank_deficient.4000x64", 4000, 64, "lapack"),
    ("inconsistent.4000x64", 4000, 64, "lapack"),
    ("tall_large.8000x2000", 8000, 2000, "lapack"),
    ("tall_large.20000x2000", 20000, 2000, "lapack"),
    ("square_large.2000x2000", 2000, 2000, "lu"),
    ("wide_large.2000x8000", 2000, 8000, "lapack"),
    ("cond_large_1e+08.6000x2000", 6000, 2000, "lapack"),
    ("cond_large_1e+14.6000x2000", 6000, 2000, "lapack"),
    ("rank_deficient_large.6000x2000", 6000, 2000, "lapack"),
    ("near_transition_large.eps_1e-11", 6000, 2000, "lapack"),
    ("near_transition.eps_1e-12", 1500, 12, "lapack"),
    ("near_transition.eps_1e-10", 1500, 12, "lapack"),
)
CANONICAL_CASES_BY_ID = {
    case_id: (m, n, baseline_kind)
    for case_id, m, n, baseline_kind in CANONICAL_REFERENCE_SIGNATURE
}
HISTORICAL_REFERENCE_CASE_IDS = frozenset((
    "tall.8000x32", "tall.7680x64", "tall.7680x128",
    "grouped_vs_lapack.16384x64", "grouped_vs_lsmr.16384x64",
    "grouped_vs_lapack.131072x64", "grouped_vs_lsmr.131072x64",
    "grouped_vs_lapack.16384x256", "grouped_vs_lsmr.16384x256",
    "square.256x256", "square.512x512", "wide.128x512",
    "wide.256x2048", "tall_large.8000x2000",
    "tall_large.20000x2000", "square_large.2000x2000",
    "wide_large.2000x8000",
))
ROW_REQUIRED_FIELDS = (
    "schema_version", "case_id", "family", "baseline_kind",
    "baseline_name", "numerical_contract", "historical_claim",
    "historical_claim_scope", "historical_claim_applicable", "m", "n",
    "note", "status", "rank", "rank_lo", "rank_hi", "berr",
    "numerical_valid", "validation_reason", "router_timings_s",
    "baseline_timings_s", "router_s", "baseline_s", "router_mad_s",
    "baseline_mad_s", "ratio_direction", "baseline_over_router",
    "historical_ratio_min", "historical_ratio_max",
    "performance_observation", "baseline_diagnostics")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_router(router_path=None):
    path = Path(router_path or LIBDIR / "libaffine_bundle_solver.so").resolve()
    lib = ctypes.CDLL(str(path))
    lib.bsolve_router_meta_api.argtypes = [
        DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, DP]
    lib.bsolve_router_meta_api.restype = None
    return lib


def verify_build_manifest(*, router_path, manifest_path, build_script_path,
                          benchmark_git_sha, benchmark_git_tree_sha):
    """Verify the build record against the exact router selected for loading."""
    router_path = Path(router_path).resolve()
    manifest_path = Path(manifest_path)
    build_script_path = Path(build_script_path)
    result = {"verified": False, "reasons": [], "manifest": None,
              "router_path": str(router_path), "router_sha256": None}
    try:
        result["router_sha256"] = sha256_file(router_path)
    except OSError:
        result["reasons"].append("router_library_unreadable")
    if not manifest_path.is_file():
        result["reasons"].append("build_manifest_missing")
        return result
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        result["reasons"].append("build_manifest_invalid_json")
        return result
    result["manifest"] = manifest
    if not isinstance(manifest, dict) or \
            manifest.get("schema_version") != BUILD_MANIFEST_SCHEMA_VERSION:
        result["reasons"].append("build_manifest_schema_invalid")
        return result

    source = manifest.get("source") or {}
    script = manifest.get("build_script") or {}
    compiler = manifest.get("compiler") or {}
    router = manifest.get("router") or {}
    router_library = router.get("library") or {}
    openblas = manifest.get("openblas") or {}
    if result["router_sha256"] is not None and \
            router_library.get("sha256") != result["router_sha256"]:
        result["reasons"].append("router_library_hash_mismatch")
    if source.get("git_sha") != benchmark_git_sha:
        result["reasons"].append("build_source_sha_mismatch")
    if source.get("git_tree_sha") != benchmark_git_tree_sha:
        result["reasons"].append("build_source_tree_mismatch")
    if source.get("git_dirty") is not False:
        result["reasons"].append("build_source_dirty")
    if not manifest.get("built_at_utc"):
        result["reasons"].append("build_timestamp_missing")
    try:
        script_hash = sha256_file(build_script_path)
    except OSError:
        script_hash = None
    if not script.get("sha256") or script.get("sha256") != script_hash:
        result["reasons"].append("build_script_hash_mismatch")
    compiler_argv = compiler.get("command_argv")
    if not isinstance(compiler_argv, list) or not compiler_argv:
        result["reasons"].append("build_compiler_command_missing")
    if not compiler.get("identity"):
        result["reasons"].append("build_compiler_identity_missing")
    compile_argv = router.get("compile_argv")
    link_argv = router.get("link_argv")
    if not isinstance(compile_argv, list) or not compile_argv:
        result["reasons"].append("router_compile_argv_missing")
    if not isinstance(link_argv, list) or not link_argv:
        result["reasons"].append("router_link_argv_missing")
    if compiler_argv and compile_argv and \
            compile_argv[:len(compiler_argv)] != compiler_argv:
        result["reasons"].append("router_compile_compiler_mismatch")
    if compiler_argv and link_argv and \
            link_argv[:len(compiler_argv)] != compiler_argv:
        result["reasons"].append("router_link_compiler_mismatch")
    arch_flags = router.get("arch_flags")
    if compiler_argv and compile_argv:
        arch_tokens = (arch_flags.split()
                       if isinstance(arch_flags, str) else None)
        arch_start = len(compiler_argv) + 1
        if arch_tokens is None or len(compile_argv) <= len(compiler_argv) or \
                compile_argv[len(compiler_argv)] != "-O3" or \
                compile_argv[arch_start:arch_start + len(arch_tokens)] != \
                arch_tokens:
            result["reasons"].append("router_arch_flags_mismatch")
    if router_library.get("basename") != router_path.name:
        result["reasons"].append("router_library_basename_mismatch")
    openblas_hash = openblas.get("sha256")
    if not openblas_hash:
        result["reasons"].append("openblas_hash_missing")
    else:
        openblas_path = openblas.get("resolved_path")
        if not openblas_path:
            result["reasons"].append("openblas_path_missing")
        elif Path(openblas_path).is_file():
            try:
                if sha256_file(openblas_path) != openblas_hash:
                    result["reasons"].append("openblas_hash_mismatch")
            except OSError:
                result["reasons"].append("openblas_library_unreadable")
        if link_argv and openblas_path not in link_argv:
            result["reasons"].append("openblas_link_argv_mismatch")
    if openblas.get("basename") != (Path(openblas.get("resolved_path")).name
                                    if openblas.get("resolved_path") else None):
        result["reasons"].append("openblas_basename_mismatch")
    result["verified"] = not result["reasons"]
    return result


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


def comparison_contract(case, driver, scale):
    """Return the driver- and configuration-scoped comparison fields."""
    kind = case.get(
        "baseline_kind", "lu" if case["m"] == case["n"] else "lapack")
    name = baseline_name(kind, driver)
    historical_range = case.get("historical_range")
    applicable = (historical_range is not None and float(scale) == 1.0 and
                  driver == "gelsy")
    scoped_range = historical_range if applicable else None
    return {
        "baseline_name": name,
        "numerical_contract": case["numerical_contract"],
        "historical_claim": case.get("historical_claim"),
        "historical_claim_scope": ({
            "dimensions": {"m": case["reference_m"],
                           "n": case["reference_n"]},
            "scale": 1.0,
            "driver": "gelsy",
            "reference_baseline": baseline_name(kind, "gelsy"),
            "machine_scope": "named-reference-machine",
            "threading": "single-thread",
        } if historical_range is not None else None),
        "historical_claim_applicable": applicable,
        "historical_range": scoped_range,
    }


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


def make_result_row(*, case_id, family, baseline_kind, baseline_name,
                    numerical_contract, historical_claim,
                    historical_claim_scope, historical_claim_applicable,
                    m, n, note, status,
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
        "schema_version": ROW_SCHEMA_VERSION,
        "case_id": case_id, "family": family,
        "baseline_kind": baseline_kind, "baseline_name": baseline_name,
        "numerical_contract": numerical_contract,
        "historical_claim": historical_claim,
        "historical_claim_scope": historical_claim_scope,
        "historical_claim_applicable": bool(historical_claim_applicable),
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


def _valid_git_identity(value):
    return (isinstance(value, str) and len(value) == 40 and
            all(character in "0123456789abcdefABCDEF" for character in value))


def _valid_sha256(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(character in "0123456789abcdefABCDEF" for character in value))


def _append_reason(reasons, reason):
    if reason not in reasons:
        reasons.append(reason)


def _is_number(value):
    return isinstance(value, (int, float, np.integer, np.floating)) and \
        not isinstance(value, (bool, np.bool_))


def validate_schema_v2_row(row, repeats):
    """Validate one publication row and return all machine-readable blockers."""
    reasons = []
    if not isinstance(row, dict):
        return ["row_field_invalid:row"]
    for field in ROW_REQUIRED_FIELDS:
        if field not in row:
            reasons.append(f"row_required_field_missing:{field}")

    if row.get("schema_version") != ROW_SCHEMA_VERSION:
        reasons.append("row_schema_invalid")
    case_id = row.get("case_id")
    expected = CANONICAL_CASES_BY_ID.get(case_id)
    if expected is None or (row.get("m"), row.get("n"),
                            row.get("baseline_kind")) != expected:
        reasons.append("row_canonical_signature_mismatch")
    if isinstance(case_id, str) and row.get("family") != case_id.split(".", 1)[0]:
        reasons.append("row_family_mismatch")

    baseline_kind = row.get("baseline_kind")
    expected_baseline = {"lapack": "DGELSY", "lu": "DGESV",
                         "lsmr": "LSMR"}.get(baseline_kind)
    if expected_baseline is None:
        reasons.append("row_field_invalid:baseline_kind")
    elif row.get("baseline_name") != expected_baseline:
        reasons.append("row_baseline_name_mismatch")
    for field in ("case_id", "family", "baseline_name",
                  "numerical_contract", "validation_reason"):
        if field in row and (not isinstance(row[field], str) or not row[field]):
            reasons.append(f"row_field_invalid:{field}")
    if "note" in row and not isinstance(row["note"], str):
        reasons.append("row_field_invalid:note")
    if row.get("status") not in CLS.values():
        reasons.append("row_field_invalid:status")

    dimensions_valid = all(
        isinstance(row.get(field), (int, np.integer)) and
        not isinstance(row.get(field), (bool, np.bool_)) and row[field] > 0
        for field in ("m", "n"))
    rank_fields_valid = all(
        isinstance(row.get(field), (int, np.integer)) and
        not isinstance(row.get(field), (bool, np.bool_))
        for field in ("rank", "rank_lo", "rank_hi"))
    if not dimensions_valid:
        reasons.append("row_dimensions_invalid")
    if not rank_fields_valid or (dimensions_valid and not (
            0 <= row["rank_lo"] <= row["rank"] <= row["rank_hi"] <=
            min(row["m"], row["n"]))):
        reasons.append("row_rank_structure_invalid")
    berr = row.get("berr")
    if not _is_number(berr) or math.isinf(float(berr)) or (
            math.isnan(float(berr)) and row.get("status") == "UNIQUE") or (
            math.isfinite(float(berr)) and float(berr) < 0):
        reasons.append("row_field_invalid:berr")
    if row.get("numerical_valid") is not True:
        reasons.append("numerical_contract_failed")

    valid_timings = {}
    for label in ("router", "baseline"):
        values = row.get(f"{label}_timings_s")
        valid = (isinstance(values, list) and len(values) == int(repeats) and
                 all(_is_number(value) and math.isfinite(float(value)) and
                     float(value) > 0 for value in values))
        valid_timings[label] = valid
        if valid:
            median = float(statistics.median(values))
            mad = float(statistics.median(abs(value - median)
                                          for value in values))
            if not _is_number(row.get(f"{label}_s")) or not math.isclose(
                    float(row[f"{label}_s"]), median,
                    rel_tol=1e-12, abs_tol=1e-15):
                reasons.append(f"row_timing_median_mismatch:{label}")
            if not _is_number(row.get(f"{label}_mad_s")) or not math.isclose(
                    float(row[f"{label}_mad_s"]), mad,
                    rel_tol=1e-12, abs_tol=1e-15):
                reasons.append(f"row_timing_mad_mismatch:{label}")

    router_s = row.get("router_s")
    baseline_s = row.get("baseline_s")
    ratio = row.get("baseline_over_router")
    ratio_valid = (row.get("ratio_direction") == "baseline_over_router" and
                   _is_number(router_s) and math.isfinite(float(router_s)) and
                   float(router_s) > 0 and _is_number(baseline_s) and
                   math.isfinite(float(baseline_s)) and float(baseline_s) > 0 and
                   _is_number(ratio) and math.isfinite(float(ratio)) and
                   math.isclose(float(ratio),
                                float(baseline_s) / float(router_s),
                                rel_tol=1e-12, abs_tol=1e-15))
    if not ratio_valid:
        reasons.append("timing_ratio_invalid")

    historical = case_id in HISTORICAL_REFERENCE_CASE_IDS
    if row.get("historical_claim_applicable") is not historical:
        reasons.append("row_historical_applicability_invalid")
    if historical:
        expected_scope = {
            "dimensions": {"m": expected[0], "n": expected[1]},
            "scale": 1.0, "driver": CANONICAL_DRIVER,
            "reference_baseline": expected_baseline,
            "machine_scope": "named-reference-machine",
            "threading": "single-thread",
        } if expected is not None else None
        if not isinstance(row.get("historical_claim"), str) or \
                not row["historical_claim"]:
            reasons.append("row_historical_claim_invalid")
        if row.get("historical_claim_scope") != expected_scope:
            reasons.append("row_historical_scope_invalid")
        lo, hi = row.get("historical_ratio_min"), row.get("historical_ratio_max")
        if not (_is_number(lo) and _is_number(hi) and
                math.isfinite(float(lo)) and math.isfinite(float(hi)) and
                0 < float(lo) <= float(hi)):
            reasons.append("row_historical_range_invalid")
        if row.get("performance_observation") not in (
                "inside-reference-range", "outside-reference-range"):
            reasons.append("row_performance_observation_invalid")
    elif any((row.get("historical_claim") is not None,
              row.get("historical_claim_scope") is not None,
              row.get("historical_ratio_min") is not None,
              row.get("historical_ratio_max") is not None,
              row.get("performance_observation") != "not-scoped")):
        reasons.append("row_historical_fields_unexpected")

    diagnostics = row.get("baseline_diagnostics")
    if baseline_kind == "lsmr":
        required = ("valid", "reason", "istop", "iterations",
                    "relative_residual", "reported_normr", "reported_normar",
                    "reported_norma", "reported_conda", "reported_normx")
        diagnostics_valid = isinstance(diagnostics, dict) and \
            all(field in diagnostics for field in required)
        if diagnostics_valid:
            numeric = ("relative_residual", "reported_normr",
                       "reported_normar", "reported_norma", "reported_conda",
                       "reported_normx")
            diagnostics_valid = (
                diagnostics.get("valid") is True and
                diagnostics.get("reason") == "ok" and
                diagnostics.get("istop") in LSMR_ACCEPTED_ISTOP and
                isinstance(diagnostics.get("iterations"), (int, np.integer)) and
                0 <= diagnostics["iterations"] <= min(row["m"], row["n"]) and
                all(_is_number(diagnostics[field]) and
                    math.isfinite(float(diagnostics[field])) and
                    float(diagnostics[field]) >= 0 for field in numeric) and
                diagnostics["relative_residual"] <=
                LSMR_RELATIVE_RESIDUAL_TOLERANCE)
        if not diagnostics_valid:
            reasons.append("row_lsmr_diagnostics_invalid")
    elif diagnostics is not None:
        reasons.append("row_baseline_diagnostics_unexpected")
    return reasons


def evaluate_publication_eligibility(*, args, rows, source_state, machine,
                                     software, thread_control, threadpools,
                                     build_verification):
    """Return every reason this run cannot be publication evidence."""
    reasons = []
    if not isinstance(args.reference_machine, str) or \
            not args.reference_machine.strip():
        reasons.append("reference_machine_missing")
    if args.seed != CANONICAL_SEED:
        reasons.append("benchmark_seed_noncanonical")
    if args.driver != CANONICAL_DRIVER:
        reasons.append("benchmark_driver_noncanonical")
    if not _valid_git_identity(source_state.get("git_sha")):
        reasons.append("source_git_sha_invalid")
    if not _valid_git_identity(source_state.get("git_tree_sha")):
        reasons.append("source_git_tree_invalid")
    dirty = source_state.get("git_dirty")
    if dirty is None:
        reasons.append("source_git_dirty_unknown")
    elif dirty:
        reasons.append("source_git_dirty")
    if float(args.scale) != 1.0:
        reasons.append("scale_not_one")
    if args.no_large:
        reasons.append("large_cases_disabled")
    if int(args.repeats) < 11:
        reasons.append("insufficient_repeats")

    expected = CANONICAL_REFERENCE_SIGNATURE
    if not rows:
        reasons.append("case_set_empty")
    actual = tuple((row.get("case_id"), row.get("m"), row.get("n"),
                    row.get("baseline_kind")) for row in rows)
    expected_ids = [entry[0] for entry in expected]
    actual_ids = [entry[0] for entry in actual]
    if len(actual) < len(expected) or set(expected_ids) - set(actual_ids):
        reasons.append("case_set_incomplete")
    if len(actual_ids) != len(set(actual_ids)):
        reasons.append("case_set_duplicate")
    if set(actual_ids) - set(expected_ids) or any(
            entry not in expected for entry in actual):
        reasons.append("case_set_unexpected")
    if (len(actual) == len(expected) and set(actual) == set(expected) and
            actual != expected):
        reasons.append("case_order_mismatch")

    numerical_failed = any(row.get("numerical_valid") is not True
                           for row in rows)
    timing_array_missing = False
    timing_repeat_count_mismatch = False
    timing_nonfinite = False
    timing_nonpositive = False
    timing_summary_nonfinite = False
    timing_summary_nonpositive = False
    timing_ratio_invalid = False
    row_schema_invalid = False
    for row in rows:
        for reason in validate_schema_v2_row(row, args.repeats):
            _append_reason(reasons, reason)
        if row.get("schema_version") != ROW_SCHEMA_VERSION:
            row_schema_invalid = True
        for key in ("router_timings_s", "baseline_timings_s"):
            values = row.get(key)
            if not isinstance(values, list):
                timing_array_missing = True
                continue
            if len(values) != int(args.repeats):
                timing_repeat_count_mismatch = True
            for value in values:
                if not isinstance(value, (int, float)) or \
                        not math.isfinite(value):
                    timing_nonfinite = True
                elif value <= 0:
                    timing_nonpositive = True
        for key in ("router_s", "baseline_s"):
            value = row.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                timing_summary_nonfinite = True
            elif value <= 0:
                timing_summary_nonpositive = True
        ratio = row.get("baseline_over_router")
        if not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or \
                ratio <= 0:
            timing_ratio_invalid = True
        elif row.get("ratio_direction") != "baseline_over_router" or not (
                isinstance(row.get("router_s"), (int, float)) and
                isinstance(row.get("baseline_s"), (int, float)) and
                row["router_s"] > 0 and math.isclose(
                    ratio, row["baseline_s"] / row["router_s"],
                    rel_tol=1e-12, abs_tol=0.0)):
            timing_ratio_invalid = True
    for failed, reason in (
            (row_schema_invalid, "row_schema_invalid"),
            (numerical_failed, "numerical_contract_failed"),
            (timing_array_missing, "timing_array_missing"),
            (timing_repeat_count_mismatch, "timing_repeat_count_mismatch"),
            (timing_nonfinite, "timing_nonfinite"),
            (timing_nonpositive, "timing_nonpositive"),
            (timing_summary_nonfinite, "timing_summary_nonfinite"),
            (timing_summary_nonpositive, "timing_summary_nonpositive"),
            (timing_ratio_invalid, "timing_ratio_invalid")):
        if failed:
            reasons.append(reason)

    for name in REQUIRED_THREAD_CONTROLS:
        if name not in thread_control or thread_control[name] is None:
            reasons.append(f"thread_control_missing:{name}")
        elif thread_control[name] != "1":
            reasons.append(f"thread_control_not_one:{name}")
    blas_pools = [pool for pool in threadpools
                  if pool.get("user_api") == "blas"]
    if not blas_pools:
        reasons.append("blas_provider_missing")
    elif any(pool.get("num_threads") != 1 for pool in blas_pools):
        reasons.append("blas_threadpool_not_single_thread")
    elif any(not pool.get("internal_api") or not pool.get("version")
             for pool in blas_pools):
        reasons.append("blas_provider_identity_missing")
    runtime_hashes = [pool.get("sha256") for pool in blas_pools
                      if _valid_sha256(pool.get("sha256"))]
    if not runtime_hashes:
        reasons.append("runtime_blas_identity_unavailable")
    else:
        manifest = (build_verification.get("manifest")
                    if isinstance(build_verification, dict) else None) or {}
        built_openblas_hash = (manifest.get("openblas") or {}).get("sha256")
        if _valid_sha256(built_openblas_hash) and \
                built_openblas_hash not in runtime_hashes:
            reasons.append("runtime_blas_hash_mismatch")

    for key in ("cpu_model", "physical_cores", "logical_cores", "ram_bytes",
                "smt_enabled", "os", "os_version", "kernel"):
        if machine.get(key) in (None, ""):
            reasons.append(f"machine_identity_missing:{key}")
    for key in ("python", "numpy", "scipy"):
        if software.get(key) in (None, ""):
            reasons.append(f"software_identity_missing:{key}")

    if not isinstance(build_verification, dict):
        reasons.append("build_verification_missing")
    else:
        reasons.extend(build_verification.get("reasons") or [])
        if not build_verification.get("verified") and \
                not build_verification.get("reasons"):
            reasons.append("build_verification_failed")
    reasons = list(dict.fromkeys(reasons))
    return {"eligible": not reasons, "reasons": reasons}


def describe_runtime_threadpools(threadpools):
    """Replace runtime BLAS paths with relocatable binary identities."""
    described = []
    for pool in threadpools:
        record = {key: value for key, value in pool.items()
                  if key != "filepath"}
        path = pool.get("filepath")
        if path:
            record["basename"] = Path(path).name
            try:
                record["sha256"] = sha256_file(path)
            except OSError:
                record["sha256"] = None
        else:
            record.setdefault("basename", None)
            record.setdefault("sha256", None)
        described.append(record)
    return described


def build_metadata_document(*, timestamp_utc, source_state, argv, args, rows,
                            machine, threadpools, software, thread_control,
                            build_verification):
    """Assemble the reference-machine sidecar and eligibility verdict."""
    clean_threadpools = describe_runtime_threadpools(threadpools)
    machine = dict(machine)
    machine["reference_name"] = args.reference_machine
    eligibility = evaluate_publication_eligibility(
        args=args, rows=rows, source_state=source_state, machine=machine,
        software=software, thread_control=thread_control,
        threadpools=clean_threadpools, build_verification=build_verification)
    document = {
        "schema_version": 2,
        "scope": "reference-machine-performance-observation",
        "timestamp_utc": timestamp_utc,
        "source": source_state,
        "command": shlex.join(["python3", *argv]),
        "command_argv": list(argv),
        "publication_eligibility": eligibility,
        "benchmark": {
            "seed": int(args.seed), "router_seed": 20260909,
            "driver": args.driver, "scale": float(args.scale),
            "large_cases": not args.no_large,
            "process_warmups": 3, "case_warmups": 1,
            "repeats": int(args.repeats),
            "summary_statistic": "median",
            "dispersion_statistic": "median-absolute-deviation",
            "canonical_reference_signature": CANONICAL_REFERENCE_SIGNATURE,
            "cases": [{"case_id": row.get("case_id"),
                       "family": row["family"], "m": row["m"],
                       "n": row["n"],
                       "baseline_kind": row.get("baseline_kind")}
                      for row in rows],
        },
        "machine": machine,
        "build_provenance": build_verification,
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
    tree = _command_output(["git", "rev-parse", "HEAD^{tree}"])
    status = _command_output(["git", "status", "--porcelain"])
    return {"git_sha": sha, "git_tree_sha": tree,
            "git_dirty": None if status is None else bool(status)}


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


def collect_metadata(args, rows, threadpools, scipy_version, source_state,
                     build_verification):
    return build_metadata_document(
        timestamp_utc=datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
        source_state=source_state, argv=sys.argv,
        args=args, rows=rows, machine=_machine_info(),
        threadpools=threadpools,
        software={"python": platform.python_version(), "numpy": np.__version__,
                  "scipy": scipy_version},
        thread_control={name: os.environ.get(name)
                        for name in REQUIRED_THREAD_CONTROLS},
        build_verification=build_verification)


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
# Cases: stable identity, portable numerical contract, scoped historical
# observation, generator, and expected classification.
# ---------------------------------------------------------------------------

def build_cases(rng, scale, large):
    s = scale
    C = []

    def add(case_id, reference_m, reference_n, **case):
        case.update(case_id=case_id, reference_m=reference_m,
                    reference_n=reference_n)
        C.append(case)

    # Aspect stays high on purpose. The claim is about m >> n, and an earlier
    # version included a 6000 x 3000 case whose aspect is 2: measuring the
    # m >> n range against it says nothing about the claim.
    for n, aspect in ((32, 250), (64, 120), (128, 60)):
        reference_m = n * aspect
        m = int(reference_m * s)
        add(f"tall.{reference_m}x{n}", reference_m, n, family="tall",
            numerical_contract="router status is UNIQUE",
            historical_claim="20-80x baseline/router on m >> n",
            gen=lambda r, m=m, n=n: gen_tall(r, m, n), m=m, n=n,
            expected_status="UNIQUE", historical_range=(20.0, 80.0))
    # These are the shapes named by the current manuscript.  The ranges are
    # retained as reference-machine observations, never portable pass/fail
    # criteria.  All ratios are baseline/router: the manuscript's statement
    # that LSMR is 2.6--5.9x faster maps to [1/5.9, 1/2.6].
    for n, m in ((64, 16384), (64, 131072), (256, 16384)):
        reference_m = m
        m = int(reference_m * s)
        add(f"grouped_vs_lapack.{reference_m}x{n}", reference_m, n,
            family="grouped_vs_lapack",
            numerical_contract="router status is UNIQUE",
            historical_claim="12-25x DGELSY/router observation",
            gen=lambda r, m=m, n=n: gen_tall_grouped(r, m, n),
            m=m, n=n, baseline_kind="lapack", expected_status="UNIQUE",
            historical_range=(12.0, 25.0))
        add(f"grouped_vs_lsmr.{reference_m}x{n}", reference_m, n,
            family="grouped_vs_lsmr",
            numerical_contract=("router status is UNIQUE and LSMR has a "
                                "compatible-system exit and residual"),
            historical_claim="0.169-0.385x LSMR/router observation",
            gen=lambda r, m=m, n=n: gen_tall_grouped(r, m, n),
            m=m, n=n, baseline_kind="lsmr", expected_status="UNIQUE",
            historical_range=(1.0 / 5.9, 1.0 / 2.6))
    for n in (256, 512):
        add(f"square.{n}x{n}", n, n, family="square",
            numerical_contract="router status is UNIQUE",
            historical_claim="0.6-0.9x DGESV/router on square systems",
            gen=lambda r, n=n: gen_square(r, n), m=n, n=n,
            expected_status="UNIQUE", baseline_kind="lu",
            historical_range=(0.6, 0.9))
    for m, n in ((128, 512), (256, 2048)):
        add(f"wide.{m}x{n}", m, n, family="wide",
            numerical_contract="router status is INFINITE",
            historical_claim="0.24-0.43x DGELSY/router underdetermined",
            gen=lambda r, m=m, n=n: gen_wide(r, m, n), m=m, n=n,
            expected_status="INFINITE", historical_range=(0.24, 0.43))
    add("wide_extreme.32x12800", 32, 12800, family="wide_extreme",
        numerical_contract="router status is INFINITE", historical_claim=None,
        gen=lambda r: gen_wide(r, 32, 12800), m=32, n=12800,
        expected_status="INFINITE", historical_range=None)
    for kappa in (1e2, 1e8, 1e14):
        m, n = int(4000 * s), 64
        add(f"cond_{kappa:.0e}.4000x64", 4000, 64,
            family=f"cond_{kappa:.0e}",
            numerical_contract="UNIQUE with berr <= 1e-14, or UNDECIDABLE",
            historical_claim=None,
            gen=lambda r, m=m, n=n, k=kappa: gen_cond(r, m, n, k),
            m=m, n=n, status="UNIQUE", quality=True)
    add("rank_deficient.4000x64", 4000, 64, family="rank_deficient",
        numerical_contract="router status is INFINITE", historical_claim=None,
        gen=lambda r: gen_rank_deficient(r, int(4000 * s), 64, 40),
        m=int(4000 * s), n=64, status="INFINITE")
    add("inconsistent.4000x64", 4000, 64, family="inconsistent",
        numerical_contract="router status is INCONSISTENT",
        historical_claim=None,
        gen=lambda r: gen_inconsistent(r, int(4000 * s), 64),
        m=int(4000 * s), n=64, status="INCONSISTENT")
    # Large systems. Everything above keeps n at 128 or below for the timed
    # families, which leaves the regime a user is most likely to care about
    # untested: the manuscript's numbers were taken on narrow systems and
    # nothing said they carry to wide ones. These are 2000 equations and up,
    # with n in the thousands, and they dominate the runtime of this script.
    # Skip with --no-large when iterating on something else.
    if large:
        for m, n, fam, historical_claim, sp in (
                (8000, 2000, "tall_large", "20-80x on m >> n", (20.0, 80.0)),
                (20000, 2000, "tall_large", "20-80x on m >> n", (20.0, 80.0)),
                (2000, 2000, "square_large", "0.6-0.9x on square", (0.6, 0.9)),
                (2000, 8000, "wide_large", "0.24-0.43x underdetermined",
                 (0.24, 0.43))):
            add(f"{fam}.{m}x{n}", m, n, family=fam,
                numerical_contract=("router status is INFINITE" if m < n
                                    else "router status is UNIQUE"),
                historical_claim=historical_claim,
                gen=lambda r, m=m, n=n: (gen_square(r, n) if m == n
                                         else gen_tall(r, m, n)),
                m=m, n=n,
                expected_status=("INFINITE" if m < n else "UNIQUE"),
                baseline_kind=("lu" if m == n else "lapack"),
                historical_range=sp)
        # Conditioning at scale: the quality invariant is the one claim that
        # could plausibly weaken with n, since the backward error grows about
        # like n * eps and the threshold does not move.
        for kappa in (1e8, 1e14):
            add(f"cond_large_{kappa:.0e}.6000x2000", 6000, 2000,
                family=f"cond_large_{kappa:.0e}",
                numerical_contract=("UNIQUE with berr <= 1e-14, or "
                                    "UNDECIDABLE"), historical_claim=None,
                gen=lambda r, k=kappa: gen_cond(r, 6000, 2000, k),
                m=6000, n=2000, status="UNIQUE", quality=True)
        add("rank_deficient_large.6000x2000", 6000, 2000,
            family="rank_deficient_large",
            numerical_contract="router status is INFINITE",
            historical_claim=None,
            gen=lambda r: gen_rank_deficient(r, 6000, 2000, 1500),
            m=6000, n=2000, status="INFINITE")
        add("near_transition_large.eps_1e-11", 6000, 2000,
            family="near_transition_large",
            numerical_contract="UNDECIDABLE with a non-point rank interval",
            historical_claim=None,
            gen=lambda r: gen_near_transition(r, 6000, 2000, 1e-11),
            m=6000, n=2000, status="UNDECIDABLE", interval=True)

    for eps in (1e-12, 1e-10):
        eps_id = f"{eps:.0e}".replace("e-0", "e-")
        add(f"near_transition.eps_{eps_id}", 1500, 12,
            family="near_transition",
            numerical_contract="UNDECIDABLE with a non-point rank interval",
            historical_claim=None,
            gen=lambda r, e=eps: gen_near_transition(r, 1500, 12, e),
            m=1500, n=12, status="UNDECIDABLE", interval=True)
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
    router_path = (LIBDIR / "libaffine_bundle_solver.so").resolve()
    build_verification = verify_build_manifest(
        router_path=router_path,
        manifest_path=router_path.parent / BUILD_MANIFEST_NAME,
        build_script_path=ROOT / "build.sh",
        benchmark_git_sha=source_state.get("git_sha"),
        benchmark_git_tree_sha=source_state.get("git_tree_sha"))
    lib = load_router(router_path)
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

            comparison = comparison_contract(case, args.driver, args.scale)
            row = make_result_row(
                case_id=case["case_id"], family=case["family"],
                baseline_kind=kind, m=m, n=n,
                note=note, status=status, rank=int(out[2]), rank_lo=lo,
                rank_hi=hi, berr=berr, router_timings=router_timings,
                baseline_timings=baseline_timings, numerical_valid=valid,
                validation_reason=reason, baseline_diagnostics=diagnostics,
                **comparison)
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
                                    scipy.__version__, source_state,
                                    build_verification)
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
