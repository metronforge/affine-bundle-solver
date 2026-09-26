#!/usr/bin/env python3
"""Row order must not create a contradiction in an exactly compatible system."""

import numpy as np

from router_test_support import INFINITE, NAME, UNDECIDABLE, classify


# N049's frozen construction has an identically zero final column and an RHS
# formed by the same binary64 matrix product.  The stored system is therefore
# exactly compatible.  Reordering its equations cannot create a contradiction.
n = 128
points = np.linspace(-1.0, 1.0, n)
angles = np.arccos(np.clip(points, -1.0, 1.0))
a = np.cos(angles[:, None] * np.arange(n)[None, :])
a[:, -1] = 0.0
x = np.sin((np.arange(n) + 1) * 0.37 + 100171e-6)
b = a @ x
assert np.max(np.abs(a @ x - b)) == 0.0
assert np.all(a[:, -1] == 0.0)

orders = {
    "original": np.arange(n),
    "reverse": np.arange(n)[::-1],
    **{f"permutation-{seed}": np.random.default_rng(seed).permutation(n) for seed in range(8)},
}
for label, order in orders.items():
    result = classify(a[order], b[order], x, 100171)
    assert result["status"] in (INFINITE, UNDECIDABLE), (
        f"exactly compatible N049 became {NAME[result['status']]} under {label}: "
        f"{result}"
    )

print("PASS: exactly compatible N049 is never a contradiction under row reorderings")
