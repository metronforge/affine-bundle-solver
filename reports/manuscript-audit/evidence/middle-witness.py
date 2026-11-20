"""Check §4.4 against the public ABI and §4.2 against the frozen Fourier fixture."""
import ctypes as ct
import math
from pathlib import Path
import sys

import numpy as np

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'tests'))
from api_regression_corpus import discover_cases, load_manifest
from api_regression_oracle import adjudicate

pointer = ct.POINTER(ct.c_double)


class LeftWitness(ct.Structure):
    _fields_ = [('m', ct.c_int), ('y', pointer), ('pivot', ct.c_int)]


def offer(verifier, a, b, y):
    pair = ct.c_double * 2
    coefficients, rhs, weights = pair(*a), pair(*b), pair(*y)
    witness = LeftWitness(2, weights, 1)
    lo, hi, eta = (ct.c_double() for _ in range(3))
    rc = verifier(coefficients, rhs, 2, 1, ct.byref(witness),
                  ct.byref(lo), ct.byref(hi), ct.byref(eta))
    print(f'yTb={sum(x * t for x, t in zip(y, b)):g} '
          f'interval=[{lo.value:g}, {hi.value:g}] eta={eta.value:.17g} rc={rc}')
    assert rc == 0 and lo.value > 0
    return eta.value


def main():
    verifier = ct.CDLL(str(root / 'libstatus_verifier.so')).bs_verify_inconsistent
    verifier.argtypes = [pointer, pointer, ct.c_int, ct.c_int,
                         ct.POINTER(LeftWitness), pointer, pointer, pointer]
    eta = offer(verifier, [1, 1], [0, 1], [1, 1])
    assert offer(verifier, [-2, 4], [0, 4], [-0.5, 0.25]) == eta
    assert offer(verifier, [-2, 4], [0, 4], [-1.5, 0.75]) == eta

    fixture_dir = root / 'tests/fixtures/api-regression'
    case = next(c for c in discover_cases(fixture_dir, load_manifest(fixture_dir))
                if c.case_id == 'T8-031')
    a = case.A
    assert a.shape == (64, 32) and not np.any(case.b)
    assert np.array_equal(a[:32, :16], a[32:, 16:])
    assert np.array_equal(a[:32, 16:], -a[32:, :16])
    oracle = adjudicate(case)
    assert (oracle.rank_a, oracle.rank_augmented, oracle.exact_status) == (32, 32, 'UNIQUE')
    print('T8-031 exact block structure, rank(A)=rank([A,b])=32, UNIQUE')

    # Nearest rank-one augmented rows on the bisecting line, as derived in the review.
    w = np.array([[1., 0., 0.], [1., 0., 1.]])
    direction = np.array([math.cos(math.pi / 8), 0., math.sin(math.pi / 8)])
    projected = np.outer(w @ direction, direction)
    relative = np.linalg.norm(w - projected, axis=1) / np.linalg.norm(w, axis=1)
    assert np.allclose(relative, math.sin(math.pi / 8), rtol=1e-15, atol=0)
    print('bisector relative row displacements:', *relative)


if __name__ == '__main__':
    main()
