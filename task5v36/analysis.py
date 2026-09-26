"""Frozen paired-log calibration analysis and selection rule."""

from __future__ import annotations

import argparse
import hashlib
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


def _arm_pairs(records, reference, candidate, field, slot):
    eligible = [row for row in records if row.get("phase") == "eligible" and
                row.get("slot_id") == slot and isinstance(row.get("record"), dict)]
    by_key = {(row["trial"], row["arm"]): row for row in eligible}
    trials = sorted({row["trial"] for row in eligible
                     if (row["trial"], reference) in by_key and
                        (row["trial"], candidate) in by_key})
    return [(by_key[trial, reference]["record"]["timing_ns"][field],
             by_key[trial, candidate]["record"]["timing_ns"][field])
            for trial in trials]


def _paired_comparison(records, reference, candidate, field, slot, *, samples, seed):
    pairs = _arm_pairs(records, reference, candidate, field, slot)
    if not pairs:
        return {"n": 0, "ratio_point": math.inf,
                "ratio_of_medians": math.inf, "speedup_of_medians": 0.0,
                "one_sided_95_upper": math.inf,
                "two_sided_95_ratio_ci": [math.inf, math.inf]}
    logs = [math.log(right / left) for left, right in pairs]
    rng = random.Random(seed)
    draws = [statistics.median(logs[rng.randrange(len(logs))]
                               for _ in logs) for _ in range(samples)]
    left = [pair[0] for pair in pairs]
    right = [pair[1] for pair in pairs]
    return {
        "n": len(pairs), "ratio_point": math.exp(statistics.median(logs)),
        "ratio_of_medians": statistics.median(right) / statistics.median(left),
        "speedup_of_medians": statistics.median(left) / statistics.median(right),
        "one_sided_95_upper": math.exp(_quantile(draws, 0.95)),
        "two_sided_95_ratio_ci": [math.exp(_quantile(draws, 0.025)),
                                   math.exp(_quantile(draws, 0.975))],
    }


def _meaningful_view(combined):
    return {key: combined.get(key) for key in (
        "api_return", "certified", "router_meta", "grey_distinct_count",
        "grey_total_events", "grey_rows", "core_rank_interval", "core_qr_rank",
        "formation_guard_counters")}


def _aggregate_speedup(records, *, samples, seed):
    slot_pairs = {slot: _arm_pairs(records, "L", "A", "total_wall", slot)
                  for slot in SLOTS}
    if any(not pairs for pairs in slot_pairs.values()):
        return {"per_slot_speedups": {}, "point_speedup": 0.0,
                "bootstrap_95_ci": [0.0, 0.0]}
    per_slot = {
        slot: statistics.median(left for left, _ in pairs) /
              statistics.median(right for _, right in pairs)
        for slot, pairs in slot_pairs.items()
    }
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        speedups = []
        for slot in SLOTS:
            pairs = slot_pairs[slot]
            sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
            speedups.append(statistics.median(left for left, _ in sample) /
                            statistics.median(right for _, right in sample))
        draws.append(math.prod(speedups) ** (1 / len(speedups)))
    return {"per_slot_speedups": per_slot,
            "point_speedup": math.prod(per_slot.values()) ** (1 / len(per_slot)),
            "bootstrap_95_ci": [_quantile(draws, 0.025),
                                 _quantile(draws, 0.975)]}


def qualification_decision(records, *, expected_libraries, integrity,
                           samples=100_000, seed=2026093699,
                           configuration="C1"):
    config = CONFIGURATIONS[configuration]
    eligible = [row for row in records if row.get("phase") == "eligible"]
    valid = [row for row in eligible if isinstance(row.get("record"), dict)]
    comparisons = {}
    for slot_index, slot in enumerate(SLOTS):
        for pair_index, (reference, candidate) in enumerate((
                ("L", "A"), ("M", "A"))):
            for field_index, field in enumerate(FIELDS):
                key = f"{slot}:{reference}/{candidate}:{field}"
                comparisons[key] = _paired_comparison(
                    records, reference, candidate, field, slot,
                    samples=samples,
                    seed=seed + 100 * slot_index + 10 * pair_index + field_index)
    aggregate = _aggregate_speedup(records, samples=samples, seed=seed + 900)

    complete = len(eligible) == len(SLOTS) * 3 * 31 and all(
        sum(row.get("slot_id") == slot and row.get("arm") == arm
            for row in eligible) == 31 for slot in SLOTS for arm in ("L", "M", "A"))
    by_key = {(row["slot_id"], row["trial"], row["arm"]): row["record"]
              for row in valid}
    meaningful = complete and all(
        _meaningful_view(by_key[slot, trial, "L"]["combined"]) ==
        _meaningful_view(by_key[slot, trial, "A"]["combined"]) and
        _meaningful_view(by_key[slot, trial, "M"]["combined"]) ==
        _meaningful_view(by_key[slot, trial, "A"]["combined"])
        for slot in SLOTS for trial in range(31))
    input_hashes = complete and all(
        by_key[slot, trial, "L"]["input"] == by_key[slot, trial, "M"]["input"] ==
        by_key[slot, trial, "A"]["input"]
        for slot in SLOTS for trial in range(31))
    libraries = all(row["record"].get("library", {}).get("sha256") ==
                    expected_libraries.get(row.get("arm")) for row in valid)

    fingerprints, runtime_ok = {}, True
    for arm in ("L", "M", "A"):
        policy = config.roles["legacy" if arm == "L" else "solver"]
        identities = set()
        for row in valid:
            if row.get("arm") != arm:
                continue
            verdict = fingerprint_eligible(row["record"]["runtime"], policy)
            runtime_ok &= verdict["passed"]
            identities.add(repr(verdict["identity"]))
        fingerprints[arm] = sorted(identities)
        runtime_ok &= len(identities) == 1
    runtime_ok &= fingerprints["M"] == fingerprints["A"]

    rss_ok = True
    for slot in SLOTS:
        medians = {arm: statistics.median(
            row["record"]["peak_rss_kb"] for row in valid
            if row.get("slot_id") == slot and row.get("arm") == arm)
            for arm in ("L", "M", "A")}
        rss_ok &= medians["A"] <= 1.10 * medians["M"]
        rss_ok &= medians["A"] <= 1.10 * medians["L"]

    checks = {
        "complete_eligible_set": complete,
        "no_execution_failures": all("execution_failure" not in row for row in records),
        "meaningful_fields_agree": meaningful,
        "router_once": all(row["record"]["combined"].get("router_executions") == 1
                           for row in valid if row.get("arm") == "A"),
        "v25_api_noninferior":
            comparisons["V31-025:M/A:combined_c_api"]["one_sided_95_upper"] < 1.03,
        "no_e2e_regression_over_10_percent": all(
            comparisons[f"{slot}:M/A:total_wall"]["ratio_of_medians"] <= 1.10
            for slot in SLOTS),
        "legacy_candidate_geomean_at_least_1_5": aggregate["point_speedup"] >= 1.5,
        "rss_within_10_percent": rss_ok,
        "thermal_valid": all(str(row["record"]["thermal"]["eligibility"])
                             .startswith("ELIGIBLE") for row in valid),
        "runtime_fingerprints_valid": runtime_ok,
        "production_api_gain": all(
            comparisons[f"{slot}:M/A:combined_c_api"]["speedup_of_medians"] > 1.0
            for slot in ("V31-026", "V31-027")),
        "wall_cpu_and_e2e_present": all(
            row["record"].get("worker_process_wall_ns", 0) > 0 and
            row["record"].get("cpu_time_ns", 0) > 0 for row in valid),
        "identity_and_evidence_integrity": bool(integrity and libraries and input_hashes),
    }
    return {"configuration": configuration, "comparisons": comparisons,
            "aggregate_legacy_candidate": aggregate,
            "runtime_fingerprints": fingerprints, "checks": checks,
            "passed": bool(checks) and all(checks.values())}


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
    qualification = subparsers.add_parser("qualification")
    qualification.add_argument("--configuration", choices=("C1", "C2"), required=True)
    qualification.add_argument("--input", type=argparse.FileType("r"), required=True)
    qualification.add_argument("--expected-library", action="append", required=True,
                               help="ARM=sha256")
    qualification.add_argument("--output", required=True)
    qualification.add_argument("--samples", type=int, default=100_000)
    qualification.add_argument("--seed", type=int, default=2026093699)
    qualification.add_argument("--integrity", action="store_true")
    args = parser.parse_args()
    if args.operation == "aa":
        report = json.load(args.input)
        result = aa_decision(report["records"], samples=args.samples,
                             seed=args.seed, configuration=args.configuration)
    elif args.operation == "select":
        decisions = {}
        for value in args.decision:
            name, path = value.split("=", 1)
            decisions[name] = json.loads(open(path, encoding="utf-8").read())
        result = {"decisions": decisions,
                  "selection": select_configuration(decisions)}
    else:
        expected = dict(value.split("=", 1) for value in args.expected_library)
        report = json.load(args.input)
        protocol_integrity = (
            report.get("complete") is True and
            report.get("protocol_sha256") ==
            hashlib.sha256(canonical_json(report.get("protocol"))).hexdigest())
        result = qualification_decision(
            report["records"], expected_libraries=expected,
            integrity=args.integrity and protocol_integrity,
            samples=args.samples, seed=args.seed,
            configuration=args.configuration)
    atomic_write(args.output, canonical_json(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
