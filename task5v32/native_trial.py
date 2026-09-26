"""Minimal one-call process used by the v3.2 diagnostic probes."""

import argparse
import ctypes as ct
import json
import os
import resource
import time

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize
from task5v31.runner import canonical_combined, json_safe, thermal_state, thread_configuration
import task5v31.solver as solver

from .diagnostics import CAMPAIGN_ID


def _trace_global_library():
    # Keep the immutable target resident before resolving the LD_PRELOAD wrapper.
    ct.CDLL(os.environ["TASK5_SOLVER_LIB"])
    library = ct.CDLL(None); pointer = ct.POINTER(ct.c_double)
    library.bsolve_certified_diag_api.argtypes = [pointer, pointer, pointer, ct.c_int, ct.c_int, ct.c_int,
                                                   ct.c_int, ct.c_int, ct.c_ulonglong, ct.c_int,
                                                   ct.POINTER(solver.BSCombinedCertifiedResult)]
    library.bsolve_certified_diag_api.restype = ct.c_int
    return library


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--slot", required=True); args = parser.parse_args()
    if os.environ.get("TASK5_V32_TRACE") == "1":
        library = _trace_global_library(); solver._library = lambda: library
    slot = next(item for item in generate_manifest()["slots"] if item["slot_id"] == args.slot)
    wall = time.perf_counter_ns(); cpu = time.process_time_ns()
    started = time.perf_counter_ns(); a, b, matrix = materialize(slot); preparation = time.perf_counter_ns() - started
    started = time.perf_counter_ns(); combined = solver.call_certified(a, b, xt=None); ffi_api = time.perf_counter_ns() - started
    record = {"campaign_id": CAMPAIGN_ID, "slot_id": args.slot, "matrix": matrix,
              "dimensions": [slot["m"], slot["n"]], "thread_configuration": thread_configuration(),
              "thermal": thermal_state(), "combined": canonical_combined(combined),
              "timing_ns": {"python_control_preparation": preparation, "ffi_api_inclusive": ffi_api,
                            "serialization_bookkeeping": 0, "total_wall": 0},
              "cpu_time_ns": 0, "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    started = time.perf_counter_ns(); json.dumps(json_safe(record), sort_keys=True, allow_nan=False)
    record["timing_ns"]["serialization_bookkeeping"] = time.perf_counter_ns() - started
    record["timing_ns"]["total_wall"] = time.perf_counter_ns() - wall
    record["cpu_time_ns"] = time.process_time_ns() - cpu
    print(json.dumps(json_safe(record), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
