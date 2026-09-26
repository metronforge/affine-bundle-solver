"""ctypes boundary for the supported one-call certified diagnostic API."""

import ctypes as ct
import math
import os
from pathlib import Path

import numpy as np

ABS_OUT_RELX, ABS_OUT_SECONDS = 6, 7


class BSCertifiedResult(ct.Structure):
    _fields_ = [("fast_status", ct.c_int), ("fast_certainty", ct.c_int), ("rank_estimate", ct.c_int),
               ("rank_lo", ct.c_int), ("rank_hi", ct.c_int), ("eta_x", ct.c_double),
               ("certified_status", ct.c_int), ("eta_status", ct.c_double),
               ("generator_code", ct.c_int), ("verifier_code", ct.c_int), ("accepted_status_mask", ct.c_int),
               ("eta_unique", ct.c_double), ("eta_infinite", ct.c_double), ("eta_inconsistent", ct.c_double),
               ("unique_generator_code", ct.c_int), ("unique_verifier_code", ct.c_int),
               ("infinite_generator_code", ct.c_int), ("infinite_verifier_code", ct.c_int),
               ("inconsistent_generator_code", ct.c_int), ("inconsistent_verifier_code", ct.c_int)]


class BSCombinedCertifiedResult(ct.Structure):
    _fields_ = [("certified", BSCertifiedResult), ("router_meta", ct.c_double * 11),
               ("grey_distinct_count", ct.c_int), ("grey_total_events", ct.c_int),
               ("grey_rows", ct.c_int * 64), ("last_orth_eta", ct.c_double),
               ("core_rank_interval", ct.c_int * 2), ("core_qr_rank", ct.c_int),
               ("formation_guard_counters", ct.c_ulonglong * 3)]


assert ct.sizeof(BSCertifiedResult) == 112
assert ct.sizeof(BSCombinedCertifiedResult) == 512


def _library():
    path = os.environ.get("TASK5_SOLVER_LIB")
    if not path:
        raise RuntimeError("TASK5_SOLVER_LIB must name libcertified_solver.so")
    library = ct.CDLL(str(Path(path)))
    pointer = ct.POINTER(ct.c_double)
    library.bsolve_certified_diag_api.argtypes = [pointer, pointer, pointer, ct.c_int, ct.c_int, ct.c_int,
                                                   ct.c_int, ct.c_int, ct.c_ulonglong, ct.c_int,
                                                   ct.POINTER(BSCombinedCertifiedResult)]
    library.bsolve_certified_diag_api.restype = ct.c_int
    library.bsolve_certified_api.argtypes = [pointer, pointer, pointer, ct.c_int, ct.c_int, ct.c_int,
                                              ct.c_int, ct.c_int, ct.c_ulonglong, ct.c_int,
                                              ct.POINTER(BSCertifiedResult)]
    library.bsolve_certified_api.restype = ct.c_int
    library.bsolve_router_diag_api.argtypes = [pointer, pointer, pointer, ct.c_int, ct.c_int, ct.c_int, ct.c_int,
                                               ct.c_int, ct.c_ulonglong, ct.c_int, pointer, ct.POINTER(ct.c_int), ct.c_int]
    library.bsolve_router_diag_api.restype = ct.c_int
    return library


def _as_dict(result, api_return):
    cert = {name: getattr(result.certified, name) for name, _ in BSCertifiedResult._fields_}
    return {"api_return": int(api_return), "certified": cert,
            "router_meta": [float(x) for x in result.router_meta],
            "grey_distinct_count": int(result.grey_distinct_count), "grey_total_events": int(result.grey_total_events),
            "grey_rows": [int(x) for x in result.grey_rows[:result.grey_distinct_count]],
            "last_orth_eta": float(result.last_orth_eta), "core_rank_interval": [int(x) for x in result.core_rank_interval],
            "core_qr_rank": int(result.core_qr_rank),
            "formation_guard_counters": [int(x) for x in result.formation_guard_counters],
            # The supported combined entry point contains exactly one internal snapshot call.
            "router_executions": 1}


def call_certified(a, b, xt=None, *, sp=2, qv=2, alpha=2, seed=17, full=0):
    a = np.ascontiguousarray(a, dtype=np.float64); b = np.ascontiguousarray(b, dtype=np.float64)
    if a.ndim != 2 or b.shape != (a.shape[0],):
        raise ValueError("A/b dimensions")
    x = None if xt is None else np.ascontiguousarray(xt, dtype=np.float64)
    if x is not None and x.shape != (a.shape[1],):
        raise ValueError("xt dimensions")
    result = BSCombinedCertifiedResult(); pointer = ct.POINTER(ct.c_double)
    rc = _library().bsolve_certified_diag_api(a.ctypes.data_as(pointer), b.ctypes.data_as(pointer),
        None if x is None else x.ctypes.data_as(pointer), a.shape[0], a.shape[1], sp, qv, alpha, seed, full, ct.byref(result))
    return _as_dict(result, rc)


def call_legacy_certified(a, b, xt=None, *, sp=2, qv=2, alpha=2, seed=17, full=0):
    a = np.ascontiguousarray(a, dtype=np.float64); b = np.ascontiguousarray(b, dtype=np.float64)
    x = None if xt is None else np.ascontiguousarray(xt, dtype=np.float64); result = BSCertifiedResult(); pointer = ct.POINTER(ct.c_double)
    rc = _library().bsolve_certified_api(a.ctypes.data_as(pointer), b.ctypes.data_as(pointer),
        None if x is None else x.ctypes.data_as(pointer), a.shape[0], a.shape[1], sp, qv, alpha, seed, full, ct.byref(result))
    if rc not in (0, 2): raise RuntimeError(f"legacy certified API returned {rc}")
    return {name: getattr(result, name) for name, _ in BSCertifiedResult._fields_}


def router_snapshot_equal(combined, a, b, *, sp=2, qv=2, alpha=2, seed=17, full=0):
    a = np.ascontiguousarray(a, dtype=np.float64); b = np.ascontiguousarray(b, dtype=np.float64)
    meta = (ct.c_double * 11)(); grey = (ct.c_int * 64)(); pointer = ct.POINTER(ct.c_double)
    count = _library().bsolve_router_diag_api(a.ctypes.data_as(pointer), b.ctypes.data_as(pointer), None,
        a.shape[0], a.shape[1], sp, qv, alpha, seed, full, meta, grey, 64)
    if count != combined["grey_distinct_count"]: return False
    for index, value in enumerate(meta):
        if index != ABS_OUT_SECONDS and not _same(float(value), combined["router_meta"][index]): return False
    return list(grey[:count]) == combined["grey_rows"]


def _same(x, y):
    if isinstance(x, float) or isinstance(y, float):
        return (math.isnan(x) and math.isnan(y)) or (math.isinf(x) and math.isinf(y) and x == y) or x == y
    return x == y


def meaningful_equal(left, right):
    if left["api_return"] != right["api_return"]:
        return False
    for key in left["certified"]:
        if not _same(left["certified"][key], right["certified"][key]):
            return False
    for index, (a, b) in enumerate(zip(left["router_meta"], right["router_meta"])):
        if index not in (ABS_OUT_RELX, ABS_OUT_SECONDS) and not _same(a, b):
            return False
    return all(left[key] == right[key] for key in ("grey_distinct_count", "grey_total_events", "grey_rows",
                                                     "core_rank_interval", "core_qr_rank", "formation_guard_counters"))


def certified_equal(left, right):
    return all(_same(left[key], right[key]) for key in left)
