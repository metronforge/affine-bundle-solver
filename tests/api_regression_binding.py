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


class CandidateCheckResult(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_size_t),
        ("policy_used", PolicyValues),
        ("verdict", ctypes.c_int),
        ("max_abs_residual_up", ctypes.c_double),
        ("mixed_backward_error_up", ctypes.c_double),
    ]


class CandidateCertificateResult(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_size_t),
        ("nearby_status_mask", ctypes.c_int),
        ("eta_unique", ctypes.c_double),
        ("eta_infinite", ctypes.c_double),
        ("eta_inconsistent", ctypes.c_double),
        ("unique_generator_code", ctypes.c_int),
        ("unique_verifier_code", ctypes.c_int),
        ("infinite_generator_code", ctypes.c_int),
        ("infinite_verifier_code", ctypes.c_int),
        ("inconsistent_generator_code", ctypes.c_int),
        ("inconsistent_verifier_code", ctypes.c_int),
        ("exact_source_status", ctypes.c_int),
        ("exact_source_verification", ctypes.c_int),
    ]


class LegacyCombinedResult(ctypes.Structure):
    _fields_ = [
        ("certified", CertificateResult),
        ("router_meta", ctypes.c_double * 11),
        ("grey_distinct_count", ctypes.c_int),
        ("grey_total_events", ctypes.c_int),
        ("grey_rows", ctypes.c_int * 64),
        ("last_orth_eta", ctypes.c_double),
        ("core_rank_interval", ctypes.c_int * 2),
        ("core_qr_rank", ctypes.c_int),
        ("formation_guard_counters", ctypes.c_ulonglong * 3),
    ]


DP = ctypes.POINTER(ctypes.c_double)


class SolveOptions(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_size_t),
        ("sketch_width", ctypes.c_int),
        ("verification_passes", ctypes.c_int),
        ("acceptance_scale", ctypes.c_int),
        ("seed", ctypes.c_ulonglong),
    ]


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
    library.bsolve_certified_diag_api.argtypes = [
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
        ctypes.POINTER(LegacyCombinedResult),
    ]
    library.bsolve_certified_diag_api.restype = ctypes.c_int
    library.bs_init_solve_result.argtypes = [ctypes.POINTER(OperationalResult)]
    library.bs_init_solve_result.restype = None
    library.bs_default_solve_options.argtypes = [ctypes.POINTER(SolveOptions)]
    library.bs_default_solve_options.restype = None
    library.bsolve.argtypes = [
        DP, DP, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(PolicyValues), DP, ctypes.POINTER(OperationalResult),
    ]
    library.bsolve.restype = ctypes.c_int
    library.bsolve_ex.argtypes = [
        DP, DP, ctypes.c_int, ctypes.c_int, ctypes.POINTER(SolveOptions),
        ctypes.POINTER(PolicyValues), DP, ctypes.POINTER(OperationalResult),
    ]
    library.bsolve_ex.restype = ctypes.c_int
    library.bs_init_candidate_check_result.argtypes = [ctypes.POINTER(CandidateCheckResult)]
    library.bs_init_candidate_check_result.restype = None
    library.abs_check_candidate.argtypes = [
        DP, DP, DP, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(PolicyValues), ctypes.POINTER(CandidateCheckResult),
    ]
    library.abs_check_candidate.restype = ctypes.c_int
    library.bs_init_certificate_result.argtypes = [ctypes.POINTER(CandidateCertificateResult)]
    library.bs_init_certificate_result.restype = None
    library.bs_certify_candidate.argtypes = [
        DP, DP, DP, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(CandidateCertificateResult),
    ]
    library.bs_certify_candidate.restype = ctypes.c_int
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


def invoke_legacy(library, A: np.ndarray, b: np.ndarray) -> tuple[int, LegacyCombinedResult]:
    matrix = np.ascontiguousarray(A, dtype=np.float64)
    rhs = np.ascontiguousarray(b, dtype=np.float64)
    result = LegacyCombinedResult()
    code = library.bsolve_certified_diag_api(
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
        ctypes.byref(result),
    )
    return code, result


def invoke_solve(library, A: np.ndarray, b: np.ndarray, policy: PolicyValues):
    matrix = np.ascontiguousarray(A, dtype=np.float64)
    rhs = np.ascontiguousarray(b, dtype=np.float64)
    x = np.empty(matrix.shape[1], dtype=np.float64)
    result = OperationalResult()
    library.bs_init_solve_result(ctypes.byref(result))
    code = library.bsolve(
        matrix.ctypes.data_as(DP), rhs.ctypes.data_as(DP),
        matrix.shape[0], matrix.shape[1],
        ctypes.byref(policy), x.ctypes.data_as(DP), ctypes.byref(result),
    )
    return code, x, result


def default_solve_options(library) -> SolveOptions:
    options = SolveOptions()
    library.bs_default_solve_options(ctypes.byref(options))
    return options


def invoke_solve_ex(library, A: np.ndarray, b: np.ndarray, options: SolveOptions,
                    policy: PolicyValues):
    matrix = np.ascontiguousarray(A, dtype=np.float64)
    rhs = np.ascontiguousarray(b, dtype=np.float64)
    x = np.empty(matrix.shape[1], dtype=np.float64)
    result = OperationalResult()
    library.bs_init_solve_result(ctypes.byref(result))
    code = library.bsolve_ex(
        matrix.ctypes.data_as(DP), rhs.ctypes.data_as(DP),
        matrix.shape[0], matrix.shape[1], ctypes.byref(options),
        ctypes.byref(policy), x.ctypes.data_as(DP), ctypes.byref(result),
    )
    return code, x, result


def invoke_candidate_check(library, A: np.ndarray, b: np.ndarray, x: np.ndarray,
                           policy: PolicyValues):
    matrix = np.ascontiguousarray(A, dtype=np.float64)
    rhs = np.ascontiguousarray(b, dtype=np.float64)
    candidate = np.ascontiguousarray(x, dtype=np.float64)
    result = CandidateCheckResult()
    library.bs_init_candidate_check_result(ctypes.byref(result))
    code = library.abs_check_candidate(
        matrix.ctypes.data_as(DP), rhs.ctypes.data_as(DP),
        candidate.ctypes.data_as(DP), matrix.shape[0], matrix.shape[1],
        ctypes.byref(policy), ctypes.byref(result),
    )
    return code, result


def invoke_candidate_certification(library, A: np.ndarray, b: np.ndarray,
                                   x: np.ndarray):
    matrix = np.ascontiguousarray(A, dtype=np.float64)
    rhs = np.ascontiguousarray(b, dtype=np.float64)
    candidate = np.ascontiguousarray(x, dtype=np.float64)
    result = CandidateCertificateResult()
    library.bs_init_certificate_result(ctypes.byref(result))
    code = library.bs_certify_candidate(
        matrix.ctypes.data_as(DP), rhs.ctypes.data_as(DP),
        candidate.ctypes.data_as(DP), matrix.shape[0], matrix.shape[1],
        ctypes.byref(result),
    )
    return code, result
