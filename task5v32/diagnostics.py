"""Utilities for the four-cycle Task-5 v3.2 bottleneck investigation."""

import json
import copy
import csv
import io
import math
import os
import subprocess
import sys
import statistics
import struct
from pathlib import Path

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize

CAMPAIGN_ID = "task5-v3.2-bottleneck-20260926"
SOLVER_COMMIT = "f66cd87a7b198497cc53d63b2bb04b85c3e64f53"
HARNESS_BASELINE = "1827f2d458bcf55b0ade81a1174d1fa2ceb9d9ad"
BOUNDED_SLOT_IDS = ("V31-025", "V31-026", "V31-027")
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def diagnostic_manifest():
    slots = [slot for slot in generate_manifest()["slots"] if slot["slot_id"] in BOUNDED_SLOT_IDS]
    return {"campaign_id": CAMPAIGN_ID, "schema_version": 32, "solver_commit": SOLVER_COMMIT,
            "harness_baseline": HARNESS_BASELINE, "thread_count": 4,
            "scope": "diagnostic-only-exactly-four-pdca-cycles", "slots": slots}


def custom_tall_slot(m, n):
    if not (m > n > 0):
        raise ValueError("custom sensitivity slot must be tall")
    base = next(slot for slot in generate_manifest()["slots"] if slot["slot_id"] == "V31-027")
    slot = copy.deepcopy(base); slot["slot_id"] = f"V32-TALL-{m}x{n}"; slot["m"] = m; slot["n"] = n
    slot["max_dimension"] = m; slot["structural_rank_profile"]["algebraic_rank"] = n
    return slot


def parse_trace_line(text):
    line = next((line for line in reversed(text.splitlines()) if line.startswith("ABS_TRACE ")), None)
    if line is None:
        raise ValueError("missing ABS_TRACE record")
    result = {}
    for field in line.split()[1:]:
        key, raw = field.split("=", 1)
        result[key] = int(raw)
    return result


def reconcile_native_phases(trace):
    total = trace["api_ns"]
    router = trace.get("router_ns", 0)
    generators = sum(value for key, value in trace.items() if key.endswith("_gen_ns"))
    verify = trace.get("verify_ns", 0)
    attributed = router + generators + verify
    unattributed = max(0, total - attributed)
    return {"native_total_ns": total, "router_inclusive_ns": router,
            "witness_generation_inclusive_ns": generators,
            "selected_kernels_inclusive_ns": trace.get("lapack_ns", 0),
            "independent_verification_inclusive_ns": verify,
            "native_unattributed_ns": unattributed,
            "reconciled_fraction": (attributed + unattributed) / total if total else math.nan}


def phase_ledger(record, trace):
    timing = record["timing_ns"]; total = timing["total_wall"]
    api = trace["api_ns"]; router = trace.get("router_ns", 0)
    generators = sum(trace.get(name, 0) for name in ("unique_gen_ns", "infinite_gen_ns", "inconsistent_gen_ns"))
    verify = trace.get("verify_ns", 0); kernels = trace.get("lapack_ns", 0)
    router_kernels = trace.get("router_lapack_ns", 0); generator_kernels = trace.get("generator_lapack_ns", 0)
    verify_kernels = trace.get("verify_lapack_ns", 0); other_kernels = trace.get("other_lapack_ns", 0)
    native_other = max(0, api - router - generators - verify)
    ffi_boundary = max(0, timing["ffi_api_inclusive"] - api)
    bookkeeping = max(0, total - timing["python_control_preparation"] - timing["ffi_api_inclusive"])
    phases = [
        ("python_control_preparation", timing["python_control_preparation"], timing["python_control_preparation"]),
        ("ffi_api_boundary", timing["ffi_api_inclusive"], ffi_boundary),
        ("router_execution", router, max(0, router - router_kernels)),
        ("selected_numerical_kernels", kernels, kernels),
        ("solution_reconstruction", generators, max(0, generators - generator_kernels)),
        ("residual_status_certification", native_other, max(0, native_other - other_kernels)),
        ("independent_verification", verify, max(0, verify - verify_kernels)),
        ("serialization_harness_bookkeeping", bookkeeping, bookkeeping),
    ]
    result = [{"component": name, "inclusive_ns": inclusive, "exclusive_ns": exclusive,
               "exclusive_percent": 100.0 * exclusive / total if total else math.nan}
              for name, inclusive, exclusive in phases]
    reconciled = sum(item["exclusive_ns"] for item in result)
    return {"total_wall_ns": total, "phases": result, "unattributed_ns": total - reconciled,
            "reconciled_fraction": reconciled / total if total else math.nan}


def rank_native_hotspots(traces, total_ns):
    functions = ("dgeqp3", "dgelsy", "dgesvd", "dgesdd", "dormqr", "dgemm", "dgemv")
    ranked = []
    for name in functions:
        elapsed = statistics.median(row.get(f"{name}_ns", 0) for row in traces)
        count = statistics.median(row.get(f"{name}_count", 0) for row in traces)
        ranked.append({"function": f"{name}_", "inclusive_median_ns": elapsed, "self_time_ns": None,
                       "call_count": count, "share_of_end_to_end": elapsed / total_ns if total_ns else math.nan})
    return sorted(ranked, key=lambda row: row["inclusive_median_ns"], reverse=True)


def controlled_environment(threads=4, preload=None):
    environment = os.environ.copy()
    for name in THREAD_VARIABLES:
        environment[name] = str(threads)
    if preload:
        environment["LD_PRELOAD"] = str(preload)
        environment["TASK5_V32_TRACE"] = "1"
    return environment


def build_trace_library(out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("native_trace.c")
    output = out_dir / "libtask5v32_trace.so"
    include = os.environ.get("TASK5_SOLVER_INCLUDE", "/projects/research-assistant/task5-solver-final/include")
    command = ["cc", "-std=c11", "-O2", "-fPIC", "-shared", "-I", include, str(source), "-ldl", "-o", str(output)]
    subprocess.run(command, check=True)
    return output


def build_reproduction_driver(out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("native_reproduction.c"); output = out_dir / "task5v32_native_reproduction"
    root = Path(os.environ.get("TASK5_SOLVER_ROOT", "/projects/research-assistant/task5-solver-final"))
    build = Path(os.environ.get("TASK5_SOLVER_BUILD", root / "build-task5-final"))
    command = ["cc", "-std=c11", "-O2", "-I", str(root / "include"), str(source), "-L", str(build),
               "-lcertified_solver", "-laffine_bundle_solver", "-lstatus_verifier", f"-Wl,-rpath,{build}", "-o", str(output)]
    subprocess.run(command, check=True)
    return output


def write_binary_input(path, slot):
    a, b, _ = materialize(slot); path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(struct.pack("=ii", slot["m"], slot["n"])); handle.write(a.tobytes(order="C")); handle.write(b.tobytes(order="C"))
    return path


def parse_driver_csv(text):
    return [{key: int(value) for key, value in row.items()} for row in csv.DictReader(io.StringIO(text))]


def coefficient_of_variation(values):
    mean = statistics.fmean(values)
    return statistics.pstdev(values) / mean if mean else math.nan


def run_slot(slot_id, *, threads=4, preload=None, legacy=False):
    command = [sys.executable, "-m", "task5v32.native_trial", "--slot", slot_id]
    if legacy:
        raise ValueError("legacy control belongs to the separate correctness comparison")
    completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=controlled_environment(threads, preload))
    result = {"command": command, "record": json.loads(completed.stdout), "stderr": completed.stderr}
    if preload:
        result["trace"] = parse_trace_line(completed.stderr)
    return result


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
