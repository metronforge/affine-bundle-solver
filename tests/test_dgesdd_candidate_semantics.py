"""Focused public-API controls for the compact DGESDD candidate.

The matrices cover wide/square/tall cores, zero and rank-deficient spectra,
the published rank ambiguity band, and repeated deterministic execution.
"""
import ctypes
import math
import os
from pathlib import Path

import numpy as np

LIB = ctypes.CDLL(str(Path(os.environ["ABS_LIB_DIR"]) / "libcertified_solver.so"))
DP = ctypes.POINTER(ctypes.c_double)


class Result(ctypes.Structure):
    _fields_ = [("fast_status", ctypes.c_int), ("fast_certainty", ctypes.c_int),
                ("rank_estimate", ctypes.c_int), ("rank_lo", ctypes.c_int),
                ("rank_hi", ctypes.c_int), ("eta_x", ctypes.c_double),
                ("certified_status", ctypes.c_int), ("eta_status", ctypes.c_double),
                ("generator_code", ctypes.c_int), ("verifier_code", ctypes.c_int),
                ("accepted_status_mask", ctypes.c_int), ("eta_unique", ctypes.c_double),
                ("eta_infinite", ctypes.c_double), ("eta_inconsistent", ctypes.c_double),
                ("unique_generator_code", ctypes.c_int), ("unique_verifier_code", ctypes.c_int),
                ("infinite_generator_code", ctypes.c_int), ("infinite_verifier_code", ctypes.c_int),
                ("inconsistent_generator_code", ctypes.c_int), ("inconsistent_verifier_code", ctypes.c_int)]


LIB.bsolve_certified_api.argtypes = [DP, DP, DP, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_ulonglong, ctypes.c_int,
                                     ctypes.POINTER(Result)]
LIB.bsolve_certified_api.restype = ctypes.c_int


def dp(x):
    return np.ascontiguousarray(x, dtype=np.float64).ctypes.data_as(DP)


def call(a, b, x):
    a = np.ascontiguousarray(a, dtype=np.float64)
    b = np.ascontiguousarray(b, dtype=np.float64)
    x = np.ascontiguousarray(x, dtype=np.float64)
    out = Result()
    assert LIB.bsolve_certified_api(dp(a), dp(b), dp(x), *a.shape, 1, 2, 2,
                                    20260925, 0, ctypes.byref(out)) == 0
    fields = tuple(getattr(out, name) for name, _ in Result._fields_)
    assert 0 <= out.rank_lo <= out.rank_hi <= min(a.shape)
    assert out.fast_status in (1, 2, 3, 5)
    # Any accepted proof must have a finite strict-verifier eta.
    for bit, eta in ((1, out.eta_unique), (2, out.eta_infinite),
                     (4, out.eta_inconsistent)):
        if out.accepted_status_mask & bit:
            assert math.isfinite(eta) and eta >= 0.0
    return fields


def same_exported(a, b):
    """NaN is the documented eta_x sentinel outside deterministic UNIQUE."""
    return all(x == y or (isinstance(x, float) and math.isnan(x) and
                          isinstance(y, float) and math.isnan(y))
               for x, y in zip(a, b))


rng = np.random.default_rng(20260925)
cases = []

# wide full-row-rank, square full-rank, and tall full-column-rank cores
for name, shape in (("wide", (32, 64)), ("square", (48, 48)), ("tall", (96, 32))):
    a = rng.standard_normal(shape); x = rng.standard_normal(shape[1])
    cases.append((name, a, a @ x, x, 1 if shape[0] >= shape[1] else 2))

# rank zero and rank deficient compatible systems; the latter reconstructs
# the minimum-norm solution's residual identity A*x == b.
a = np.zeros((48, 64)); x = np.zeros(64); cases.append(("zero", a, a @ x, x, 2))
u = rng.standard_normal((96, 12)); v = rng.standard_normal((12, 32)); a = u @ v
x = rng.standard_normal(32); cases.append(("rank-deficient", a, a @ x, x, 2))

# Inconsistency must remain classifiable; a gapped spectrum covers a decisive
# direction and the near-threshold policy band without changing policy.
a = rng.standard_normal((96, 32)); x = rng.standard_normal(32); b = a @ x; b[3] += 1.0
cases.append(("inconsistent", a, b, x, 3))
q1, _ = np.linalg.qr(rng.standard_normal((96, 32))); q2, _ = np.linalg.qr(rng.standard_normal((32, 32)))
for name, gap, expected in (("gapped-full", 1e-6, 1), ("near-threshold", 1e-11, 5)):
    a = q1 @ np.diag(np.r_[np.ones(31), gap]) @ q2.T; x = np.ones(32)
    cases.append((name, a, a @ x, x, expected))

for name, a, b, x, expected in cases:
    first = call(a, b, x)
    second = call(a, b, x)
    assert same_exported(first, second), f"{name}: nondeterministic exported result"
    assert first[0] == expected, f"{name}: status {first[0]} != {expected}"
    print(name, "status", first[0], "rank", first[2], "mask", first[10])

print("PASS: compact DGESDD focused public semantics")
