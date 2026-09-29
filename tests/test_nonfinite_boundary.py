"""Fast-math compilation must not erase rejection of NaN and infinity."""
import ctypes
import numpy as np
from compare_builds import DP, load, ptr, run
from library_paths import library_path

lib = load(library_path("affine_bundle_solver").parent)
lib.abs_stream_create.argtypes = [ctypes.c_int]
lib.abs_stream_create.restype = ctypes.c_void_p
lib.abs_stream_insert.argtypes = [ctypes.c_void_p, DP, ctypes.c_double]
lib.abs_stream_insert.restype = ctypes.c_int
lib.abs_stream_destroy.argtypes = [ctypes.c_void_p]
for value in (float("nan"), float("inf"), -float("inf")):
    for where in ("matrix", "rhs"):
        A, b, x = np.eye(2), np.ones(2), np.ones(2)
        if where == "matrix":
            A[1, 1] = value
        else:
            b[1] = value
        out = run(lib, A, b, x, 12345)
        assert int(out[0]) == 4 and int(out[9]) == 4, (value, where, out)
    stream = lib.abs_stream_create(2)
    assert stream
    try:
        assert lib.abs_stream_insert(stream, ptr(np.array([value, 0.])), 1.) == -2
        assert lib.abs_stream_insert(stream, ptr(np.array([1., 0.])), value) == -2
        assert lib.abs_stream_insert(stream, ptr(np.array([1., 0.])), 1.) == 1
    finally:
        lib.abs_stream_destroy(stream)
print("NaN/+Inf/-Inf batch and streaming input rejection: PASS")
