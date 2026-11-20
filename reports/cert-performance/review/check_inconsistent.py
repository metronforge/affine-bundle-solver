#!/usr/bin/env python3
"""Differential verifier test with independent exact dyadic sign/radius bounds.

Usage: python3 check_inconsistent.py BASE_LIB CANDIDATE_LIB
Both arguments refer to libstatus_verifier. The only build is a temporary,
portable helper to obtain the C implementation's fenv constants.
"""
import argparse
import ctypes as C
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile


DoublePtr = C.POINTER(C.c_double)
TINY = math.ulp(0.0)
LARGE = sys.float_info.max
SEED = 0x5769746E657373


class Witness(C.Structure):
    _fields_ = [("m", C.c_int), ("y", DoublePtr), ("pivot_row", C.c_int)]


def verifier(path):
    f = C.CDLL(str(path.resolve())).bs_verify_inconsistent
    f.argtypes = [DoublePtr, DoublePtr, C.c_int, C.c_int, C.POINTER(Witness),
                  DoublePtr, DoublePtr, DoublePtr]
    f.restype = C.c_int
    return f


def fenv_library(directory):
    path = directory / "fenv.so"
    subprocess.run([os.environ.get("CC", "cc"), "-x", "c", "-", "-shared",
                    "-fPIC", "-o", path, "-lm"], check=True, text=True, input="""
#include <fenv.h>
int set_mode(int n) {
    int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
    return fesetround(modes[n]);
}
int get_mode(void) { return fegetround(); }
""")
    return C.CDLL(str(path))


def cases():
    rng = random.Random(SEED)
    for n in (0, 1, 2, 7, 8, 9, 15, 16, 17, 31, 32, 33,
              63, 64, 65, 127, 128, 129, 255, 256, 257):
        m = 9
        y = [0.0, 0.5, -0.5, 0.0, -0.0, 1.25, -1.25, -0.0, 0.5]
        b = [LARGE, 1, 1, TINY, -LARGE, 0, 0, TINY, -2]
        row = [rng.uniform(-1.0, 1.0) for _ in range(n)]
        tail = [math.nextafter(x, LARGE) for x in row]
        A = [LARGE] * n + row + row + [TINY] * n + [-LARGE] * n + tail + row + [-TINY] * n + [-0.0] * n
        yield "tile-cancellation", A, b, y, 8
        yield "all-zero-source", [0.0] * (m*n), [0.0] * m, y, 8
    # Set E = frexp(y).exponent + frexp(b).exponent using b as
    # the unique largest entry. This sets ey-E to each guard boundary.
    for yr in (TINY, sys.float_info.min, 0.75, LARGE, -LARGE):
        for diff in (-501, -500, -499, 499, 500, 501):
            bval = math.ldexp(0.75, -diff)
            aval = math.copysign(min(abs(bval), math.ldexp(1.0, -500)), yr)
            yield "scaled-y-boundary", [aval, -aval, -0.0], [bval], [yr], 0
            yield "zero-column-y-boundary", [0.0, -0.0], [bval], [yr], 0
    # Two adjacent normal framed products have a subnormal *difference*.
    # E=0 is fixed by the final row; that row also carries the sign proof.
    a = math.ldexp(1.0, -500)
    w = math.ldexp(1.0, -501)
    for s in (-1.0, 1.0):
        yield "subnormal-sum", [math.nextafter(a, LARGE), a, -0.0], [0., 0., 0.25], [s*w, -s*w, 1.], 2
    for ae in (-500, 500):
        a0 = math.ldexp(1.0, ae)
        for a in (math.nextafter(a0, 0.0), a0, math.nextafter(a0, LARGE)):
            for y in ([1.0, -1.0], [TINY, -2*TINY], [LARGE, -LARGE]):
                yield "matrix-boundary", [a, -a, a, a], [a, 0], y, 0
    for x in (TINY, math.nextafter(sys.float_info.min, 0),
              sys.float_info.min, 1.0, LARGE):
        for z in (TINY, sys.float_info.min, 1.0, LARGE):
            yield "range", [x, z, -x, -z], [z, 0], [x, -x], 0
            yield "sign-zero", [x, z, -x, -z], [z, z], [x, -x], 0
    # Consumers compare caller modes too. Also exercise validation before
    # any mode changes and rejection after the interval includes zero.
    yield "zero-pivot", [1., 0.], [1., 0.], [-0., 1.], 0
    yield "pivot-out-of-range", [1.], [1.], [1.], -1
    yield "nan-inactive", [1., float("nan")], [1., 0.], [1., 0.], 0
    yield "infinite-rhs", [1.], [math.inf], [1.], 0
    yield "infinite-witness", [1.], [1.], [-math.inf], 0
    yield "zero-pivot-row-source", [0., 1.], [0., 1.], [1., 1.], 0

    def varied(exponents):
        if rng.random() < 0.12:
            return rng.choice((-0.0, 0.0))
        return math.ldexp(rng.choice((-1, 1)) * rng.uniform(0.5, 0.9999999999999999),
                          rng.choice(exponents))

    for trial in range(1300):
        m = rng.choice((1, 2, 3, 4, 7, 13, 23))
        n = rng.choice((0, 1, 2, 3, 5, 8, 13, 17, 32))
        spreads = ((-7, -1, 0, 3, 10), (-499, -498, -300, -1, 80, 240),
                   (-1073, -1022, -560, -499, -1, 0, 499, 700, 1024))
        exponents = spreads[trial % 3]
        A = [varied(exponents) for _ in range(m*n)]
        b = [varied(exponents) for _ in range(m)]
        y = [varied(exponents) for _ in range(m)]
        k = rng.randrange(m)
        if y[k] == 0 and trial % 7:
            y[k] = -1.0
        if m >= 2 and trial % 5 == 0:
            y[0], y[1] = 1.0, -1.0
            A[n:2*n] = A[:n]
            b[0] = math.nextafter(b[1], 0.0)
        yield "random-" + str(trial % 3), A, b, y, k


def exact_oracle(A, b, y, k, status, lo, hi, eta):
    m, n = len(y), len(A) // len(y)
    # E is defined by every nonzero input pair, independently of the C scan.
    exps = [math.frexp(yi)[1] + math.frexp(v)[1] for i, yi in enumerate(y)
            if yi for v in [b[i], *A[i*n:(i+1)*n]] if v]
    assert exps
    E = max(exps)
    Y, B = list(map(Fraction, y)), list(map(Fraction, b))
    ytb = sum(v*w for v, w in zip(Y, B)) * Fraction(2) ** (-E)
    assert Fraction(lo) <= ytb <= Fraction(hi), (lo, hi, float(ytb))
    if status == 4:
        return "sign-rejected"
    weight_ok = all(-500 <= math.frexp(v)[1] - E <= 500 for v in y if v)
    matrix_ok = all(v == 0 or 2.0**-500 <= abs(v) <= 2.0**500
                    for i in range(m) if y[i] for v in A[i*n:(i+1)*n])
    domain = "eligible" if weight_ok and matrix_ok else "fallback"
    if status:
        return domain
    assert math.isfinite(eta) and eta >= 0 and (lo > 0 or hi < 0)
    a = list(map(Fraction, A))
    ytA = [sum(Y[i]*a[i*n+j] for i in range(m)) for j in range(n)]
    row_norm_sq = sum(v*v for v in a[k*n:(k+1)*n]) + B[k]**2
    assert Fraction(eta)**2 * Y[k]**2 * row_norm_sq >= sum(v*v for v in ytA)
    return domain


def array(values):
    # Keep the API's non-null A requirement when n=0.
    return (C.c_double * max(1, len(values)))(*values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    fv = [verifier(p) for p in (args.base, args.candidate)]
    stats, families, domains = Counter(), Counter(), Counter()
    modes = ["nearest", "upward", "downward", "toward-zero"]
    with tempfile.TemporaryDirectory() as d:
        env = fenv_library(Path(d))
        original = env.get_mode()
        for index, (family, A, b, y, k) in enumerate(cases()):
            n = len(A) // len(y)
            a0, b0, y0 = map(array, (A, b, y))
            witness = Witness(len(y), y0, k)
            reference = None
            for mode in range(4):
                for f in fv:
                    out = [C.c_double(17.125), C.c_double(17.125), C.c_double(-3)]
                    assert env.set_mode(mode) == 0
                    expected = env.get_mode()
                    try:
                        rc = f(a0, b0, len(y), n, C.byref(witness),
                               *(C.byref(v) for v in out))
                        actual = env.get_mode()
                    finally:
                        assert env.set_mode(0) == 0
                    assert actual == expected, (index, family, mode, "mode changed")
                    vals = [v.value for v in out]
                    bits = (rc, b"".join(struct.pack(">d", v) for v in vals))
                    if reference is None:
                        reference = bits
                        stats[str(rc)] += 1
                        families[family] += 1
                        if rc in (0, 6) or (rc == 4 and vals[0] != 17.125):
                            try:
                                domain = exact_oracle(A, b, y, k, rc, *vals)
                                domains[domain] += 1
                            except AssertionError as exc:
                                raise AssertionError((index, family, "oracle", vals)) from exc
                    assert bits == reference, (index, family, modes[mode], bits, reference)
        assert env.get_mode() == original
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (args.base, args.candidate)]
    count = sum(stats.values())
    print(json.dumps(dict(base_sha256=hashes[0], candidate_sha256=hashes[1],
                          seed=SEED, cases=count, paired_comparisons=count*4,
                          checked_calls=count*8, caller_modes=modes,
                          return_codes=stats, input_families=families,
                          input_guard_classes=domains, exact_accepted_radii=stats["0"],
                          outcome="pass"), indent=2))


if __name__ == "__main__":
    main()
