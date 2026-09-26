"""Deterministic analysis helpers for Task-5 v3.4 evidence."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence


CAMPAIGN_ID = "task5-v3.4-shared-overhead-20260926"
FROZEN_SPEEDUPS = (1.191, 1.013, 2.540)


def parse_trace_line(line: str) -> dict[str, int]:
    """Parse the integer key/value payload emitted by the native tracer."""
    marker = "ABS_V34 "
    if marker not in line:
        raise ValueError("missing ABS_V34 trace marker")
    payload = line.split(marker, 1)[1].strip()
    result: dict[str, int] = {}
    for key, value in re.findall(r"([A-Za-z0-9_]+)=([0-9]+)", payload):
        result[key] = int(value)
    if not result:
        raise ValueError("empty ABS_V34 trace payload")
    return result


def inconsistent_fesetround_bounds(m: int, n: int) -> dict[str, int]:
    """Structural counts for a dense, nonzero inconsistent verification.

    The baseline performs two framed passes over b and every matrix column,
    redundantly setting the already-active direction for every scalar product.
    The optimized bound retains two mode changes per dot product plus five
    norm/product/division/restore changes.
    """
    if m <= 0 or n < 0:
        raise ValueError("unsupported inconsistent-verifier dimensions")
    baseline = 2 * (m + 1) * (n + 1) + 5
    optimized = 2 * n + 7
    return {
        "baseline_exact": baseline,
        "optimized_max": optimized,
        "removed": baseline - optimized,
    }


def triangular_product_terms(n: int) -> dict[str, int]:
    """Count work in the baseline and direct packed-LU entry products."""
    if n <= 0:
        raise ValueError("unique certificate dimension must be positive")
    triangular_terms_one_pass = sum(
        (row + 1) * (row + 2) // 2 + (n - row - 1) * (row + 1)
        for row in range(n)
    )
    baseline_dot_terms = 2 * n**3
    direct_dot_terms = 2 * triangular_terms_one_pass
    return {
        "baseline_dot_terms": baseline_dot_terms,
        "baseline_materialization_writes": n**3 + n**2,
        "direct_dot_terms": direct_dot_terms,
        "removed_dot_terms": baseline_dot_terms - direct_dot_terms,
    }


_CATEGORY = {
    "combined_c_api": "production_api",
    "array_conversion": "required_caller_preparation",
    "meaningful_field_comparison": "correctness_validation",
    "json_serialization": "harness_only",
}


def classify_measurement(name: str) -> str:
    try:
        return _CATEGORY[name]
    except KeyError as exc:
        raise ValueError(f"unregistered measurement category: {name}") from exc


def amdahl_projection(
    baseline_speedups: Sequence[float], removable_fractions: Sequence[float]
) -> dict[str, object]:
    if len(baseline_speedups) != len(removable_fractions) or not baseline_speedups:
        raise ValueError("speedup and fraction vectors must be nonempty and aligned")
    projected = []
    for speedup, fraction in zip(baseline_speedups, removable_fractions, strict=True):
        if speedup <= 0.0 or not 0.0 <= fraction < 1.0:
            raise ValueError("invalid speedup or removable fraction")
        projected.append(speedup / (1.0 - fraction))
    return {
        "projected_speedups": projected,
        "geometric_mean": math.prod(projected) ** (1.0 / len(projected)),
    }


def select_shared_target(
    name: str,
    slot_evidence: Iterable[dict[str, object]],
    baseline_speedups: Sequence[float] = FROZEN_SPEEDUPS,
) -> dict[str, object]:
    evidence = list(slot_evidence)
    fractions = [float(row["production_fraction"]) for row in evidence]
    supported = sum(bool(row.get("supported")) and fraction > 0.0
                    for row, fraction in zip(evidence, fractions, strict=True))
    projection = amdahl_projection(baseline_speedups, fractions)
    if supported < 2:
        reason = "target lacks measured support in at least two bounded-large slots"
    elif float(projection["geometric_mean"]) < 1.5:
        reason = "measured removable production fraction cannot project to 1.5x"
    else:
        reason = "shared-production and Amdahl gates passed"
    return {
        "target": name,
        "accepted": supported >= 2 and float(projection["geometric_mean"]) >= 1.5,
        "supported_slots": supported,
        "reason": reason,
        **projection,
    }
