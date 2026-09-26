"""Cycle 3: bounded size, thread, and warm/cold sensitivity."""

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

from .diagnostics import BOUNDED_SLOT_IDS, build_trace_library, controlled_environment, parse_trace_line, write_json


def run_case(arguments, threads, tracer):
    command = [sys.executable, "-m", "task5v32.sensitivity_trial", *arguments, "--repeats", "4"]
    environment = controlled_environment(threads, tracer); completed = subprocess.run(
        command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
    return {"command": command, "threads": threads, "record": json.loads(completed.stdout),
            "trace": parse_trace_line(completed.stderr), "stderr": completed.stderr}


def slope(points):
    xs, ys = [math.log(x) for x, _ in points], [math.log(y) for _, y in points]
    xbar, ybar = statistics.fmean(xs), statistics.fmean(ys)
    return sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys)) / sum((x-xbar)**2 for x in xs)


def summarize(row):
    calls = row["record"]["calls"]; warm = calls[1:]
    return {"case_id": row["record"]["case_id"], "dimensions": row["record"]["dimensions"], "threads": row["threads"],
            "cold_wall_ns": calls[0]["wall_ns"], "warm_wall_median_ns": statistics.median(x["wall_ns"] for x in warm),
            "warm_cpu_utilization_median": statistics.median(x["cpu_utilization"] for x in warm),
            "peak_rss_kb": max(x["peak_rss_kb"] for x in calls),
            "router_executions_per_call": sorted(set(x["combined"]["router_executions"] for x in calls)),
            "dgeqp3_count_per_call": row["trace"]["dgeqp3_count"] / len(calls),
            "dgeqp3_ns_per_call": row["trace"]["dgeqp3_ns"] / len(calls),
            "lapack_ns_per_call": row["trace"]["lapack_ns"] / len(calls),
            "thermal": row["record"]["thermal"]}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True); args = parser.parse_args()
    tracer = build_trace_library(args.build_dir); raw = []
    for slot in BOUNDED_SLOT_IDS:
        for threads in (1, 4): raw.append(run_case(["--slot", slot], threads, tracer))
    for m, n in ((128,64), (192,96), (256,128), (320,160)):
        raw.append(run_case(["--m", str(m), "--n", str(n)], 4, tracer))
    summary = [summarize(row) for row in raw]
    tall = [row for row in summary if row["case_id"].startswith("V32-TALL")]
    scaling = {"warm_wall_exponent_vs_n": slope([(row["dimensions"][1], row["warm_wall_median_ns"]) for row in tall]),
               "qrcp_time_exponent_vs_n": slope([(row["dimensions"][1], row["dgeqp3_ns_per_call"]) for row in tall]),
               "qrcp_calls_formula_observed": [[row["dimensions"], row["dgeqp3_count_per_call"]] for row in tall]}
    thread_effect = []
    for slot in BOUNDED_SLOT_IDS:
        one = next(row for row in summary if row["case_id"] == slot and row["threads"] == 1)
        four = next(row for row in summary if row["case_id"] == slot and row["threads"] == 4)
        thread_effect.append({"slot_id": slot, "one_thread_ns": one["warm_wall_median_ns"],
                              "four_thread_ns": four["warm_wall_median_ns"],
                              "four_thread_speedup": one["warm_wall_median_ns"] / four["warm_wall_median_ns"]})
    payload = {"cycle": 3, "hypothesis": "the dominant cost has a compute-scaling signature rather than fixed or allocation overhead",
               "matrix_justification": "three frozen slots at 1/4 threads plus four nearby 2:1 tall sizes at the official 4 threads",
               "raw_records": raw, "summary": summary, "scaling": scaling, "thread_effect": thread_effect}
    write_json(args.out, payload)


if __name__ == "__main__":
    main()
