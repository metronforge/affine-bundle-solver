"""NumPy-free ctypes boundary for the supported combined API."""

from __future__ import annotations

import ctypes as ct
import math


class BSCertifiedResult(ct.Structure):
    _fields_ = [
        ("fast_status", ct.c_int), ("fast_certainty", ct.c_int),
        ("rank_estimate", ct.c_int), ("rank_lo", ct.c_int), ("rank_hi", ct.c_int),
        ("eta_x", ct.c_double), ("certified_status", ct.c_int),
        ("eta_status", ct.c_double), ("generator_code", ct.c_int),
        ("verifier_code", ct.c_int), ("accepted_status_mask", ct.c_int),
        ("eta_unique", ct.c_double), ("eta_infinite", ct.c_double),
        ("eta_inconsistent", ct.c_double), ("unique_generator_code", ct.c_int),
        ("unique_verifier_code", ct.c_int), ("infinite_generator_code", ct.c_int),
        ("infinite_verifier_code", ct.c_int),
        ("inconsistent_generator_code", ct.c_int),
        ("inconsistent_verifier_code", ct.c_int),
    ]


class BSCombinedCertifiedResult(ct.Structure):
    _fields_ = [
        ("certified", BSCertifiedResult), ("router_meta", ct.c_double * 11),
        ("grey_distinct_count", ct.c_int), ("grey_total_events", ct.c_int),
        ("grey_rows", ct.c_int * 64), ("last_orth_eta", ct.c_double),
        ("core_rank_interval", ct.c_int * 2), ("core_qr_rank", ct.c_int),
        ("formation_guard_counters", ct.c_ulonglong * 3),
    ]


assert ct.sizeof(BSCertifiedResult) == 112
assert ct.sizeof(BSCombinedCertifiedResult) == 512


class CertifiedLibrary:
    def __init__(self, path):
        self.library = ct.CDLL(str(path))
        pointer = ct.POINTER(ct.c_double)
        self.function = self.library.bsolve_certified_diag_api
        self.function.argtypes = [pointer, pointer, pointer, ct.c_int, ct.c_int,
                                  ct.c_int, ct.c_int, ct.c_int, ct.c_ulonglong,
                                  ct.c_int, ct.POINTER(BSCombinedCertifiedResult)]
        self.function.restype = ct.c_int

    @staticmethod
    def pointer(values):
        if values is None:
            return None
        view = (ct.c_double * len(values)).from_buffer(values)
        return ct.cast(view, ct.POINTER(ct.c_double))

    def call_raw(self, a, b, xt, m, n):
        result = BSCombinedCertifiedResult()
        rc = self.function(self.pointer(a), self.pointer(b), self.pointer(xt),
                           m, n, 2, 2, 2, 17, 0, ct.byref(result))
        return rc, result


def _safe(value):
    value = float(value)
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def result_dict(rc, result):
    certified = {name: (_safe(getattr(result.certified, name))
                        if kind is ct.c_double else int(getattr(result.certified, name)))
                 for name, kind in BSCertifiedResult._fields_}
    names = ("STATUS", "CERTAINTY", "RANK", "RANK_LO", "RANK_HI", "RELRES",
             "RELX", "SECONDS", "FALLBACK", "CLS", "BERR")
    router_meta = {name: _safe(value) for name, value in zip(names, result.router_meta)
                   if name not in ("RELX", "SECONDS")}
    return {
        "api_return": int(rc), "certified": certified, "router_meta": router_meta,
        "grey_distinct_count": int(result.grey_distinct_count),
        "grey_total_events": int(result.grey_total_events),
        "grey_rows": [int(value) for value in
                      result.grey_rows[:result.grey_distinct_count]],
        "last_orth_eta": _safe(result.last_orth_eta),
        "core_rank_interval": [int(value) for value in result.core_rank_interval],
        "core_qr_rank": int(result.core_qr_rank),
        "formation_guard_counters": [int(value) for value in
                                     result.formation_guard_counters],
        "router_executions": 1,
    }

