"""Isolated, deterministic alternating control/candidate performance trials."""

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

from .campaign import canonical_json, generate_manifest
from .runner import json_safe


def geometric_mean(values):
    return math.exp(statistics.fmean(math.log(value) for value in values))


def _trial(slot_id, legacy):
    command = [sys.executable, "-m", "task5v31.runner", "--slot", slot_id]
    if legacy: command.append("--legacy-preliminary-xt")
    completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, env=os.environ.copy())
    return json.loads(completed.stdout)


def _semantic_view(row):
    return {key: row[key] for key in ("matrix", "router_strategy", "standard_oracle", "contract_oracle", "combined")}


def run_benchmark(slot_ids, repetitions=3):
    records = []
    for slot_id in slot_ids:
        # One warm-up for each process-isolated path is intentionally retained but excluded.
        records.append({"slot_id": slot_id, "phase": "warmup", "path": "control", "record": _trial(slot_id, True)})
        records.append({"slot_id": slot_id, "phase": "warmup", "path": "candidate", "record": _trial(slot_id, False)})
        for trial in range(repetitions):
            order = (True, False) if trial % 2 == 0 else (False, True)
            for legacy in order:
                row = _trial(slot_id, legacy)
                records.append({"slot_id": slot_id, "phase": "eligible", "trial": trial,
                                "path": "control" if legacy else "candidate", "record": row})
    summaries = []
    for slot_id in slot_ids:
        eligible = [x for x in records if x["slot_id"] == slot_id and x["phase"] == "eligible"]
        control = [x["record"] for x in eligible if x["path"] == "control"]
        candidate = [x["record"] for x in eligible if x["path"] == "candidate"]
        agreement = all(_semantic_view(a) == _semantic_view(b) for a, b in zip(control, candidate))
        control_median = statistics.median(x["timing_ns"]["total_wall"] for x in control)
        candidate_median = statistics.median(x["timing_ns"]["total_wall"] for x in candidate)
        summaries.append({"slot_id": slot_id, "eligible_trials": repetitions, "semantic_agreement": agreement,
                          "control_median_ns": control_median, "candidate_median_ns": candidate_median,
                          "speedup": control_median / candidate_median,
                          "control_peak_rss_kb": statistics.median(x["peak_rss_kb"] for x in control),
                          "candidate_peak_rss_kb": statistics.median(x["peak_rss_kb"] for x in candidate)})
    return {"campaign_id": "task5-v3.1-performance-20260926", "control_definition":
            "same frozen input, solver library, combined API, threads and process isolation; only extra scipy gelsd xt", 
            "records": records, "summaries": summaries, "geometric_mean_speedup": geometric_mean([x["speedup"] for x in summaries])}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3); parser.add_argument("--slots", nargs="*")
    args = parser.parse_args()
    slots = args.slots or [s["slot_id"] for s in generate_manifest()["slots"] if s["eligibility"]["bounded_large"]]
    report = run_benchmark(slots, args.repetitions); args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical_json(json_safe(report))); print(json.dumps({"geometric_mean_speedup": report["geometric_mean_speedup"]}))


if __name__ == "__main__":
    main()
