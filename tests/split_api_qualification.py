"""Qualification of split APIs against the unchanged frozen 36-case corpus."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from api_regression_binding import (
    default_policy,
    default_solve_options,
    invoke,
    invoke_candidate_certification,
    invoke_candidate_check,
    invoke_solve,
    invoke_solve_ex,
    load_library,
)
from api_regression_corpus import discover_cases, load_manifest
from api_regression_oracle import load_oracles


def oracle_quality(A: np.ndarray, b: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    wide = np.longdouble
    Aw = A.astype(wide)
    bw = b.astype(wide)
    xw = x.astype(wide)
    residual = np.abs(Aw @ xw - bw)
    maximum = float(np.max(residual, initial=wide(0)))
    xnorm = np.sqrt(np.sum(xw * xw, dtype=wide))
    rownorm = np.sqrt(np.sum(Aw * Aw, axis=1, dtype=wide))
    denominator = np.abs(bw) + rownorm * xnorm
    ratios = np.empty_like(residual)
    nonzero = denominator != 0
    ratios[nonzero] = residual[nonzero] / denominator[nonzero]
    ratios[~nonzero] = np.where(residual[~nonzero] == 0, wide(0), wide(np.inf))
    return maximum, float(np.max(ratios, initial=wide(0)))


def close_bound(left: float, right: float) -> bool:
    if math.isinf(left) or math.isinf(right):
        return math.isinf(left) and math.isinf(right)
    return math.isclose(left, right, rel_tol=2e-11, abs_tol=2e-15)


def qualify(fixture_root: Path) -> dict[str, int]:
    cases = discover_cases(fixture_root, load_manifest(fixture_root))
    oracles = load_oracles(fixture_root / "oracles.json")
    library = load_library()
    policy = default_policy(library)
    counts = {
        "solve": 0,
        "solve_default_equivalence": 0,
        "solve_candidate_check": 0,
        "certification": 0,
        "combined_vs_composed": 0,
        "caller_supplied_candidates": 0,
        "independent_quality_oracles": 0,
        "independent_solution_oracles": 0,
    }
    for case in cases:
        code, x, operational = invoke_solve(library, case.A, case.b, policy)
        if code != 0 or not np.isfinite(x).all():
            raise AssertionError(f"{case.case_id}: solve code={code}, finite={np.isfinite(x).all()}")
        counts["solve"] += 1

        ex_code, ex_x, ex_operational = invoke_solve_ex(
            library, case.A, case.b, default_solve_options(library), policy
        )
        if ex_code != code or not np.allclose(ex_x, x, rtol=2e-13, atol=2e-15,
                                              equal_nan=True):
            raise AssertionError(f"{case.case_id}: default solve entry points differ")
        if operational.struct_size != ex_operational.struct_size:
            raise AssertionError(f"{case.case_id}: default result size differs")
        if operational.policy_used.struct_size != ex_operational.policy_used.struct_size:
            raise AssertionError(f"{case.case_id}: default policy size differs")
        comparable = (
            "operational_status", "operational_certainty", "exact_source_status",
            "exact_source_verification", "grey_distinct_count", "grey_total_events",
            "last_orth_eta", "core_qr_rank",
        )
        for field in comparable:
            left, right = getattr(operational, field), getattr(ex_operational, field)
            if left != right and not (isinstance(left, float) and math.isnan(left)
                                      and math.isnan(right)):
                raise AssertionError(f"{case.case_id}: default {field} differs")
        if list(operational.core_rank_interval) != list(ex_operational.core_rank_interval):
            raise AssertionError(f"{case.case_id}: default rank interval differs")
        if list(operational.grey_rows) != list(ex_operational.grey_rows):
            raise AssertionError(f"{case.case_id}: default grey rows differ")
        if list(operational.formation_guard_counters) != list(
                ex_operational.formation_guard_counters):
            raise AssertionError(f"{case.case_id}: default guard counters differ")
        if operational.policy_used.values() != ex_operational.policy_used.values():
            raise AssertionError(f"{case.case_id}: default policy evidence differs")
        for index in range(11):
            if index == 7:
                continue
            left, right = operational.router_meta[index], ex_operational.router_meta[index]
            if left != right and not (math.isnan(left) and math.isnan(right)):
                raise AssertionError(f"{case.case_id}: default router meta[{index}] differs")
        counts["solve_default_equivalence"] += 1

        oracle_x, *_ = np.linalg.lstsq(case.A, case.b, rcond=1e-12)
        residual = np.linalg.norm(case.A @ x - case.b)
        oracle_residual = np.linalg.norm(case.A @ oracle_x - case.b)
        scale = max(1.0, np.linalg.norm(case.b), oracle_residual)
        if residual > oracle_residual + 5e-9 * scale:
            raise AssertionError(
                f"{case.case_id}: solve residual {residual} exceeds oracle {oracle_residual}"
            )
        exact = oracles[case.case_id]
        condition = np.linalg.cond(case.A)
        solution_rtol = max(2e-8, 4.0 * np.finfo(np.float64).eps * condition)
        solution_error = np.linalg.norm(x - oracle_x)
        solution_scale = max(1.0, np.linalg.norm(oracle_x))
        if (exact.exact_status == "UNIQUE" and operational.operational_status == 1
                and solution_error > solution_rtol * solution_scale + 2e-10):
            raise AssertionError(f"{case.case_id}: unique solution disagrees with oracle")
        if exact.exact_status == "INFINITE" and np.linalg.norm(x) > np.linalg.norm(oracle_x) + 5e-8 * max(1.0, np.linalg.norm(oracle_x)):
            raise AssertionError(f"{case.case_id}: non-unique candidate is not minimum norm")
        counts["independent_solution_oracles"] += 1

        check_code, checked = invoke_candidate_check(library, case.A, case.b, x, policy)
        if check_code != 0:
            raise AssertionError(f"{case.case_id}: candidate check code={check_code}")
        residual_oracle, backward_oracle = oracle_quality(case.A, case.b, x)
        if checked.max_abs_residual_up + 1e-300 < residual_oracle or checked.mixed_backward_error_up + 1e-300 < backward_oracle:
            raise AssertionError(f"{case.case_id}: candidate bounds do not enclose oracle")
        if checked.verdict == 1 and backward_oracle > policy.quality_threshold:
            raise AssertionError(f"{case.case_id}: quality success contradicts oracle")
        if checked.verdict == 2 and not checked.mixed_backward_error_up > policy.quality_threshold:
            raise AssertionError(f"{case.case_id}: NOT_ESTABLISHED lacks threshold evidence")
        counts["solve_candidate_check"] += 1
        counts["independent_quality_oracles"] += 1

        cert_code, certificate = invoke_candidate_certification(library, case.A, case.b, x)
        if cert_code != 0:
            raise AssertionError(f"{case.case_id}: certification code={cert_code}")
        counts["certification"] += 1

        legacy_code, legacy = invoke(library, case.A, case.b, policy)
        if legacy_code not in (0, 2):
            raise AssertionError(f"{case.case_id}: legacy combined code={legacy_code}")
        if operational.operational_status != legacy.operational.operational_status or operational.operational_certainty != legacy.operational.operational_certainty:
            raise AssertionError(f"{case.case_id}: operational semantics changed")
        profile = legacy.certificate_profile
        exact_fields = (
            "nearby_status_mask", "unique_generator_code", "unique_verifier_code",
            "infinite_generator_code", "infinite_verifier_code",
            "inconsistent_generator_code", "inconsistent_verifier_code",
        )
        for field in exact_fields:
            legacy_value = profile.accepted_status_mask if field == "nearby_status_mask" else getattr(profile, field)
            if getattr(certificate, field) != legacy_value:
                raise AssertionError(f"{case.case_id}: certificate {field} changed")
        for field in ("eta_unique", "eta_infinite", "eta_inconsistent"):
            if not close_bound(getattr(certificate, field), getattr(profile, field)):
                raise AssertionError(f"{case.case_id}: certificate {field} changed")
        counts["combined_vs_composed"] += 1

        direction = np.arange(1, x.size + 1, dtype=np.float64)
        direction /= np.linalg.norm(direction)
        candidates = (
            x + direction * 1e-13 * max(1.0, np.linalg.norm(x)),
            x + direction * 1e-4 * max(1.0, np.linalg.norm(x)),
            np.zeros_like(x),
            np.full_like(x, 17.0),
        )
        for candidate in candidates:
            candidate_code, candidate_result = invoke_candidate_check(
                library, case.A, case.b, candidate, policy
            )
            if candidate_code != 0:
                raise AssertionError(f"{case.case_id}: arbitrary candidate code={candidate_code}")
            residual_oracle, backward_oracle = oracle_quality(case.A, case.b, candidate)
            if candidate_result.max_abs_residual_up + 1e-300 < residual_oracle or candidate_result.mixed_backward_error_up + 1e-300 < backward_oracle:
                raise AssertionError(f"{case.case_id}: arbitrary candidate bound underestimates")
            counts["caller_supplied_candidates"] += 1
            counts["independent_quality_oracles"] += 1

    if len(cases) != 36:
        raise AssertionError(f"expected 36 frozen cases, got {len(cases)}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, default=Path(__file__).parent / "fixtures/api-regression")
    parser.add_argument("--expect-count", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    counts = qualify(args.fixture_root)
    if counts["solve"] != args.expect_count:
        parser.error(f"expected {args.expect_count} solve cases, got {counts['solve']}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n")
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
