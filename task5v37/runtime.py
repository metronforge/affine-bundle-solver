"""Root-cause-qualified bootstrap policy for v3.7 controls."""

from __future__ import annotations

from task5v36.runtime import RolePolicy, environment_for


def bootstrap_environment(policy: RolePolicy) -> dict[str, str]:
    """Initialize shared OpenBLAS controls at the largest required pool.

    SciPy OpenBLAS 0.3.28 crashes in ``dgelsd`` on V31-026 when initialized
    at one thread and subsequently raised to four through threadpoolctl.  The
    v3.7 process therefore starts both OpenBLAS DSOs at the maximum required
    budget; the existing direct per-DSO policy then leaves the active DSO at
    that budget and lowers the inactive DSO to one.
    """
    values = environment_for(policy)
    values["OPENBLAS_NUM_THREADS"] = str(
        max(policy.system_openblas_threads, policy.scipy_blas_threads)
    )
    return values
