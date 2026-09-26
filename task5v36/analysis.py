"""Frozen paired-log calibration analysis and selection rule."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics

from task5v36.runtime import CONFIGURATIONS, fingerprint_eligible, fingerprint_identity
from task5v31.campaign import atomic_write, canonical_json


SLOTS = ("V31-025", "V31-026", "V31-027")
FIELDS = ("combined_c_api", "total_wall")


def _quantile(values, probability):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(probability * len(ordered)))]


def _pairs(records, field, slot):
    eligible = [row for row in records if row.get("phase") == "eligible" and
                row.get("slot_id") == slot and isinstance(row.get("record"), dict)]
    by_key = {(row["trial"], row["arm"]): row for row in eligible}
    trials = sorted({row["trial"] for row in eligible
                     if (row["trial"], "M1") in by_key and
                        (row["trial"], "M2") in by_key})
    return [(by_key[trial, "M1"]["record"]["timing_ns"][field],
             by_key[trial, "M2"]["record"]["timing_ns"][field],
             by_key[trial, "M2"]["order"]) for trial in trials]


def _metric(pairs, *, samples, seed):
    logs = [math.log(right / left) for left, right, _ in pairs]
    rng = random.Random(seed)
    draws = [statistics.median(logs[rng.randrange(len(logs))]
                               for _ in logs) for _ in range(samples)]
    point = statistics.median(logs)
    return {"n": len(logs), "ratio_point": math.exp(point),
            "one_sided_95_upper": math.exp(_quantile(draws, 0.95)),
            "two_sided_95_ratio_ci": [math.exp(_quantile(draws, 0.025)),
                                       math.exp(_quantile(draws, 0.975))]}


def _order_effect(pairs, *, samples, seed):
    first = [math.log(right / left) for left, right, order in pairs
             if order.index("M2") < order.index("M1")]
    second = [math.log(right / left) for left, right, order in pairs
              if order.index("M2") > order.index("M1")]
    if not first or not second:
        return {"difference": math.inf, "bootstrap_95_ci": [math.inf, math.inf],
                "passed": False}
    difference = statistics.median(first) - statistics.median(second)
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        a = [first[rng.randrange(len(first))] for _ in first]
        b = [second[rng.randrange(len(second))] for _ in second]
        draws.append(statistics.median(a) - statistics.median(b))
    interval = [_quantile(draws, 0.025), _quantile(draws, 0.975)]
    return {"difference": difference, "bootstrap_95_ci": interval,
            "passed": abs(difference) < math.log(1.02) and
                      interval[0] <= 0.0 <= interval[1]}


def aa_decision(records, *, samples=100_000, seed=2026093699,
                configuration):
    config = CONFIGURATIONS[configuration]
    metrics, order_effects = [], []
    complete = True
    for slot_index, slot in enumerate(SLOTS):
        for field_index, field in enumerate(FIELDS):
            pairs = _pairs(records, field, slot)
            complete &= len(pairs) == 31
            if pairs:
                metrics.append({"slot_id": slot, "field": field,
                                **_metric(pairs, samples=samples,
                                          seed=seed + 10 * slot_index + field_index)})
                order_effects.append({"slot_id": slot, "field": field,
                                      **_order_effect(
                                          pairs, samples=samples,
                                          seed=seed + 100 + 10 * slot_index + field_index)})
    eligible = [row for row in records if row.get("phase") == "eligible"]
    valid = [row for row in eligible if isinstance(row.get("record"), dict)]
    fingerprints = {}
    policy = config.roles["solver"]
    fingerprint_policy_ok = True
    for arm in ("M1", "M2"):
        identities = []
        for row in valid:
            if row["arm"] != arm:
                continue
            verdict = fingerprint_eligible(row["record"]["runtime"], policy)
            fingerprint_policy_ok &= verdict["passed"]
            identities.append(fingerprint_identity(row["record"]["runtime"]))
        fingerprints[arm] = {repr(value) for value in identities}
    matching = fingerprints["M1"] == fingerprints["M2"] and bool(fingerprints["M1"])
    thermal = all(str(row["record"]["thermal"]["eligibility"]).startswith("ELIGIBLE")
                  for row in valid)
    budgets = all(row["record"].get("active_compute_budget") == config.active_threads
                  for row in valid)
    expected_affinity = sorted(int(cpu) for cpu in config.cpu_set.split(","))
    affinity = all(row["record"]["runtime"].get("process_affinity") == expected_affinity
                   for row in valid)
    checks = {
        "complete_eligible_set": complete and len(eligible) == 3 * 2 * 31,
        "one_sided_upper_below_1_03": len(metrics) == 6 and
            all(item["one_sided_95_upper"] < 1.03 for item in metrics),
        "no_preregistered_order_effect": len(order_effects) == 6 and
            all(item["passed"] for item in order_effects),
        "matching_runtime_fingerprints": matching,
        "runtime_policy_valid": fingerprint_policy_ok,
        "thermal_valid": thermal,
        "equal_active_compute_budget": budgets,
        "fixed_cpu_affinity": affinity,
        "no_execution_failures": all("execution_failure" not in row for row in records),
    }
    api = [item["one_sided_95_upper"] for item in metrics
           if item["field"] == "combined_c_api"]
    main_e2e = [row["record"]["timing_ns"]["total_wall"] for row in valid
                if row["arm"] in ("M1", "M2")]
    return {"configuration": configuration, "metrics": metrics,
            "order_effects": order_effects,
            "fingerprints": {key: sorted(value) for key, value in fingerprints.items()},
            "checks": checks, "passed": all(checks.values()),
            "maximum_api_upper": max(api) if api else math.inf,
            "aggregate_main_e2e_median_ns": statistics.median(main_e2e)
            if main_e2e else math.inf}


def select_configuration(decisions):
    eligible = {name: value for name, value in decisions.items()
                if name in ("C1", "C2") and value.get("passed")}
    if not eligible:
        return {"selected": None, "reason": "no_selectable_configuration_passed"}
    ranked = sorted(eligible, key=lambda name: eligible[name]["maximum_api_upper"])
    best = ranked[0]
    if len(ranked) > 1:
        other = ranked[1]
        if abs(eligible[best]["maximum_api_upper"] -
               eligible[other]["maximum_api_upper"]) <= 0.005:
            best = min((best, other), key=lambda name:
                       eligible[name]["aggregate_main_e2e_median_ns"])
            reason = "api_upper_tie_within_0.005_then_lower_e2e_median"
        else:
            reason = "smallest_maximum_api_upper"
    else:
        reason = "only_eligible_configuration"
    return {"selected": best, "reason": reason,
            "eligible": sorted(eligible)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    aa = subparsers.add_parser("aa")
    aa.add_argument("--configuration", choices=("C1", "C2", "C3"), required=True)
    aa.add_argument("--input", type=argparse.FileType("r"), required=True)
    aa.add_argument("--output", required=True)
    aa.add_argument("--samples", type=int, default=100_000)
    aa.add_argument("--seed", type=int, default=2026093699)
    select = subparsers.add_parser("select")
    select.add_argument("--decision", action="append", required=True,
                        help="NAME=analysis.json")
    select.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.operation == "aa":
        report = json.load(args.input)
        result = aa_decision(report["records"], samples=args.samples,
                             seed=args.seed, configuration=args.configuration)
    else:
        decisions = {}
        for value in args.decision:
            name, path = value.split("=", 1)
            decisions[name] = json.loads(open(path, encoding="utf-8").read())
        result = {"decisions": decisions,
                  "selection": select_configuration(decisions)}
    atomic_write(args.output, canonical_json(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
