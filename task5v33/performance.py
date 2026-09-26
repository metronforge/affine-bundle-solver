"""Frozen baseline-versus-merged-candidate Task-5 v3.3 comparison."""

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json
from task5v31.runner import json_safe

CAMPAIGN_ID = "task5-v3.3-reusable-qrcp-20260926"
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
MEASUREMENT_FIELDS = {
    "campaign_id",
    "path",
    "library",
    "timing_ns",
    "cpu_time_ns",
    "peak_rss_kb",
    "thermal",
    "thread_configuration",
    "legacy_preliminary_lstsq_ns",
}


def controlled_environment(library):
    environment = os.environ.copy()
    environment.update({name: "4" for name in THREAD_VARIABLES})
    environment["TASK5_SOLVER_LIB"] = str(Path(library).resolve())
    return environment


def semantic_view(row):
    return {key: value for key, value in row.items() if key not in MEASUREMENT_FIELDS}


def coefficient_of_variation(values):
    return statistics.stdev(values) / statistics.fmean(values) if len(values) > 1 else 0.0


def geometric_mean(values):
    return math.exp(statistics.fmean(math.log(value) for value in values))


def file_sha256(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _trial(slot_id, path, library, environment):
    command = [sys.executable, "-m", "task5v31.runner", "--slot", slot_id]
    if path == "control":
        command.append("--legacy-preliminary-xt")
    completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment)
    row = json.loads(completed.stdout)
    row["campaign_id"] = CAMPAIGN_ID
    row["path"] = "legacy_equivalent_control" if path == "control" else "candidate_null_xt"
    row["library"] = {"path": str(Path(library).resolve()), "sha256": file_sha256(library)}
    return row


def run_comparison(slot_ids, *, baseline_library, candidate_library, repetitions=5):
    if repetitions < 5:
        raise ValueError("official comparison requires at least five eligible trials")
    libraries = {"control": Path(baseline_library), "candidate": Path(candidate_library)}
    environments = {path: controlled_environment(library) for path, library in libraries.items()}
    records = []
    for slot_index, slot_id in enumerate(slot_ids):
        for path in ("control", "candidate"):
            records.append({"slot_id": slot_id, "phase": "warmup", "path": path,
                            "record": _trial(slot_id, path, libraries[path], environments[path])})
        for trial in range(repetitions):
            order = ("control", "candidate") if (slot_index + trial) % 2 == 0 else ("candidate", "control")
            for path in order:
                records.append({"slot_id": slot_id, "phase": "eligible", "trial": trial, "path": path,
                                "order": list(order),
                                "record": _trial(slot_id, path, libraries[path], environments[path])})

    summaries = []
    for slot_id in slot_ids:
        eligible = [item for item in records if item["slot_id"] == slot_id and item["phase"] == "eligible"]
        control = [item["record"] for item in eligible if item["path"] == "control"]
        candidate = [item["record"] for item in eligible if item["path"] == "candidate"]
        control_wall = [row["timing_ns"]["total_wall"] for row in control]
        candidate_wall = [row["timing_ns"]["total_wall"] for row in candidate]
        control_median = statistics.median(control_wall)
        candidate_median = statistics.median(candidate_wall)
        control_rss = statistics.median(row["peak_rss_kb"] for row in control)
        candidate_rss = statistics.median(row["peak_rss_kb"] for row in candidate)
        summaries.append({
            "slot_id": slot_id,
            "eligible_trials": repetitions,
            "semantic_agreement": all(semantic_view(left) == semantic_view(right)
                                      for left, right in zip(control, candidate)),
            "candidate_router_executions": sorted({row["combined"]["router_executions"] for row in candidate}),
            "thermal_eligibility": sorted({row["thermal"]["eligibility"] for row in control + candidate}),
            "control_total_wall_ns": control_wall,
            "candidate_total_wall_ns": candidate_wall,
            "control_median_ns": control_median,
            "candidate_median_ns": candidate_median,
            "control_cv": coefficient_of_variation(control_wall),
            "candidate_cv": coefficient_of_variation(candidate_wall),
            "speedup": control_median / candidate_median,
            "control_combined_median_ns": statistics.median(row["timing_ns"]["combined_c_api"] for row in control),
            "candidate_combined_median_ns": statistics.median(row["timing_ns"]["combined_c_api"] for row in candidate),
            "control_peak_rss_kb": control_rss,
            "candidate_peak_rss_kb": candidate_rss,
            "rss_ratio": candidate_rss / control_rss,
        })

    speedup = geometric_mean([summary["speedup"] for summary in summaries])
    checks = {
        "geometric_mean_at_least_1_5": speedup >= 1.5,
        "no_slot_more_than_10_percent_slower": all(summary["candidate_median_ns"] <= 1.1 * summary["control_median_ns"] for summary in summaries),
        "semantic_agreement": all(summary["semantic_agreement"] for summary in summaries),
        "one_router_execution": all(summary["candidate_router_executions"] == [1] for summary in summaries),
        "rss_within_10_percent": all(summary["rss_ratio"] <= 1.1 for summary in summaries),
        "thermally_eligible": all(summary["thermal_eligibility"] == ["ELIGIBLE_NO_THROTTLE_SIGNAL"] for summary in summaries),
    }
    return {
        "campaign_id": CAMPAIGN_ID,
        "control_definition": "frozen f66cd87 solver plus the unchanged preliminary scipy gelsd xt solve; identical frozen input, API, four-thread configuration, and process isolation",
        "candidate_definition": "verified squash-merged solver with genuine NULL xt",
        "libraries": {path: {"path": str(library.resolve()), "sha256": file_sha256(library)}
                      for path, library in libraries.items()},
        "thread_configuration": {name: "4" for name in THREAD_VARIABLES},
        "records": records,
        "summaries": summaries,
        "geometric_mean_speedup": speedup,
        "pre_gate": {**checks, "passed": all(checks.values())},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-library", type=Path, required=True)
    parser.add_argument("--candidate-library", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--slots", nargs="*", default=["V31-025", "V31-026", "V31-027"])
    args = parser.parse_args()
    for library in (args.baseline_library, args.candidate_library):
        if not library.is_file():
            raise SystemExit(f"missing library: {library}")
    report = run_comparison(args.slots, baseline_library=args.baseline_library,
                            candidate_library=args.candidate_library, repetitions=args.repetitions)
    atomic_write(args.out, canonical_json(json_safe(report)))
    print(json.dumps({"geometric_mean_speedup": report["geometric_mean_speedup"],
                      "pre_gate": report["pre_gate"]}, sort_keys=True))


if __name__ == "__main__":
    main()
