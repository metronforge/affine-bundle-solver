import os
import ctypes
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
# Shared objects are looked up in ABS_LIB_DIR when it is set, so that CTest
# can run this battery against a CMake build tree without touching the
# repository root.  Unset, it falls back to the root, which is where
# build.sh leaves them.
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
cert = ctypes.CDLL(str(LIBDIR / 'libcertified_solver.so'))
ver = ctypes.CDLL(str(LIBDIR / 'libstatus_verifier.so'))
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
# the topological degeneracy of distance to inconsistency for tall systems
# (Proposition on status-set closure: d_inc = 0 for a tall compatible system).
#
# Candidate quality matters and is not a property of the data.  b0 = A @ x is
# compatible, so y^T b0 vanishes for an exact left-null y; the verified
# interval then legitimately straddles zero and the checker refuses.  A
# candidate is accepted only when the rounding-level residual of y^T b0
# exceeds the verifier's own error envelope.  Picking an arbitrary basis
# direction is therefore a coin flip -- measured on one platform only 3 of the
# 40 left-null basis vectors were accepted, and which 3 depends on the LAPACK
# build.  That made this assertion environment-dependent.
#
# The generator instead aims: among unit vectors of the left null space,
# |y^T b0| is maximised by the normalised projection of b0 onto that space.
# This is the strongest available candidate and is deterministic.  The basis
# directions are kept as a fallback.  The checker is unchanged throughout and
# decides alone; the search only affects which candidates it is offered.
Q, _ = np.linalg.qr(A, mode='complete')
Qn = Q[:, A.shape[1]:]
src = np.sqrt(np.sum(A * A, axis=1) + b0 * b0)

proj = Qn @ (Qn.T @ b0)
proj_norm = float(np.linalg.norm(proj))
candidates = []
if proj_norm > 0.0:
    candidates.append(proj / proj_norm)
candidates += [Qn[:, j] for j in range(Qn.shape[1])]

lo = ctypes.c_double(); hi = ctypes.c_double(); eta = ctypes.c_double()


def offer(A_, b_, y_raw):
    """Offer one left-null candidate to the checker and report what it said."""
    y = arr(y_raw)
    s_ = np.sqrt(np.sum(A_ * A_, axis=1) + b_ * b_)
    k = int(np.argmax(np.abs(y) * s_))
    w = InconsistentWitness(A_.shape[0], ptr(y), k)
    rc = ver.bs_verify_inconsistent(ptr(A_), ptr(b_), A_.shape[0], A_.shape[1],
                                    ctypes.byref(w), ctypes.byref(lo),
                                    ctypes.byref(hi), ctypes.byref(eta))
    return rc, lo.value, hi.value, eta.value


# ---------------------------------------------------------------------------
# Part one: the degenerate case, asserted one-sidedly.
#
# b0 = A @ x is COMPATIBLE, so y^T b0 vanishes for an exact left-null y and is
# nonzero here only through rounding.  Whether the verified interval clears
# zero is therefore a property of the machine's arithmetic and not of the
# library: measured at 5.2e-15 of left-null projection on one platform, 4 of
# 41 candidates were accepted; at 4.0e-15 on another, none were, and the
# checker correctly refused because there is nothing to certify.
#
# Requiring an acceptance here would assert that rounding noise on this
# machine exceeds the verifier's own error envelope, which is not a claim the
# library makes.  What IS invariant, and is asserted, is one-sided: an
# acceptance must carry a small radius.  A checker that certified a distant
# system would fail this; a checker that refuses everything would pass it,
# which is why part two exists.
# ---------------------------------------------------------------------------
accepted = 0
best_eta = math.inf
first_rc, first_lo, first_hi = None, None, None
for y_raw in candidates:
    rc, l, h, e = offer(A, b0, y_raw)
    if first_rc is None:
        first_rc, first_lo, first_hi = rc, l, h
    if rc == 0:
        accepted += 1
        assert e < 1e-12, e
        best_eta = min(best_eta, e)

# Measurement, not an assertion.  Reported so a reproduction on other hardware
# has the number rather than a bare pass.
print(f"degenerate case: ||P_null b0|| = {proj_norm:.3e}, "
      f"{accepted} of {len(candidates)} candidates accepted, "
      f"first interval [{first_lo:.3e}, {first_hi:.3e}]")

# ---------------------------------------------------------------------------
# Part two: a system that is inconsistent by a controlled amount.
#
# b0 is pushed off the column space along a left-null direction by delta,
# chosen far above any rounding-level effect and far below the scale of the
# data.  Now y^T b is delta rather than noise, the interval must clear zero on
# any machine, and the checker is required to certify.  This is what stops
# part one's one-sided assertion from being vacuous.
# ---------------------------------------------------------------------------
u = candidates[0] if proj_norm > 0.0 else Qn[:, 0]
u = arr(u / np.linalg.norm(u))
delta = 1e-8 * float(np.linalg.norm(b0))
b_inc = arr(b0 + delta * u)

rc, l, h, e = offer(A, b_inc, u)
print(f"controlled case: delta = {delta:.3e}, rc={rc}, "
      f"interval [{l:.3e}, {h:.3e}], eta = {e:.3e}")

assert rc == 0, (
    f"the checker refused a system inconsistent by delta={delta:.3e}, which is "
    f"{delta / max(proj_norm, 1e-300):.1e} times the machine-scale left-null "
    f"projection; interval [{l:.3e}, {h:.3e}]")
assert l > 0.0, f"verified interval straddles zero at delta={delta:.3e}: [{l:.3e}, {h:.3e}]"
assert math.isfinite(e), e
assert e < 1e-6, (
    f"certificate radius {e:.3e} is not tight for a system inconsistent by "
    f"delta={delta:.3e}")

# Left as infinity when nothing was accepted: the controlled case's radius
# belongs to a different system and must not be reported under this label.

for eps, eu, ei in rows:
    print(f'eps={eps:.0e} eta_unique={eu:.3e} eta_inconsistent={ei:.3e}')
if accepted:
    print(f'compatible-adversarial eta_inconsistent={best_eta:.3e} '
          f'({accepted}/{len(candidates)} candidates accepted, '
          f'||P_null b0||={proj_norm:.2e})')
else:
    print(f'compatible-adversarial eta_inconsistent=not observed '
          f'(0/{len(candidates)} candidates accepted, '
          f'||P_null b0||={proj_norm:.2e}); the rounding-level residual did '
          f'not clear the verifier envelope on this platform')
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
