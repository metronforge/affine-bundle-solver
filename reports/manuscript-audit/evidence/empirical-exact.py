"""Replay stored-data oracles against a clean built checkout given as argv[1]."""
import copy
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / "tests"), str(root / "experiments")]
import pbt_equivalence_orbits as orbit
import rerun_applications as apps


def exact_ints(a):
    # IEEE binary64 integer values can exceed int64 after dyadic shifts.
    return np.vectorize(int, otypes=[object])(a)


def reduce_mod(matrix, prime):
    a = []
    for row in matrix:
        vals = [float(x).as_integer_ratio() for x in row]
        a.append([v * pow(d, -1, prime) % prime for v, d in vals])
    return a


def det_mod(matrix, prime):
    a = reduce_mod(matrix, prime)
    det = 1
    for j in range(len(a)):
        pivot = next((i for i in range(j, len(a)) if a[i][j]), None)
        if pivot is None:
            return 0
        if pivot != j:
            det *= -1
            a[j], a[pivot] = a[pivot], a[j]
        det = det * a[j][j] % prime
        inv = pow(a[j][j], -1, prime)
        for i in range(j + 1, len(a)):
            scale = a[i][j] * inv
            a[i] = [(v - scale * w) % prime for v, w in zip(a[i], a[j])]
    return det


def example_oracles():
    rng = np.random.default_rng(3)
    a = rng.standard_normal((48, 8))
    b = a @ rng.standard_normal(8)
    p = 1000000007
    minor_a = det_mod(a[:8], p)
    minor_ab = det_mod(np.column_stack([a, b])[:9], p)
    assert minor_a and minor_ab
    print("seed-3 A, [A|b] leading minors modulo", p, minor_a, minor_ab)
    a, b, _ = apps.radio_complete(64, seed=1001)
    # Lexicographic upper-triangle ordering. Edges 0→1, 1→j, 0→j.
    for j in range(2, 64):
        ids = [0, 63 + j - 2, j - 1]
        assert np.all(a[ids[0]] + a[ids[1]] == a[ids[2]])
        rhs = [Fraction.from_float(float(b[i])) for i in ids]
        defect = rhs[0] + rhs[1] - rhs[2]
        if defect:
            print("N64_gauge triangle vertices", (0, 1, j), "row IDs", ids, "exact RHS defect", defect)
            break
    else:
        raise AssertionError("no triangle defect")

    # A nonzero modular minor is also nonzero over the dyadic rationals.
    a, _, _ = apps.make_harmonic(7, 4096, 'equator', 2107)
    work = reduce_mod(a[:64], p)
    row_ids = list(range(len(work)))
    rows, cols = [], []
    for j in range(a.shape[1]):
        k = len(rows)
        i = next((i for i in range(k, len(work)) if work[i][j]), None)
        if i is None:
            continue
        row_ids[k], row_ids[i] = row_ids[i], row_ids[k]
        work[k], work[i] = work[i], work[k]
        rows.append(row_ids[k])
        cols.append(j)
        inv = pow(work[k][j], -1, p)
        for i in range(k + 1, len(work)):
            scale = work[i][j] * inv
            work[i] = [(v - scale * w) % p for v, w in zip(work[i], work[k])]
    minor = det_mod(a[np.ix_(rows, cols)], p)
    assert minor and len(rows) > 15
    print("L7_equator stored coefficient rank lower bound", len(rows),
          "minor modulo", p, minor, "rows", rows, "cols", cols)


def translation_oracle():
    shift = orbit.affine_shift
    check = orbit.Report.check
    classified = []
    current = {}

    def inspect_shift(a, b, x, rng, exp):
        preview = copy.deepcopy(rng)
        c = exact_ints(preview.integers(-3, 4, size=a.shape[1])) * (1 << exp)
        at, bt, xt = shift(a, b, x, rng, exp)
        current.update(a=a, b=b, bt=bt, c=c, exp=exp)
        return at, bt, xt

    def inspect_check(report, prop, ok, severity='hard', **ctx):
        check(report, prop, ok, severity, **ctx)
        if ok or 'affine_translation' not in prop:
            return
        a, b, bt, c = [exact_ints(current[k]) for k in ('a', 'b', 'bt', 'c')]
        r = ctx.get('rank', 3)
        u, v = a[:, :r], a[:r, :]
        assert np.array_equal(u @ v, a) and np.array_equal(v[:, :r], np.eye(r))
        original_inconsistent = np.any(u @ b[:r] != b)
        translated_inconsistent = np.any(u @ bt[:r] != bt)
        rounded = np.any(b - a @ c != bt)
        record = dict(property=prop, trial=ctx['t'], exp=current['exp'],
                      original_inconsistent=bool(original_inconsistent),
                      stored_inconsistent=bool(translated_inconsistent),
                      rounded_rhs=bool(rounded), returned=ctx['got']['status'])
        if original_inconsistent and not translated_inconsistent and not any(
                row['original_inconsistent'] and not row['stored_inconsistent'] for row in classified):
            # U,V identity proves consistency with these first r unknowns.
            print("lost-contradiction witness", json.dumps(record),
                  "A =", a.tolist(), "b =", b.tolist(), "c =", c.tolist(),
                  "stored b' =", bt.tolist(), "exact x' =", [*bt[:r], *([0] * (a.shape[1]-r))])
        classified.append(record)

    orbit.affine_shift = inspect_shift
    orbit.Report.check = inspect_check
    report = orbit.run("full").compact()
    counts = Counter((r['exp'], r['original_inconsistent'], r['stored_inconsistent'], r['rounded_rhs'])
                     for r in classified)
    print("PBT", report['checks'], report['failure_counts_by_severity'])
    for key, count in sorted(counts.items()):
        print("exp, original inconsistent, stored inconsistent, RHS rounded, count", *key, count)


example_oracles()
translation_oracle()
