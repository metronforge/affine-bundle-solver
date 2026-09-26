import math

import pytest

from task5v34.diagnostics import (
    amdahl_projection,
    classify_measurement,
    inconsistent_fesetround_bounds,
    parse_trace_line,
    select_shared_target,
    triangular_product_terms,
)


def test_trace_parser_retains_counts_times_and_allocation_bytes():
    trace = parse_trace_line(
        "ABS_V34 api_ns=100 api_count=1 inconsistent_verify_ns=40 "
        "inconsistent_verify_count=1 fesetround_count=66311 malloc_bytes=4096 "
        "memcpy_bytes=1024"
    )
    assert trace == {
        "api_ns": 100,
        "api_count": 1,
        "inconsistent_verify_ns": 40,
        "inconsistent_verify_count": 1,
        "fesetround_count": 66311,
        "malloc_bytes": 4096,
        "memcpy_bytes": 1024,
    }


@pytest.mark.parametrize(
    ("m", "n", "before", "after_max"),
    [(128, 256, 66311, 519), (192, 192, 74503, 391), (256, 128, 66311, 263)],
)
def test_inconsistent_verifier_rounding_count_bound(m, n, before, after_max):
    bounds = inconsistent_fesetround_bounds(m, n)
    assert bounds["baseline_exact"] == before
    assert bounds["optimized_max"] == after_max
    assert bounds["removed"] >= before - after_max


def test_measurement_categories_exclude_validation_and_harness_from_claim():
    assert classify_measurement("combined_c_api") == "production_api"
    assert classify_measurement("array_conversion") == "required_caller_preparation"
    assert classify_measurement("meaningful_field_comparison") == "correctness_validation"
    assert classify_measurement("json_serialization") == "harness_only"


def test_amdahl_projection_uses_only_measured_production_fraction():
    projected = amdahl_projection(
        [1.191, 1.013, 2.540],
        [0.10, 0.08, 0.06],
    )
    expected = math.prod(
        [1.191 / 0.90, 1.013 / 0.92, 2.540 / 0.94]
    ) ** (1.0 / 3.0)
    assert projected["projected_speedups"] == pytest.approx(
        [1.191 / 0.90, 1.013 / 0.92, 2.540 / 0.94]
    )
    assert projected["geometric_mean"] == pytest.approx(expected)


def test_target_requires_two_slots_and_projected_geomean_at_least_1_5():
    accepted = select_shared_target(
        "same_mode_fesetround",
        [
            {"slot_id": "V31-025", "production_fraction": 0.10, "supported": True},
            {"slot_id": "V31-026", "production_fraction": 0.08, "supported": True},
            {"slot_id": "V31-027", "production_fraction": 0.06, "supported": True},
        ],
        [1.191, 1.013, 2.540],
    )
    assert accepted["accepted"] is True
    assert accepted["supported_slots"] == 3
    rejected = select_shared_target(
        "one_slot_only",
        [
            {"slot_id": "V31-025", "production_fraction": 0.30, "supported": True},
            {"slot_id": "V31-026", "production_fraction": 0.0, "supported": False},
            {"slot_id": "V31-027", "production_fraction": 0.0, "supported": False},
        ],
        [1.191, 1.013, 2.540],
    )
    assert rejected["accepted"] is False
    assert "at least two" in rejected["reason"]


def test_triangular_term_count_proves_structural_zero_reduction():
    counts = triangular_product_terms(192)
    assert counts["baseline_dot_terms"] == 2 * 192**3
    assert counts["baseline_materialization_writes"] == 192**3 + 192**2
    assert counts["direct_dot_terms"] < counts["baseline_dot_terms"] / 3 + 2 * 192**2
    assert counts["removed_dot_terms"] > 0
