import ctypes
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
cert = ctypes.CDLL(str(ROOT / 'libcertified_solver.so'))
ver = ctypes.CDLL(str(ROOT / 'libstatus_verifier.so'))
DP = ctypes.POINTER(ctypes.c_double)

class Result(ctypes.Structure):
    _fields_ = [
        ('fast_status', ctypes.c_int), ('fast_certainty', ctypes.c_int),
        ('rank_estimate', ctypes.c_int), ('rank_lo', ctypes.c_int), ('rank_hi', ctypes.c_int),
        ('eta_x', ctypes.c_double), ('certified_status', ctypes.c_int),
        ('eta_status', ctypes.c_double), ('generator_code', ctypes.c_int), ('verifier_code', ctypes.c_int),
        ('accepted_status_mask', ctypes.c_int),
        ('eta_unique', ctypes.c_double), ('eta_infinite', ctypes.c_double), ('eta_inconsistent', ctypes.c_double),
        ('unique_generator_code', ctypes.c_int), ('unique_verifier_code', ctypes.c_int),
        ('infinite_generator_code', ctypes.c_int), ('infinite_verifier_code', ctypes.c_int),
        ('inconsistent_generator_code', ctypes.c_int), ('inconsistent_verifier_code', ctypes.c_int),
    ]

class InconsistentWitness(ctypes.Structure):
    _fields_ = [('m', ctypes.c_int), ('y', DP), ('pivot_row', ctypes.c_int)]

cert.bsolve_certified_api.argtypes = [
    DP, DP, DP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_ulonglong, ctypes.c_int, ctypes.POINTER(Result)
]
cert.bsolve_certified_api.restype = ctypes.c_int
ver.bs_verify_inconsistent.argtypes = [
    DP, DP, ctypes.c_int, ctypes.c_int, ctypes.POINTER(InconsistentWitness),
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)
]
ver.bs_verify_inconsistent.restype = ctypes.c_int

def arr(a):
    return np.ascontiguousarray(a, dtype=np.float64)

def ptr(a):
    return a.ctypes.data_as(DP)

def call(A, b, x):
    A, b, x = arr(A), arr(b), arr(x)
    out = Result()
    rc = cert.bsolve_certified_api(ptr(A), ptr(b), ptr(x), A.shape[0], A.shape[1],
                                   1, 2, 2, 12345, 0, ctypes.byref(out))
    assert rc == 0
    return out

# A fixed tall full-column-rank family.  The right-hand side is progressively
# perturbed away from compatibility while A is unchanged.
rng = np.random.default_rng(3)
A = arr(rng.standard_normal((48, 8)))
x = arr(rng.standard_normal(8))
b0 = arr(A @ x)
scale = max(1.0, np.linalg.norm(A[-1]))

epsilons = [1e-12, 1e-9, 1e-6, 1e-3, 1e-1]
rows = []
for eps in epsilons:
    b = b0.copy()
    b[-1] += eps * scale
    r = call(A, b, x)
    assert r.accepted_status_mask & 1
    assert r.accepted_status_mask & 4
    assert math.isfinite(r.eta_unique)
    assert math.isfinite(r.eta_inconsistent)
    rows.append((eps, r.eta_unique, r.eta_inconsistent))

# The compatibility/unique radius tracks contradiction scale, while the
# inconsistent radius is essentially a machine-scale left-null correction.
assert rows[0][1] < rows[-1][1] * 1e-8
inc = np.array([q[2] for q in rows])
assert inc.max() < 1e-12
assert inc.max() / inc.min() < 10.0

# Semantic attack: even the nearly compatible floating data admit a machine-
# scale inconsistent proof object.  This does not violate soundness; it records
# the topological degeneracy of distance to inconsistency for tall systems.
Q, _ = np.linalg.qr(A, mode='complete')
y = arr(Q[:, A.shape[1]])
src = np.sqrt(np.sum(A * A, axis=1) + b0 * b0)
k = int(np.argmax(np.abs(y) * src))
w = InconsistentWitness(A.shape[0], ptr(y), k)
lo = ctypes.c_double(); hi = ctypes.c_double(); eta = ctypes.c_double()
rc = ver.bs_verify_inconsistent(ptr(A), ptr(b0), A.shape[0], A.shape[1],
                                ctypes.byref(w), ctypes.byref(lo), ctypes.byref(hi), ctypes.byref(eta))
assert rc == 0, (rc, lo.value, hi.value)
assert eta.value < 1e-12, eta.value

for eps, eu, ei in rows:
    print(f'eps={eps:.0e} eta_unique={eu:.3e} eta_inconsistent={ei:.3e}')
print(f'compatible-adversarial eta_inconsistent={eta.value:.3e}')
print('PRIMARY PASS')

# Mirror case: an exactly compatible tall system with exact rank 4 < n=6.
# The data are built from small integers so the two column dependencies and the
# chosen right-hand side are exact properties of the stored binary64 values.
# At such an exact-infinite source point all three exact status-set distances
# have zero infimum: infinite trivially, unique by arbitrarily small rank
# completion that preserves compatibility, and inconsistent by the tall
# left-null perturbation mechanism.
rng2 = np.random.default_rng(17)
base = rng2.integers(-8, 9, size=(40, 4)).astype(np.float64)
for i in range(base.shape[0]):
    if not np.any(base[i]):
        base[i, 0] = 1.0
A2 = arr(np.column_stack([
    base,
    base[:, 0] + base[:, 1],
    2.0 * base[:, 2] - base[:, 3],
]))
x2 = arr(np.array([1.0, 2.0, 0.0, 0.0, 0.0, 0.0]))
b2 = arr(A2[:, 0] + 2.0 * A2[:, 1])
assert np.max(np.abs(A2 @ x2 - b2)) == 0.0
r2 = call(A2, b2, x2)
assert r2.accepted_status_mask == 7, (
    r2.accepted_status_mask,
    r2.unique_generator_code, r2.unique_verifier_code,
    r2.infinite_generator_code, r2.infinite_verifier_code,
    r2.inconsistent_generator_code, r2.inconsistent_verifier_code,
)
mirror = np.array([r2.eta_unique, r2.eta_infinite, r2.eta_inconsistent])
assert np.all(np.isfinite(mirror))
assert mirror.max() < 1e-12, mirror
print('rank-deficient-compatible '
      f'eta_unique={r2.eta_unique:.3e} '
      f'eta_infinite={r2.eta_infinite:.3e} '
      f'eta_inconsistent={r2.eta_inconsistent:.3e}')
print('MIRROR PASS')
