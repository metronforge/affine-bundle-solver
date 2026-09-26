"""Warm/cold repeated one-call diagnostic for a single sensitivity case."""

import argparse
import json
import os
import resource
import time

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize
from task5v31.runner import canonical_combined, json_safe, thermal_state, thread_configuration
import task5v31.solver as solver

from .diagnostics import CAMPAIGN_ID, custom_tall_slot
from .native_trial import _trace_global_library


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--slot")
    parser.add_argument("--m", type=int); parser.add_argument("--n", type=int); parser.add_argument("--repeats", type=int, default=4)
    args = parser.parse_args()
    if os.environ.get("TASK5_V32_TRACE") == "1":
        library = _trace_global_library(); solver._library = lambda: library
    if args.slot:
        slot = next(item for item in generate_manifest()["slots"] if item["slot_id"] == args.slot)
    else:
        slot = custom_tall_slot(args.m, args.n)
    a, b, matrix = materialize(slot); calls = []
    for index in range(args.repeats):
        wall, cpu = time.perf_counter_ns(), time.process_time_ns(); combined = solver.call_certified(a, b, xt=None)
        wall_ns, cpu_ns = time.perf_counter_ns() - wall, time.process_time_ns() - cpu
        calls.append({"index": index, "temperature": "cold" if index == 0 else "warm", "wall_ns": wall_ns,
                      "cpu_ns": cpu_ns, "cpu_utilization": cpu_ns / wall_ns if wall_ns else 0.0,
                      "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "combined": canonical_combined(combined)})
    result = {"campaign_id": CAMPAIGN_ID, "case_id": slot["slot_id"], "dimensions": [slot["m"], slot["n"]],
              "profile": slot["generator_parameters"]["profile"], "rhs_policy": slot["rhs_policy"],
              "matrix": matrix, "thread_configuration": thread_configuration(), "thermal": thermal_state(), "calls": calls}
    print(json.dumps(json_safe(result), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
