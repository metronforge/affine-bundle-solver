"""Cycle 4: independent reproduction, falsification, and baseline confirmation."""

import argparse
import hashlib
import json
import os
import statistics
import subprocess
from pathlib import Path

from task5v31.benchmark import run_benchmark
from task5v31.campaign import generate_manifest

from .diagnostics import (BOUNDED_SLOT_IDS, build_reproduction_driver, coefficient_of_variation,
                          controlled_environment, parse_driver_csv, run_slot, write_binary_input, write_json)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True); parser.add_argument("--cycle1", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=5); args = parser.parse_args()
    driver = build_reproduction_driver(args.build_dir); environment = controlled_environment(4)
    slots = {slot["slot_id"]: slot for slot in generate_manifest()["slots"] if slot["slot_id"] in BOUNDED_SLOT_IDS}
    driver_raw, driver_summary = [], []
    for slot_id in BOUNDED_SLOT_IDS:
        input_path = write_binary_input(args.build_dir / f"{slot_id}.bin", slots[slot_id])
        command = [str(driver), str(input_path), str(args.trials)]
        completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        rows = parse_driver_csv(completed.stdout)
        driver_raw.append({"slot_id": slot_id, "command": command, "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                           "stdout": completed.stdout, "stderr": completed.stderr, "rows": rows})
        combined = [row["combined_ns"] for row in rows]; generator = [row["inconsistent_generator_ns"] for row in rows]
        driver_summary.append({"slot_id": slot_id, "combined_median_ns": statistics.median(combined),
                               "combined_cv": coefficient_of_variation(combined),
                               "inconsistent_generator_median_ns": statistics.median(generator),
                               "generator_share_of_combined": statistics.median(generator) / statistics.median(combined),
                               "router_median_ns": statistics.median(row["router_ns"] for row in rows),
                               "verifier_median_ns": statistics.median(row["inconsistent_verifier_ns"] for row in rows),
                               "all_return_codes_zero": all(row["api_rc"] == row["gen_rc"] == row["verify_rc"] == 0 for row in rows)})
    minimal_raw, minimal_summary = [], []
    for slot_id in BOUNDED_SLOT_IDS:
        run_slot(slot_id)  # warmup, excluded
        rows = [run_slot(slot_id) for _ in range(args.trials)]; minimal_raw.extend({"slot_id": slot_id, **row} for row in rows)
        totals = [row["record"]["timing_ns"]["total_wall"] for row in rows]
        minimal_summary.append({"slot_id": slot_id, "median_ns": statistics.median(totals), "cv": coefficient_of_variation(totals),
                                "router_execution_values": sorted(set(row["record"]["combined"]["router_executions"] for row in rows))})
    full_control = run_benchmark(list(BOUNDED_SLOT_IDS), repetitions=args.trials)
    cycle1 = json.loads(args.cycle1.read_text()); baseline = {row["slot_id"]: row for row in cycle1["summary"]}
    drift = [{"slot_id": row["slot_id"], "cycle1_median_ns": baseline[row["slot_id"]]["uninstrumented_total_median_ns"],
              "cycle4_median_ns": row["median_ns"], "ratio": row["median_ns"] / baseline[row["slot_id"]]["uninstrumented_total_median_ns"]}
             for row in minimal_summary]
    candidate_records = [row["record"] for row in full_control["records"] if row["phase"] == "eligible" and row["path"] == "candidate"]
    payload = {"cycle": 4, "hypothesis": "the repeated compatible-tall QRCP scan is independently reproducible and remains dominant",
               "independent_method": "standalone C driver timing public combined/router/inconsistent-generator/verifier APIs",
               "driver_raw": driver_raw, "driver_summary": driver_summary,
               "falsification": {"alternative": "generic matrix size or memory traffic explains V31-027",
                 "test": "compare V31-027 with the larger-element-count V31-026 under standalone C timing",
                 "v31_027_to_v31_026_combined_ratio": next(x["combined_median_ns"] for x in driver_summary if x["slot_id"]=="V31-027") / next(x["combined_median_ns"] for x in driver_summary if x["slot_id"]=="V31-026"),
                 "result": "generic-size alternative falsified if ratio materially exceeds one"},
               "minimal_uninstrumented_raw": minimal_raw, "minimal_uninstrumented_summary": minimal_summary,
               "cycle1_to_cycle4_drift": drift, "full_legacy_control_comparison": full_control,
               "correctness": {"semantic_agreement_all_slots": all(row["semantic_agreement"] for row in full_control["summaries"]),
                 "candidate_router_executions": sorted(set(row["combined"]["router_executions"] for row in candidate_records)),
                 "candidate_trial_count": len(candidate_records),
                 "thermal_eligibility": sorted(set(row["thermal"]["eligibility"] for row in candidate_records))}}
    write_json(args.out, payload)


if __name__ == "__main__":
    main()
