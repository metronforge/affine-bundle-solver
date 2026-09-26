#!/usr/bin/env python3
"""A source-policy grey row must not become a point INFINITE verdict."""

import numpy as np

from router_test_support import INFINITE, NAME, UNDECIDABLE, classify


# The fourth row has normalized unexplained norm 3.54e-13, strictly inside
# the published [1e-13, 1e-9] source-policy grey band.  Rank four is therefore
# not excluded and a point INFINITE result would overclaim.
base = np.array(
    [
        [-1.0, 1.0, 0.0, 0.0],
        [0.0, -1.0, 1.0, 0.0],
        [0.0, 0.0, -1.0, 1.0],
    ]
)
x = np.array([0.0, 0.2, -0.1, 0.4])

# Just below the dependency boundary the source policy resolves the row as
# dependent.  Keep this adjacent control so the grey-zone repair does not
# simply demote every near-boundary INFINITE result.
resolved = np.vstack([base, base[0] + 1e-13 * np.eye(4)[0]])
resolved_result = classify(resolved, resolved @ x, x, 20260920)
assert resolved_result["status"] == INFINITE, (
    "a row below the dependency boundary should remain INFINITE, got "
    f"{NAME[resolved_result['status']]}"
)

a = np.vstack([base, base[0] + 1e-12 * np.eye(4)[0]])
result = classify(a, a @ x, x, 20260920)

assert result["status"] == UNDECIDABLE, (
    "a source row in the declared grey band must remain UNDECIDABLE, got "
    f"{NAME[result['status']]}"
)
assert (result["rank_lo"], result["rank_hi"]) == (3, 4), result
# Sequential screening must retain the boundary row.  Source QRCP may also
# report another source row representing the same pivot-order grey direction.
assert 3 in result["grey_rows"], result

print("PASS: graph-03 remains UNDECIDABLE at rank interval [3,4]")
