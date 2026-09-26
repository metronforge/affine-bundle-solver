"""Frozen paired-log analysis for Task-5 v3.5."""

from __future__ import annotations

import math
import os
import random
import statistics
import argparse
import json
from pathlib import Path

from task5v33.performance import MEASUREMENT_FIELDS
from task5v31.campaign import atomic_write, canonical_json
from task5v31.runner import json_safe


SLOTS = ("V31-025", "V31-026", "V31-027")


def _pairs(records, reference, candidate, field, slot_id=None):
    eligible = [row for row in records if row["phase"] == "eligible"
                and (slot_id is None or row["slot_id"] == slot_id)]
    by_key = {(row["trial"], row["arm"]): row for row in eligible}
    trials = sorted({row["trial"] for row in eligible if row["arm"] == reference})
    pairs = []
    for trial in trials:
        left = by_key[(trial, reference)]["record"]["timing_ns"][field]
        right = by_key[(trial, candidate)]["record"]["timing_ns"][field]
        pairs.append((left, right, by_key[(trial, candidate)]["order"]))
    return pairs


def _quantile(values, probability):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(probability * len(ordered)))]


def mad(values):
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def cv(values):
    return statistics.stdev(values) / statistics.fmean(values) if len(values) > 1 else 0.0


def compare_paired(records, reference, candidate, field, *, samples=100_000,
                   seed=20260926, slot_id=None):
    pairs = _pairs(records, reference, candidate, field, slot_id)
    if not pairs:
        raise ValueError("no eligible paired observations")
    ref = [pair[0] for pair in pairs]
    cand = [pair[1] for pair in pairs]
    logs = [math.log(right / left) for left, right, _ in pairs]
    rng = random.Random(seed)
    boot = [statistics.median(logs[rng.randrange(len(logs))]
                              for _ in range(len(logs))) for _ in range(samples)]
    point = statistics.median(logs)
    return {
        "reference": reference,
        "candidate": candidate,
        "field": field,
        "n": len(pairs),
        "reference_raw_ns": ref,
        "candidate_raw_ns": cand,
        "reference_median_ns": statistics.median(ref),
        "candidate_median_ns": statistics.median(cand),
        "reference_mad_ns": mad(ref),
        "candidate_mad_ns": mad(cand),
        "reference_cv": cv(ref),
        "candidate_cv": cv(cand),
        "paired_log_ratios": logs,
        "ratio_point": math.exp(point),
        "speedup_point": math.exp(-point),
        "ratio_of_medians_speedup": statistics.median(ref) / statistics.median(cand),
        "one_sided_95_upper": math.exp(_quantile(boot, 0.95)),
        "two_sided_95_ratio_ci": [math.exp(_quantile(boot, 0.025)),
                                  math.exp(_quantile(boot, 0.975))],
    }


def aggregate_speedup(records, reference, candidate, field, *, samples=100_000,
                      seed=20260926):
    slot_pairs = {slot: _pairs(records, reference, candidate, field, slot)
                  for slot in SLOTS}
    if any(not pairs for pairs in slot_pairs.values()):
        raise ValueError("missing slot observations")
    per_slot = {}
    for slot, pairs in slot_pairs.items():
        ref = [pair[0] for pair in pairs]
        cand = [pair[1] for pair in pairs]
        per_slot[slot] = statistics.median(ref) / statistics.median(cand)
    point = math.prod(per_slot.values()) ** (1 / len(SLOTS))
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        speedups = []
        for slot in SLOTS:
            pairs = slot_pairs[slot]
            sample = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
            speedups.append(statistics.median(x[0] for x in sample) /
                            statistics.median(x[1] for x in sample))
        draws.append(math.prod(speedups) ** (1 / len(speedups)))
    return {"reference": reference, "candidate": candidate, "field": field,
            "per_slot_speedups": per_slot, "point_speedup": point,
            "bootstrap_95_ci": [_quantile(draws, 0.025), _quantile(draws, 0.975)]}


def qualification_gate(checks):
    return {**checks, "passed": bool(checks) and all(checks.values())}


def _order_effect(records, reference, candidate, field, slot_id, *, samples, seed):
    pairs = _pairs(records, reference, candidate, field, slot_id)
    first = [math.log(right / left) for left, right, order in pairs
             if order.index(candidate) < order.index(reference)]
    second = [math.log(right / left) for left, right, order in pairs
              if order.index(candidate) > order.index(reference)]
    if not first or not second:
        return {"difference": math.inf, "bootstrap_95_ci": [math.inf, math.inf],
                "ci_contains_zero": False}
    difference = statistics.median(first) - statistics.median(second)
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        a = [first[rng.randrange(len(first))] for _ in range(len(first))]
        b = [second[rng.randrange(len(second))] for _ in range(len(second))]
        draws.append(statistics.median(a) - statistics.median(b))
    interval = [_quantile(draws, 0.025), _quantile(draws, 0.975)]
    return {"difference": difference, "bootstrap_95_ci": interval,
            "ci_contains_zero": interval[0] <= 0.0 <= interval[1]}


def _library_fingerprint(record):
    return tuple(sorted(os.path.basename(path)
                        for path in record.get("loaded_numeric_libraries", [])))


def aa_decision(records, *, samples=100_000, seed=20260926):
    slots = sorted({row["slot_id"] for row in records if row["phase"] == "eligible"})
    metrics = []
    effects = []
    for index, slot in enumerate(slots):
        for field in ("combined_c_api", "total_wall"):
            metrics.append({"slot_id": slot,
                            **compare_paired(records, "M1", "M2", field,
                                             samples=samples, seed=seed + index,
                                             slot_id=slot)})
            effects.append({"slot_id": slot, "field": field,
                            **_order_effect(records, "M1", "M2", field, slot,
                                            samples=samples, seed=seed + 100 + index)})
    eligible = [row for row in records if row["phase"] == "eligible"]
    fingerprints = {arm: sorted({_library_fingerprint(row["record"])
                                 for row in eligible if row["arm"] == arm})
                    for arm in ("M1", "M2")}
    checks = {
        "point_near_one": all(0.97 <= item["ratio_point"] <= 1.03 for item in metrics),
        "one_sided_upper_below_1_03": all(item["one_sided_95_upper"] < 1.03
                                          for item in metrics),
        "no_systematic_order_effect": all(abs(item["difference"]) < math.log(1.02)
                                           and item["ci_contains_zero"]
                                           for item in effects),
        "same_loaded_libraries": fingerprints["M1"] == fingerprints["M2"],
    }
    return {"metrics": metrics, "order_effects": effects,
            "library_fingerprints": fingerprints, **qualification_gate(checks)}


def semantic_view(record):
    excluded = set(MEASUREMENT_FIELDS) | {
        "arm", "loaded_numeric_libraries", "process_affinity"
    }
    return {key: value for key, value in record.items() if key not in excluded}


def _semantic_agreement(records, left_arm, right_arm):
    eligible = [row for row in records if row["phase"] == "eligible"]
    by_key = {(row["slot_id"], row["trial"], row["arm"]): row["record"]
              for row in eligible}
    keys = sorted((row["slot_id"], row["trial"]) for row in eligible
                  if row["arm"] == left_arm)
    return all(semantic_view(by_key[slot, trial, left_arm]) ==
               semantic_view(by_key[slot, trial, right_arm])
               for slot, trial in keys)


def official_decision(records, *, samples=100_000, seed=20260926,
                      integrity=False):
    comparisons = {}
    for slot_index, slot in enumerate(SLOTS):
        for pair_index, (left, right) in enumerate((
                ("L", "A"), ("M", "F"), ("F", "A"), ("M", "A"))):
            for field in ("combined_c_api", "total_wall"):
                key = f"{slot}:{left}/{right}:{field}"
                comparisons[key] = compare_paired(
                    records, left, right, field, samples=samples,
                    seed=seed + 100 * slot_index + 10 * pair_index,
                    slot_id=slot)
    aggregate = aggregate_speedup(records, "L", "A", "total_wall",
                                  samples=samples, seed=seed + 900)
    v25 = comparisons["V31-025:M/A:combined_c_api"]
    eligible = [row for row in records if row["phase"] == "eligible"]

    rss_ok = True
    for slot in SLOTS:
        medians = {}
        for arm in ("L", "M", "F", "A"):
            values = [row["record"]["peak_rss_kb"] for row in eligible
                      if row["slot_id"] == slot and row["arm"] == arm]
            medians[arm] = statistics.median(values)
        rss_ok &= all(medians["A"] <= 1.10 * medians[arm]
                      for arm in ("L", "M", "F"))

    checks = {
        "correctness": all(_semantic_agreement(records, left, right)
                           for left, right in (("L", "A"), ("M", "F"),
                                               ("F", "A"), ("M", "A"))),
        "router_once": all(row["record"]["combined"]["router_executions"] == 1
                           for row in eligible),
        "complete_eligible_set": all(
            sum(row["slot_id"] == slot and row["arm"] == arm
                for row in eligible) == 31
            for slot in SLOTS for arm in ("L", "M", "F", "A")),
        "v25_api_noninferior": v25["one_sided_95_upper"] < 1.03,
        "no_e2e_regression_over_10_percent": all(
            comparisons[f"{slot}:L/A:total_wall"]["ratio_of_medians_speedup"]
            >= 1 / 1.10 for slot in SLOTS),
        "legacy_candidate_geomean_at_least_1_5": aggregate["point_speedup"] >= 1.5,
        "rss_within_10_percent": rss_ok,
        "thermal_valid": all(row["record"]["thermal"]["eligibility"] ==
                             "ELIGIBLE_NO_THROTTLE_SIGNAL" for row in eligible),
        "production_api_gain": all(
            comparisons[f"{slot}:M/A:combined_c_api"]["ratio_of_medians_speedup"] > 1.0
            for slot in ("V31-026", "V31-027")),
        "integrity": integrity,
    }
    return {"comparisons": comparisons,
            "aggregate_legacy_candidate": aggregate,
            **qualification_gate(checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("aa", "official"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=100_000)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--integrity", action="store_true")
    args = parser.parse_args()
    records = json.loads(args.input.read_text())["records"]
    if args.mode == "aa":
        result = aa_decision(records, samples=args.samples, seed=args.seed)
    else:
        result = official_decision(records, samples=args.samples, seed=args.seed,
                                   integrity=args.integrity)
    atomic_write(args.out, canonical_json(json_safe(result)))
    print(json.dumps({"mode": args.mode, "passed": result["passed"],
                      "out": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
