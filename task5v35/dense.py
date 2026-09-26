"""Frozen seeded dense secondary inputs and one-process probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import time

import numpy as np

from task5v31.runner import canonical_combined, json_safe, thermal_state, thread_configuration
from task5v31.solver import call_certified
from task5v35.trial import loaded_numeric_libraries


DENSE_SPECS = {
    "V31-025": {"m": 128, "n": 256, "seed": 20260927},
    "V31-026": {"m": 192, "n": 192, "seed": 20260928},
    "V31-027": {"m": 256, "n": 128, "seed": 20260929},
}


def dense_input(slot_id):
    spec = DENSE_SPECS[slot_id]
    rng = np.random.Generator(np.random.PCG64(spec["seed"]))
    matrix = np.ascontiguousarray(rng.standard_normal((spec["m"], spec["n"])),
                                  dtype=np.float64)
    rhs = np.ascontiguousarray(matrix[:, 0])
    return matrix, rhs


def _array_sha256(array):
    return hashlib.sha256(memoryview(np.ascontiguousarray(array)).cast("B")).hexdigest()


def dense_manifest():
    result = {}
    for slot_id, spec in DENSE_SPECS.items():
        matrix, rhs = dense_input(slot_id)
        result[slot_id] = {**spec, "matrix_sha256": _array_sha256(matrix),
                           "rhs_sha256": _array_sha256(rhs)}
    return result


def run_dense_trial(slot_id):
    matrix, rhs = dense_input(slot_id)
    wall = time.perf_counter_ns()
    start = time.perf_counter_ns()
    combined = call_certified(matrix, rhs, xt=None, full=0)
    api_ns = time.perf_counter_ns() - start
    row = {
        "slot_id": slot_id,
        "input": dense_manifest()[slot_id],
        "combined": canonical_combined(combined),
        "timing_ns": {"combined_c_api": api_ns,
                      "total_wall": time.perf_counter_ns() - wall},
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "thermal": thermal_state(),
        "thread_configuration": thread_configuration(),
        "process_affinity": sorted(os.sched_getaffinity(0)),
        "loaded_numeric_libraries": loaded_numeric_libraries(),
    }
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True, choices=sorted(DENSE_SPECS))
    args = parser.parse_args()
    print(json.dumps(json_safe(run_dense_trial(args.slot)), sort_keys=True,
                     allow_nan=False))


if __name__ == "__main__":
    main()

