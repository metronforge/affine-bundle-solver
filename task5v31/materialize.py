"""Analytic diagonal-profile materialization for frozen V3.1 inputs."""

import hashlib
import numpy as np


def materialize(slot):
    m, n = slot["m"], slot["n"]
    rank = slot["structural_rank_profile"]["algebraic_rank"]
    params = slot["generator_parameters"]
    profile, scale, k = params["profile"], float(params["scale"]), min(m, n)
    if profile == "scaled_pair":
        singular = np.array([1.0, 1e-10])
    elif profile == "zero":
        singular = np.zeros(k)
    else:
        singular = np.linspace(1.0, 0.6, k)
        if profile == "exact_deficient":
            singular[-1] = 0.0
        elif profile in ("near_low", "near_high"):
            singular[-1] = params["near_singular"]
        singular *= np.random.default_rng(slot["seed"]).choice([-1.0, 1.0], size=k)
    a = np.zeros((m, n), dtype=np.float64)
    a[np.arange(k), np.arange(k)] = scale * singular
    # For this diagonal design A @ ones(n) is exactly the rowwise diagonal;
    # form it directly so materialization does no general matrix product.
    b = np.zeros(m, dtype=np.float64)
    b[:k] = scale * singular
    if slot["rhs_policy"] == "incompatible":
        b[rank] += 1.0
    metadata = {"algebraic_rank": rank,
                "matrix_sha256": hashlib.sha256(a.tobytes(order="C")).hexdigest(),
                "rhs_sha256": hashlib.sha256(b.tobytes(order="C")).hexdigest(),
                "construction": "seeded-sign-diagonal-profile"}
    return a, b, metadata
