"""Research-only exact rational reference for affine interface composition.

This is NOT the production ABS and makes no performance claim.
Run: python -m unittest discover -s research/graph_butterfly -p 'test_*.py'
"""
from fractions import Fraction as Q


def rref(rows, n, pivot_columns=None):
    """Reduced echelon augmented matrix, with inconsistency detection."""
    a = [[Q(v) for v in row] for row in rows]
    if pivot_columns is None:\n        pivot_columns = n\n    pivots = []
    k = 0
    for j in range(pivot_columns):
        p = next((i for i in range(k, len(a)) if a[i][j]), None)
        if p is None:
            continue
        a[k], a[p] = a[p], a[k]
        scale = a[k][j]
        a[k] = [v / scale for v in a[k]]
        for i in range(len(a)):
            if i != k and a[i][j]:
                t = a[i][j]
                a[i] = [v - t * w for v, w in zip(a[i], a[k])]
        pivots.append(j)
        k += 1
        if k == len(a):
            break
    if any(all(v == 0 for v in row[:n]) and row[n] for row in a):
        return None
    return a, pivots


def project_block(rows, internal, separator):
    """Exact existential elimination of internal columns.

    rows use column order [internal variables, separator variables, RHS].
    Return constraints only on separator, without claiming reconstruction.
    """
    ni, ns = internal, separator
    if any(len(row) != ni + ns + 1 for row in rows):
        raise ValueError("invalid block row")
    reduced = rref(rows, ni + ns, pivot_columns=ni)
    if reduced is None:
        return None
    a, _ = reduced
    return [row[ni:] for row in a if all(v == 0 for v in row[:ni])]


def interface_feasible(left, right, left_internal, right_internal, separator):
    """B: reference composition by intersection of exact interface constraints."""
    l = project_block(left, left_internal, separator)
    r = project_block(right, right_internal, separator)
    if l is None or r is None:
        return False
    return rref(l + r, separator) is not None


def interface_feasible_incremental(left, right, left_internal, right_internal, separator):
    """C candidate: insert interface rows incrementally, checking rank and RHS.

    This is a semantic reference, NOT yet a paper-derived optimized butterfly.
    No distinct algorithmic advantage is asserted.
    """
    l = project_block(left, left_internal, separator)
    r = project_block(right, right_internal, separator)
    if l is None or r is None:
        return False
    accepted = []
    for row in l + r:
        if rref(accepted + [row], separator) is None:
            return False
        accepted.append(row)
    return True
