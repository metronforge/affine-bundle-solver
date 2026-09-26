"""Independent-computation inputs for v3.7 qualification review."""

from __future__ import annotations

import argparse
import json
import math
import statistics

from task5v31.campaign import atomic_write, canonical_json


SLOTS = ("V31-025", "V31-026", "V31-027")
ARMS = ("L", "M", "A")
FIELDS = ("combined_c_api", "total_wall")


def coefficient_of_variation(values):
    values = list(values)
    mean = statistics.mean(values)
    return statistics.stdev(values) / mean if len(values) > 1 and mean else 0.0


def order_summary(pairs, reference, candidate):
    before = [math.log(right / left) for left, right, order in pairs
              if order.index(candidate) < order.index(reference)]
    after = [math.log(right / left) for left, right, order in pairs
             if order.index(candidate) > order.index(reference)]
    return {
        "candidate_before_reference_n": len(before),
        "candidate_after_reference_n": len(after),
        "candidate_before_reference_median_ratio":
            math.exp(statistics.median(before)) if before else None,
        "candidate_after_reference_median_ratio":
            math.exp(statistics.median(after)) if after else None,
        "log_ratio_difference": statistics.median(before) - statistics.median(after)
            if before and after else None,
    }


def schedule_matches(records, schedule):
    if len(records) != len(schedule):
        return False
    return all(
        {key: value for key, value in row.items()
         if key not in ("record", "execution_failure")} == expected
        for row, expected in zip(records, schedule)
    )


def audit(report, schedule):
    records = report["records"]
    schedule_match = schedule_matches(records, schedule)
    eligible = [row for row in records if row["phase"] == "eligible"]
    successful = [row for row in eligible if isinstance(row.get("record"), dict)]
    summaries, orders = {}, {}
    for slot in SLOTS:
        for arm in ARMS:
            arm_rows = [row["record"] for row in successful
                        if row["slot_id"] == slot and row["arm"] == arm]
            summaries[f"{slot}:{arm}"] = {
                "n": len(arm_rows),
                "api_median_ns": statistics.median(
                    row["timing_ns"]["combined_c_api"] for row in arm_rows),
                "api_cv": coefficient_of_variation(
                    row["timing_ns"]["combined_c_api"] for row in arm_rows),
                "e2e_median_ns": statistics.median(
                    row["timing_ns"]["total_wall"] for row in arm_rows),
                "e2e_cv": coefficient_of_variation(
                    row["timing_ns"]["total_wall"] for row in arm_rows),
                "cpu_median_ns": statistics.median(row["cpu_time_ns"] for row in arm_rows),
                "rss_median_kb": statistics.median(row["peak_rss_kb"] for row in arm_rows),
            }
        for reference in ("L", "M"):
            for field in FIELDS:
                by_trial = {(row["trial"], row["arm"]): row for row in eligible
                            if row["slot_id"] == slot and isinstance(row.get("record"), dict)}
                pairs = [(by_trial[t, reference]["record"]["timing_ns"][field],
                          by_trial[t, "A"]["record"]["timing_ns"][field],
                          tuple(by_trial[t, "A"]["order"])) for t in range(31)]
                orders[f"{slot}:{reference}/A:{field}"] = order_summary(
                    pairs, reference, "A")
    candidate = [row["record"] for row in records
                 if row["arm"] == "A" and isinstance(row.get("record"), dict)]
    valid = [row["record"] for row in records if isinstance(row.get("record"), dict)]
    return {
        "record_accounting": {
            "scheduled": len(schedule), "retained": len(records),
            "eligible": len(eligible), "successful_eligible": len(successful),
            "warmups": sum(row["phase"] == "warmup" for row in records),
            "execution_failures": sum("execution_failure" in row for row in records),
        },
        "schedule_exact_match": schedule_match,
        "candidate_router_once": len(candidate) == 96 and all(
            row["combined"].get("router_executions") == 1 for row in candidate),
        "bootstrap_openblas_four": all(
            row.get("bootstrap_openblas_threads") == "4" for row in valid),
        "returncodes_zero": all(row.get("process_returncode") == 0 for row in valid),
        "affinity_fixed": all(row["runtime"]["process_affinity"] == [1, 3, 6, 8]
                              for row in valid),
        "thermal_invalid_count": sum(
            not str(row["thermal"]["eligibility"]).startswith("ELIGIBLE") for row in valid),
        "summaries": summaries,
        "order_effects": orders,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(json.load(open(args.input)), json.load(open(args.schedule)))
    atomic_write(args.output, canonical_json(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
