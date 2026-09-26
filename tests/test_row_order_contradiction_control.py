#!/usr/bin/env python3
"""The compatibility repair must not hide a genuine source contradiction."""

import numpy as np

from router_test_support import INCONSISTENT, NAME, classify


n = 4
a = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]
)
x = np.array([0.25, -0.5, 0.75, 1.0])
b = a @ x

# Append an exact duplicate of the first equation with a conflicting RHS.
# Check both ends of the stream: the new compatibility guard must preserve a
# real contradiction rather than conservatively demoting all bad residuals.
conflict_row = a[0:1].copy()
conflict_rhs = np.array([b[0] + 1.0])
cases = {
    "duplicate-last": (np.vstack([a, conflict_row]), np.concatenate([b, conflict_rhs])),
    "duplicate-first": (np.vstack([conflict_row, a]), np.concatenate([conflict_rhs, b])),
}
for label, (case_a, case_b) in cases.items():
    result = classify(case_a, case_b, x, 20260920)
    assert result["status"] == INCONSISTENT, (
        f"genuine contradiction became {NAME[result['status']]} under {label}: "
        f"{result}"
    )

print("PASS: a genuine duplicate-row contradiction remains detectable")
