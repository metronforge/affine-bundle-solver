"""Pre-registered v3.4 branch and post-merge bounded-large protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json
from task5v31.runner import json_safe
from task5v33.performance import semantic_view

CAMPAIGN_ID = "task5-v3.4-shared-overhead-20260926"
SLOTS = ("V31-025", "V31-026", "V31-027")
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
FROZEN_V33_SPEEDUPS = {"V31-025": 1.1914408315496332,
                       "V31-026": 1.0128628893142817,
                       "V31-027": 2.540193239515411}
FROZEN_V33_GEOMEAN = 1.4526577258405202


def mad(values):
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def coefficient_of_variation(values):
    return statistics.stdev(values) / statistics.fmean(values) if len(values) > 1 else 0.0


def bootstrap_median_ratio_ci(ratios, *, samples=10_000, seed=20260926):
    rng = random.Random(seed)
    n = len(ratios)
    draws = sorted(statistics.median(ratios[rng.randrange(n)] for _ in range(n))
                   for _ in range(samples))
    return [draws[int(0.025 * samples)], draws[min(samples - 1, int(0.975 * samples))]]


def _metric(control, candidate, field, *, bootstrap_samples):
    left = [row["timing_ns"][field] for row in control]
    right = [row["timing_ns"][field] for row in candidate]
    ratios = [a / b for a, b in zip(left, right, strict=True)]
    return {"control_raw_ns": left, "candidate_raw_ns": right,
            "control_median_ns": statistics.median(left),
            "candidate_median_ns": statistics.median(right),
            "control_mad_ns": mad(left), "candidate_mad_ns": mad(right),
            "control_cv": coefficient_of_variation(left),
            "candidate_cv": coefficient_of_variation(right),
            "paired_ratios": ratios,
            "paired_ratio_median": statistics.median(ratios),
            "bootstrap_95_ci": bootstrap_median_ratio_ci(
                ratios, samples=bootstrap_samples, seed=20260926),
            "median_speedup": statistics.median(left) / statistics.median(right)}


def summarize_pairs(control, candidate, *, bootstrap_samples=10_000):
    control_rss = statistics.median(row["peak_rss_kb"] for row in control)
    candidate_rss = statistics.median(row["peak_rss_kb"] for row in candidate)
    return {"api": _metric(control, candidate, "combined_c_api",
                           bootstrap_samples=bootstrap_samples),
            "end_to_end": _metric(control, candidate, "total_wall",
                                  bootstrap_samples=bootstrap_samples),
            "control_peak_rss_median_kb": control_rss,
            "candidate_peak_rss_median_kb": candidate_rss,
            "rss_ratio": candidate_rss / control_rss}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def controlled_environment(library):
    env = os.environ.copy()
    env.update({name: "4" for name in THREAD_VARIABLES})
    env["TASK5_SOLVER_LIB"] = str(Path(library).resolve())
    env["LD_LIBRARY_PATH"] = str(Path(library).resolve().parent)
    return env


def trial(slot_id, path, library):
    command = [sys.executable, "-m", "task5v31.runner", "--slot", slot_id]
    completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=controlled_environment(library))
    row = json.loads(completed.stdout)
    row["campaign_id"] = CAMPAIGN_ID
    row["path"] = path
    row["library"] = {"path": str(Path(library).resolve()), "sha256": sha256(library)}
    return {"command": command, "record": row, "stderr": completed.stderr}


def run_comparison(*, baseline_library, candidate_library, repetitions=11,
                   bootstrap_samples=10_000):
    if repetitions != 11:
        raise ValueError("v3.4 protocol requires exactly 11 eligible trials")
    libraries = {"baseline": Path(baseline_library), "candidate": Path(candidate_library)}
    records = []
    for slot_index, slot_id in enumerate(SLOTS):
        for path in ("baseline", "candidate"):
            records.append({"slot_id": slot_id, "phase": "excluded_warmup", "path": path,
                            **trial(slot_id, path, libraries[path])})
        for trial_index in range(repetitions):
            order = (("baseline", "candidate") if (slot_index + trial_index) % 2 == 0
                     else ("candidate", "baseline"))
            for path in order:
                records.append({"slot_id": slot_id, "phase": "eligible", "trial": trial_index,
                                "path": path, "order": list(order),
                                **trial(slot_id, path, libraries[path])})
    summaries = []
    for slot_id in SLOTS:
        eligible = [item for item in records if item["slot_id"] == slot_id and item["phase"] == "eligible"]
        control = [item["record"] for item in eligible if item["path"] == "baseline"]
        candidate = [item["record"] for item in eligible if item["path"] == "candidate"]
        summary = summarize_pairs(control, candidate, bootstrap_samples=bootstrap_samples)
        summary.update({"slot_id": slot_id, "eligible_trials_per_path": repetitions,
                        "semantic_agreement": all(semantic_view(a) == semantic_view(b)
                                                  for a, b in zip(control, candidate, strict=True)),
                        "candidate_router_executions": sorted({row["combined"]["router_executions"] for row in candidate}),
                        "thermal_eligibility": sorted({row["thermal"]["eligibility"] for row in control + candidate})})
        summary["projected_legacy_speedup"] = (FROZEN_V33_SPEEDUPS[slot_id] *
                                                summary["end_to_end"]["median_speedup"])
        summaries.append(summary)
    gm = math.prod(row["projected_legacy_speedup"] for row in summaries) ** (1 / 3)
    checks = {
        "correctness": all(row["semantic_agreement"] for row in summaries),
        "one_router_execution": all(row["candidate_router_executions"] == [1] for row in summaries),
        "api_improvement_at_least_two_slots": sum(row["api"]["median_speedup"] > 1.0 for row in summaries) >= 2,
        "no_api_regression_over_3_percent": all(row["api"]["median_speedup"] >= 1 / 1.03 for row in summaries),
        "end_to_end_geomean_improves": gm > FROZEN_V33_GEOMEAN,
        "rss_within_10_percent": all(row["rss_ratio"] <= 1.10 for row in summaries),
        "thermally_eligible": all(row["thermal_eligibility"] == ["ELIGIBLE_NO_THROTTLE_SIGNAL"] for row in summaries),
    }
    return {"campaign_id": CAMPAIGN_ID,
            "protocol": {"excluded_warmups_per_path_per_slot": 1,
                         "eligible_trials_per_path_per_slot": 11,
                         "order": "deterministic alternating", "selective_reruns": False,
                         "threads": {name: "4" for name in THREAD_VARIABLES}},
            "libraries": {name: {"path": str(path.resolve()), "sha256": sha256(path)}
                          for name, path in libraries.items()},
            "records": records, "summaries": summaries,
            "frozen_v33_geometric_mean": FROZEN_V33_GEOMEAN,
            "projected_legacy_geometric_mean": gm,
            "qualification_gate": {**checks, "passed": all(checks.values())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-library", type=Path, required=True)
    parser.add_argument("--candidate-library", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run_comparison(baseline_library=args.baseline_library,
                            candidate_library=args.candidate_library)
    atomic_write(args.out, canonical_json(json_safe(report)))
    print(json.dumps({"projected_legacy_geometric_mean": report["projected_legacy_geometric_mean"],
                      "qualification_gate": report["qualification_gate"]}, sort_keys=True))


if __name__ == "__main__":
    main()
