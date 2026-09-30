"""Independent high-precision EYM subspace reference for the realified cases.

This is a normwise SVD reference, NOT a global rowwise minimax oracle.
Exact binary64 inputs enter mpmath without decimal-string rounding.
"""
import mpmath as mp
import numpy as np

# Literature: Eckart & Young (1936), doi:10.1007/BF02288367.
# The projector identity is exact algebra; the numerical eigensolve below
# is a precision-refined reference, not a validated interval eigenvalue proof.


def reference(A, b, digits=80):
    m, n = A.shape
    h, k = m // 2, n // 2
    if m % 2 or n % 2 or not (
        np.array_equal(A[:h, :k], A[h:, k:])
        and np.array_equal(A[:h, k:], -A[h:, :k])
    ):
        raise ValueError("exact complex-realification block identity is absent")
    with mp.workdps(digits):
        M = mp.matrix([[mp.mpf(float(v)) for v in row] for row in A])
        rhs = mp.matrix([mp.mpf(float(v)) for v in b])
        G = M.T * M
        values, V = mp.eigsy(G)
        # Realification commutes with the orthogonal complex structure J;
        # every real eigenspace has even dimension. The numerical gap below
        # checks that the isolated bottom cluster has dimension two here.
        if not (values[0] > 0 and values[2] > mp.mpf('1.01') * values[1]):
            raise ValueError("reference requires an isolated positive bottom pair")
        P = V[:, :2] * V[:, :2].T
        largest = max(P[j, j] for j in range(n))
        pivot = next(j for j in range(n) if P[j, j] >= largest / 2)
        z = P[:, pivot]
        z /= mp.norm(z)
        # Exact least squares, evaluated at high precision independently of LAPACK.
        x = mp.lu_solve(G, M.T * rhs)
        def radius(direction):
            az = M * direction
            residual = M * x - rhs
            return max(
                mp.sqrt(az[i]**2 + (abs(residual[i]) + abs(az[i])*mp.norm(x))**2)
                / mp.sqrt(mp.fsum(M[i,j]**2 for j in range(n)) + rhs[i]**2)
                for i in range(m)
            )
        sigma = mp.sqrt(values[0])
        return {
            'digits': digits, 'pivot': pivot,
            'sigma_min': mp.nstr(sigma, 45),
            'sigma_next_cluster': mp.nstr(mp.sqrt(values[2]), 45),
            'relative_pair_split': mp.nstr(abs(values[1]-values[0])/values[0], 8),
            'canonical_radius': mp.nstr(radius(z), 45),
            'z': [float(v) for v in z],
            'x': [float(v) for v in x],
        }


if __name__ == '__main__':
    import json
    from pathlib import Path
    from api_regression_corpus import discover_cases, load_manifest
    root = Path(__file__).resolve().parent / 'fixtures/api-regression'
    for case in discover_cases(root, load_manifest(root)):
        if case.case_id in ('T8-030', 'T8-031', 'T8-032'):
            for digits in (80, 120):
                result = reference(case.A, case.b, digits)
                result.pop('z')
                result.pop('x')
                print(json.dumps(dict(case_id=case.case_id,
                                      A_sha256=case.metadata['A_bytes_sha256'],
                                      b_sha256=case.metadata['b_bytes_sha256'], **result)))
