"""Cycle 1: end-to-end and diagnostic-only phase decomposition."""

import argparse
import statistics
import sys
from pathlib import Path

from .diagnostics import BOUNDED_SLOT_IDS, build_trace_library, phase_ledger, run_slot, write_json


def median(values):
    return statistics.median(values)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True); parser.add_argument("--trials", type=int, default=5)
    args = parser.parse_args(); tracer = build_trace_library(args.build_dir)
    raw, summary = [], []
    for slot_id in BOUNDED_SLOT_IDS:
        raw.append({"slot_id": slot_id, "kind": "warmup_uninstrumented", **run_slot(slot_id)})
        raw.append({"slot_id": slot_id, "kind": "warmup_instrumented", **run_slot(slot_id, preload=tracer)})
        plain, traced = [], []
        for index in range(args.trials):
            uninstrumented = run_slot(slot_id); instrumented = run_slot(slot_id, preload=tracer)
            uninstrumented.update({"slot_id": slot_id, "kind": "production_uninstrumented", "trial": index})
            instrumented.update({"slot_id": slot_id, "kind": "diagnostic_instrumented", "trial": index})
            raw.extend((uninstrumented, instrumented)); plain.append(uninstrumented); traced.append(instrumented)
        plain_total = median([item["record"]["timing_ns"]["total_wall"] for item in plain])
        traced_ledgers = [phase_ledger(item["record"], item["trace"]) for item in traced]
        traced_total = median([item["total_wall_ns"] for item in traced_ledgers])
        components = []
        for name in [item["component"] for item in traced_ledgers[0]["phases"]]:
            rows = [next(item for item in ledger["phases"] if item["component"] == name) for ledger in traced_ledgers]
            inclusive, exclusive = median([row["inclusive_ns"] for row in rows]), median([row["exclusive_ns"] for row in rows])
            components.append({"component": name, "inclusive_median_ns": inclusive, "exclusive_median_ns": exclusive,
                               "exclusive_percent_of_instrumented_total": 100.0 * exclusive / traced_total})
        summary.append({"slot_id": slot_id, "production_trials": args.trials,
                        "uninstrumented_total_median_ns": plain_total, "instrumented_total_median_ns": traced_total,
                        "profiler_overhead_fraction": traced_total / plain_total - 1.0,
                        "instrumented_unattributed_median_ns": median([item["unattributed_ns"] for item in traced_ledgers]),
                        "phase_medians": components,
                        "peak_rss_uninstrumented_median_kb": median([item["record"]["peak_rss_kb"] for item in plain]),
                        "cpu_time_uninstrumented_median_ns": median([item["record"]["cpu_time_ns"] for item in plain])})
    payload = {"cycle": 1, "hypothesis": "one or two high-level phases explain most one-call runtime",
               "command": sys.argv, "clock": "time.perf_counter_ns / CLOCK_MONOTONIC_RAW",
               "safety": {"router_calls_per_candidate": 1, "production_and_instrumented_separate": True},
               "raw_records": raw, "summary": summary}
    write_json(args.out, payload)


if __name__ == "__main__":
    main()
