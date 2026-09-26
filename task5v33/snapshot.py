"""Process-isolated public-API snapshots for baseline/candidate comparison."""

import argparse
import ctypes as ct
import json
import math
import os

import numpy as np

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize
from task5v31.runner import canonical_combined, json_safe
import task5v31.solver as solver


class UniqueWitness(ct.Structure):
    _fields_ = [("m", ct.c_int), ("n", ct.c_int),
                ("idx", ct.POINTER(ct.c_int)), ("scale", ct.POINTER(ct.c_double)),
                ("perm", ct.POINTER(ct.c_int)), ("packed_lu", ct.POINTER(ct.c_double)),
                ("x", ct.POINTER(ct.c_double))]


class InfiniteWitness(ct.Structure):
    _fields_ = [("n", ct.c_int), ("x", ct.POINTER(ct.c_double)),
                ("z", ct.POINTER(ct.c_double))]


class InconsistentWitness(ct.Structure):
    _fields_ = [("m", ct.c_int), ("y", ct.POINTER(ct.c_double)),
                ("pivot_row", ct.c_int)]


def _cases():
    slots = {slot["slot_id"]: slot for slot in generate_manifest()["slots"]}
    cases = []
    for slot_id in ("V31-025", "V31-026", "V31-027"):
        a, b, _ = materialize(slots[slot_id])
        cases.append((slot_id, a, b))
    pivoted = np.array([[0., 0., 4.], [2., 0., 0.], [0., 3., 0.],
                        [2., 3., 4.], [0., 0., 0.], [1., -3., 2.]])
    cases.extend([
        ("compatible-tall-pivoted", pivoted, pivoted @ np.array([2., -1., .5])),
        ("compatible-tall-rank-deficient",
         np.array([[1., 2., 3.], [2., 4., 6.], [0., 1., 1.], [0., 2., 2.],
                   [3., 0., 3.], [0., 0., 0.]]),
         np.array([6., 12., 2., 4., 6., 0.])),
        ("inconsistent-tall",
         np.array([[1., 0.], [2., 0.], [0., 1.], [0., 2.], [0., 0.]]),
         np.array([1., 2., 1., 3., 1.])),
        ("near-rank-boundary",
         np.array([[1., 0.], [0., 1.e-12], [1., 1.e-12], [0., 0.]]),
         np.array([1., 1.e-12, 1.+1.e-12, 0.])),
        ("tiny-1x1", np.array([[2.]]), np.array([4.])),
        ("zero-compatible", np.zeros((4, 2)), np.zeros(4)),
        ("zero-inconsistent", np.zeros((4, 2)), np.array([0., 0., 0., 1.])),
        ("zero-column-compatible", np.empty((3, 0)), np.zeros(3)),
        ("zero-column-inconsistent", np.empty((3, 0)), np.array([0., 1., 0.])),
    ])
    return cases


def _configure(library):
    dp = ct.POINTER(ct.c_double)
    library.bs_generate_unique_witness.argtypes = [dp, dp, ct.c_int, ct.c_int,
                                                    ct.POINTER(UniqueWitness)]
    library.bs_generate_infinite_witness.argtypes = [dp, dp, ct.c_int, ct.c_int,
                                                      ct.POINTER(InfiniteWitness)]
    library.bs_generate_inconsistent_witness.argtypes = [dp, dp, ct.c_int, ct.c_int,
                                                          ct.POINTER(InconsistentWitness)]
    for name in ("bs_generate_unique_witness", "bs_generate_infinite_witness",
                 "bs_generate_inconsistent_witness"):
        getattr(library, name).restype = ct.c_int
    library.bs_unique_witness_free.argtypes = [ct.POINTER(UniqueWitness)]
    library.bs_infinite_witness_free.argtypes = [ct.POINTER(InfiniteWitness)]
    library.bs_inconsistent_witness_free.argtypes = [ct.POINTER(InconsistentWitness)]


def _values(pointer, count):
    return [float(pointer[i]) for i in range(count)] if pointer else None


def _ints(pointer, count):
    return [int(pointer[i]) for i in range(count)] if pointer else None


def snapshot_case(library, a, b):
    a = np.ascontiguousarray(a, dtype=np.float64)
    b = np.ascontiguousarray(b, dtype=np.float64)
    m, n = a.shape
    dp = ct.POINTER(ct.c_double)
    ap, bp = a.ctypes.data_as(dp), b.ctypes.data_as(dp)
    unique, infinite, inconsistent = UniqueWitness(), InfiniteWitness(), InconsistentWitness()
    urc = library.bs_generate_unique_witness(ap, bp, m, n, ct.byref(unique))
    irc = library.bs_generate_infinite_witness(ap, bp, m, n, ct.byref(infinite))
    crc = library.bs_generate_inconsistent_witness(ap, bp, m, n, ct.byref(inconsistent))
    result = {
        "shape": [m, n],
        "unique": {"rc": urc, "m": unique.m, "n": unique.n,
                   "idx": _ints(unique.idx, n), "scale": _values(unique.scale, n),
                   "perm": _ints(unique.perm, n),
                   "packed_lu": _values(unique.packed_lu, n*n), "x": _values(unique.x, n)},
        "infinite": {"rc": irc, "n": infinite.n,
                     "x": _values(infinite.x, n), "z": _values(infinite.z, n)},
        "inconsistent": {"rc": crc, "m": inconsistent.m,
                         "y": _values(inconsistent.y, m),
                         "pivot_row": inconsistent.pivot_row},
    }
    library.bs_unique_witness_free(ct.byref(unique))
    library.bs_infinite_witness_free(ct.byref(infinite))
    library.bs_inconsistent_witness_free(ct.byref(inconsistent))
    if n > 0:
        combined = solver.call_certified(a, b, xt=None)
        result["combined"] = canonical_combined(combined)
    return json_safe(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True)
    args = parser.parse_args()
    os.environ["TASK5_SOLVER_LIB"] = args.lib
    library = ct.CDLL(args.lib)
    _configure(library)
    records = []
    for name, a, b in _cases():
        first = snapshot_case(library, a, b)
        second = snapshot_case(library, a, b)
        if first != second:
            raise RuntimeError(f"nondeterministic repeated snapshot: {name}")
        records.append({"case": name, "snapshot": first})
    print(json.dumps({"library": args.lib, "records": records},
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
