"""ctypes mirror of the current combined public API."""

from __future__ import annotations

import ctypes
from pathlib import Path

import numpy as np

from library_paths import library_path


class PolicyValues(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_size_t),
        ("dependence_threshold", ctypes.c_double),
        ("growth_threshold", ctypes.c_double),
        ("compatibility_tolerance", ctypes.c_double),
        ("quality_threshold", ctypes.c_double),
    ]

    def values(self):
        return (
            self.dependence_threshold,
            self.growth_threshold,
            self.compatibility_tolerance,
            self.quality_threshold,
        )


class OperationalResult(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_size_t),
        ("policy_used", PolicyValues),
        ("operational_status", ctypes.c_int),
        ("operational_certainty", ctypes.c_int),
        ("exact_source_status", ctypes.c_int),
        ("exact_source_verification", ctypes.c_int),
        ("router_meta", ctypes.c_double * 11),
        ("grey_distinct_count", ctypes.c_int),
        ("grey_total_events", ctypes.c_int),
        ("grey_rows", ctypes.c_int * 64),
        ("last_orth_eta", ctypes.c_double),
        ("core_rank_interval", ctypes.c_int * 2),
        ("core_qr_rank", ctypes.c_int),
        ("formation_guard_counters", ctypes.c_ulonglong * 3),
    ]


class CertificateResult(ctypes.Structure):
    _fields_ = [
        ("fast_status", ctypes.c_int),
        ("fast_certainty", ctypes.c_int),
        ("rank_estimate", ctypes.c_int),
        ("rank_lo", ctypes.c_int),
        ("rank_hi", ctypes.c_int),
        ("eta_x", ctypes.c_double),
        ("certified_status", ctypes.c_int),
        ("eta_status", ctypes.c_double),
        ("generator_code", ctypes.c_int),
        ("verifier_code", ctypes.c_int),
        ("accepted_status_mask", ctypes.c_int),
        ("eta_unique", ctypes.c_double),
        ("eta_infinite", ctypes.c_double),
        ("eta_inconsistent", ctypes.c_double),
        ("unique_generator_code", ctypes.c_int),
        ("unique_verifier_code", ctypes.c_int),
        ("infinite_generator_code", ctypes.c_int),
        ("infinite_verifier_code", ctypes.c_int),
        ("inconsistent_generator_code", ctypes.c_int),
        ("inconsistent_verifier_code", ctypes.c_int),
    ]


class CombinedResult(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_size_t),
        ("operational", OperationalResult),
        ("nearby_status_mask", ctypes.c_int),
        ("eta_unique", ctypes.c_double),
        ("eta_infinite", ctypes.c_double),
        ("eta_inconsistent", ctypes.c_double),
        ("certificate_profile", CertificateResult),
    ]


DP = ctypes.POINTER(ctypes.c_double)


def load_library(directory: Path | None = None):
    library = ctypes.CDLL(str(library_path("certified_solver", directory)))
    library.bs_default_operational_policy.argtypes = [ctypes.POINTER(PolicyValues)]
    library.bs_default_operational_policy.restype = None
    library.bs_init_combined_semantic_result.argtypes = [ctypes.POINTER(CombinedResult)]
    library.bs_init_combined_semantic_result.restype = None
    library.bsolve_certified_policy_api.argtypes = [
        DP,
        DP,
        DP,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_ulonglong,
        ctypes.c_int,
        ctypes.POINTER(PolicyValues),
        ctypes.POINTER(CombinedResult),
    ]
    library.bsolve_certified_policy_api.restype = ctypes.c_int
    return library


def default_policy(library) -> PolicyValues:
    policy = PolicyValues()
    library.bs_default_operational_policy(ctypes.byref(policy))
    return policy


def invoke(library, A: np.ndarray, b: np.ndarray, policy: PolicyValues) -> tuple[int, CombinedResult]:
    matrix = np.ascontiguousarray(A, dtype=np.float64)
    rhs = np.ascontiguousarray(b, dtype=np.float64)
    result = CombinedResult()
    library.bs_init_combined_semantic_result(ctypes.byref(result))
    code = library.bsolve_certified_policy_api(
        matrix.ctypes.data_as(DP),
        rhs.ctypes.data_as(DP),
        None,
        matrix.shape[0],
        matrix.shape[1],
        1,
        2,
        2,
        17,
        0,
        ctypes.byref(policy),
        ctypes.byref(result),
    )
    return code, result
