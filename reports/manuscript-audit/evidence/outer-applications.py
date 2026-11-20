"""Check exact ranks and compatibility against public application classifications."""
from fractions import Fraction
from functools import cache
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import scipy

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "experiments"))
from rerun_applications import STATUS, load, make_harmonic, radio_complete, radio_disconnected, router

PRIME = 1_000_000_007


@cache
def inverse_denominator(d):
    return pow(d, -1, PRIME)


def residue(x):
    n, d = float(x).as_integer_ratio()
    return n * inverse_denominator(d) % PRIME


def determinant(matrix):
    # Each product of two residues fits in int64. Reduce after each operation.
    a = np.array([[residue(x) for x in row] for row in matrix], dtype=np.int64)
    det = 1
    for k in range(len(a)):
        pivots = np.flatnonzero(a[k:, k])
        if not pivots.size:
            return 0
        j = k + int(pivots[0])
        if j != k:
            a[[k, j]] = a[[j, k]]
            det = -det
        pivot = int(a[k, k])
        det = det * pivot % PRIME
        factors = a[k+1:, k] * pow(pivot, -1, PRIME) % PRIME
        a[k+1:, k+1:] = (a[k+1:, k+1:] - factors[:, None] * a[k, k+1:]) % PRIME
    return det


def digest(a):
    return hashlib.sha256(a.astype('<f8', copy=False).tobytes(order='C')).hexdigest()


print("NumPy", np.__version__, "SciPy", scipy.__version__, "prime", PRIME)
record = json.loads((root / "results/applications_final.json").read_text())
historical = {row["case"]: (row["router_class"], row["router_rank"])
              for group in ("radio", "harmonic") for row in record[group]["rows"]}
lib = load()
for degree, samples in [(7, 4096), (11, 8192), (15, 16384)]:
    for kind in ("full", "equator"):
        seed = 2000 + degree + (100 if kind == "equator" else 0)
        a, b, x = make_harmonic(degree, samples, kind, seed)
        # Match the generator's route controls and seed on this very input.
        route = router(lib, a, b, x, 94000 + degree + int(kind == "equator"), 4)
        assert (STATUS[int(route[0])], int(route[2])) == historical[f"L{degree}_{kind}"]
        remove = set()
        if kind == "equator":
            zonal = [j*j for j in range(degree+1)]
            assert a[0, 0] != 0 and np.all(a[:, zonal] == a[0, zonal])
            remove.update(zonal[1:])
        keep = [j for j in range(a.shape[1]) if j not in remove]
        k = len(keep)
        minor = a[:k+1, keep]
        det_a = determinant(minor[:k])
        det_ab = determinant(np.column_stack((minor, b[:k+1])))
        assert det_a and det_ab, (degree, kind, det_a, det_ab)
        print(f"L={degree} {kind} seed={seed} shape={a.shape} ranks={k},{k+1} "
              f"router={STATUS[int(route[0])]}/{int(route[2])} det_mod={det_a},{det_ab} A_sha256={digest(a)} b_sha256={digest(b)}",
              flush=True)

# A single failed cycle proves inconsistency even if another row fixes a gauge.
for i, (size, kind) in enumerate([(64, "gauge"), (64, "reference"), (128, "gauge"),
                                  (128, "disconnected"), (256, "gauge"), (256, "perturbed")]):
    seed = 1001 + i
    if kind == "disconnected":
        a, b, x = radio_disconnected(size, seed)
        component = size // 2
    else:
        a, b, x = radio_complete(size, kind == "reference", kind == "perturbed", seed)
        component = size
    for j in range(2, component):
        ids = [0, component + j - 3, j - 1]
        assert np.array_equal(a[ids[0]] + a[ids[1]], a[ids[2]])
        b01, b1j, b0j = (Fraction(float(b[t])) for t in ids)
        defect = b01 + b1j - b0j
        if defect:
            break
    else:
        raise AssertionError(("no failed triangle", size, kind))
    route = router(lib, a, b, x, 93000 + i, 4)
    name = "inconsistent" if kind == "perturbed" else kind
    assert (STATUS[int(route[0])], int(route[2])) == historical[f"N{size}_{name}"]
    print(f"N={size} {kind} seed={seed} rows={ids} cycle_defect={defect} "
          f"router={STATUS[int(route[0])]}/{int(route[2])}", flush=True)
