"""Small ctypes adapter shared by router integration regressions."""

import ctypes
import os
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))

DP = ctypes.POINTER(ctypes.c_double)
IP = ctypes.POINTER(ctypes.c_int)
lib.bsolve_router_diag_api.argtypes = (
    [DP, DP, DP]
    + [ctypes.c_int] * 5
    + [ctypes.c_ulonglong, ctypes.c_int, DP, IP, ctypes.c_int]
)
lib.bsolve_router_diag_api.restype = ctypes.c_int

UNIQUE, INFINITE, INCONSISTENT, FAIL, UNDECIDABLE = 1, 2, 3, 4, 5
NAME = {
    UNIQUE: "UNIQUE",
    INFINITE: "INFINITE",
    INCONSISTENT: "INCONSISTENT",
    FAIL: "FAIL",
    UNDECIDABLE: "UNDECIDABLE",
}


def _array(value):
    return np.ascontiguousarray(value, dtype=np.float64)


def _pointer(value):
    return value.ctypes.data_as(DP)


def classify(a, b, x, seed):
    a, b, x = _array(a), _array(b), _array(x)
    output = np.zeros(11, dtype=np.float64)
    grey = np.full(a.shape[0], -1, dtype=np.int32)
    grey_count = lib.bsolve_router_diag_api(
        _pointer(a),
        _pointer(b),
        _pointer(x),
        a.shape[0],
        a.shape[1],
        1,
        2,
        2,
        seed,
        0,
        _pointer(output),
        grey.ctypes.data_as(IP),
        len(grey),
    )
    return {
        "status": int(output[0]),
        "rank_lo": int(output[3]),
        "rank_hi": int(output[4]),
        "grey_rows": [int(row) for row in grey[:grey_count]],
    }
