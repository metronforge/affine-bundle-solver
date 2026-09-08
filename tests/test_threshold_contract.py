#!/usr/bin/env python3
"""
test_threshold_contract.py -- the decision thresholds behave as documented.

ABS_DEPENDENCE_THRESHOLD and ABS_GROWTH_THRESHOLD are part of the public
contract, which means three things have to actually hold rather than merely
be written down:

  1. The library was built with the values the header states.
  2. A direction whose distance is clearly below the dependence threshold is
     absorbed; clearly above the growth threshold, it grows the rank; between
     them, neither is established and the row is deferred.
  3. The thresholds are scale-free.  Multiplying a row by a large or small
     constant must not move it across them, because the distances are
     measured on normalised rows.

Point 3 is the one worth testing rather than assuming: it is the difference
between a threshold that means something about the data and one that means
something about the units the data happened to arrive in.
"""
import ctypes
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
lib = ctypes.CDLL(str(LIBDIR / "libaffine_bundle_solver.so"))

DP = ctypes.POINTER(ctypes.c_double)

# Values as documented in include/affine_bundle/router.h.
HEADER_DEP = 1e-13
HEADER_GROW = 1e-9

lib.abs_thresholds.argtypes = [DP, DP]
lib.abs_stream_create.argtypes = [ctypes.c_int]
lib.abs_stream_create.restype = ctypes.c_void_p
lib.abs_stream_destroy.argtypes = [ctypes.c_void_p]
lib.abs_stream_insert.argtypes = [ctypes.c_void_p, DP, ctypes.c_double]
lib.abs_stream_insert.restype = ctypes.c_int

ABSORB, GROW, DEFER, CONTRA = 0, 1, 2, -1
NAME = {0: "ABSORB", 1: "GROW", 2: "DEFER", -1: "CONTRA", -2: "EINVAL"}


def ptr(a):
    return np.ascontiguousarray(a, dtype=np.float64).ctypes.data_as(DP)


def library_thresholds():
    dep = ctypes.c_double(0.0)
    grow = ctypes.c_double(0.0)
    lib.abs_thresholds(ctypes.byref(dep), ctypes.byref(grow))
    return dep.value, grow.value


def insert_probe(eps, scale=1.0, n=6, base_rows=3, seed=4242):
    """Build a span from base_rows rows, then offer a row that lies in that
    span plus a component of size eps pointing out of it.  Everything is
    multiplied by scale, which must not matter."""
    rng = np.random.default_rng(seed)
    rows = rng.standard_normal((base_rows, n))
    out_dir = rng.standard_normal(n)

    st = lib.abs_stream_create(n)
    assert st, "abs_stream_create returned NULL"
    for i in range(base_rows):
        r = np.ascontiguousarray(rows[i] * scale)
        lib.abs_stream_insert(st, ptr(r), float(np.dot(rows[i], np.ones(n)) * scale))

    probe = np.ascontiguousarray((rows[0] + eps * out_dir) * scale)
    rhs = float(np.dot(rows[0] + eps * out_dir, np.ones(n)) * scale)
    rc = lib.abs_stream_insert(st, ptr(probe), rhs)
    lib.abs_stream_destroy(st)
    return rc


def main():
    failures = []

    dep, grow = library_thresholds()
    print(f"  header : dependence {HEADER_DEP:.0e}, growth {HEADER_GROW:.0e}")
    print(f"  library: dependence {dep:.0e}, growth {grow:.0e}")
    if dep != HEADER_DEP or grow != HEADER_GROW:
        failures.append("header and library disagree on the thresholds")
    if not dep < grow:
        failures.append(f"dependence threshold {dep:.0e} is not below growth {grow:.0e}")

    print()
    print("  Row = in-span row + eps * out-of-span direction")
    print(f"  {'eps':>8s} {'verdict':>10s}   expected")
    print("  " + "-" * 40)

    # Two decades of margin on each side of the band; the band itself is four
    # decades wide, so this leaves the boundaries themselves untested on
    # purpose.  A threshold is a contract about what is clearly inside and
    # clearly outside, not about its own last bit.
    plan = [(1e-15, ABSORB), (1e-14, ABSORB),
            (1e-12, DEFER), (1e-11, DEFER), (1e-10, DEFER),
            (1e-7, GROW), (1e-6, GROW)]
    for eps, expected in plan:
        rc = insert_probe(eps)
        ok = (rc == expected)
        if not ok:
            failures.append(f"eps={eps:.0e}: got {NAME.get(rc)}, expected {NAME.get(expected)}")
        print(f"  {eps:>8.0e} {NAME.get(rc, '?'):>10s}   {NAME.get(expected)}"
              f"{'' if ok else '   <-- MISMATCH'}")

    print()
    print("  Same systems, rescaled.  Scale must not change the verdict.")
    print(f"  {'eps':>8s} " + " ".join(f"{s:>10.0e}" for s in (1e-8, 1.0, 1e8)))
    print("  " + "-" * 44)
    for eps, _ in plan:
        verdicts = [insert_probe(eps, scale=s) for s in (1e-8, 1.0, 1e8)]
        if len(set(verdicts)) != 1:
            failures.append(
                f"eps={eps:.0e}: verdict depends on scale: "
                + ", ".join(NAME.get(v, '?') for v in verdicts))
        print(f"  {eps:>8.0e} " + " ".join(f"{NAME.get(v, '?'):>10s}" for v in verdicts))

    print()
    if failures:
        print(f"FAIL ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
        return 1
    print("ok: thresholds match the header, separate the three verdicts, "
          "and are scale-free")
    return 0


if __name__ == "__main__":
    sys.exit(main())
