#!/usr/bin/env python3
"""
check_paper_claims.py -- assert that the manuscript's quantitative claims are
still reproduced by the current code.

Ordinary regression tests answer "did anything crash".  This script answers a
different and, for a paper artifact, more important question: do the specific
numbers printed in the manuscript still come out of this build?

It runs the two property batteries, parses their JSON, and compares against
the values stated in paper.tex.  A mismatch is a failure even when every
individual test passes, because a silently changed count invalidates a
sentence in the paper.

Exit status: 0 = all claims reproduced, 1 = at least one mismatch.

Usage:
    python3 tests/check_paper_claims.py            # run batteries, compare
    python3 tests/check_paper_claims.py --list     # print expectations only
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


# --------------------------------------------------------------------------
# Claims taken verbatim from paper.tex.  The "where" field is the manuscript
# location, so a failure tells you which sentence to fix.
# --------------------------------------------------------------------------

EXACT_CLAIMS = [
    # (battery, json path, expected value, where in the paper)
    ("pbt_equivalence_orbits", ["checks"], 8335,
     "Abstract; sec:results 'executes 8,335 checks'"),
    ("pbt_equivalence_orbits",
     ["failure_counts_by_severity", "known-representation"], 154,
     "Abstract; sec:results '154 explicitly labelled ... affine-translation cases'"),
    ("pbt_certificate_equivariance", ["checks"], 2271,
     "Abstract; sec:results 'A second focused battery contains 2,271 ... checks'"),
]

# Floating-point measurements.  These are NOT deterministic across platforms:
# they depend on the LAPACK/BLAS build and the compiler.  Observed spread
# between two environments (local reference vs. GitHub runner):
#
#     inconsistent_eta_max     3.871e-15  vs  3.804e-15   (-1.7%)
#     inconsistent_eta_median  9.418e-17  vs  1.004e-16   (+6.6%)
#     shadow_ratio_max         2.000      vs  1.235
#
# Asserting the printed digits would therefore test the platform, not the
# code.  What the manuscript actually relies on is the SCALE -- accepted
# radii stay at machine precision -- so that is what is asserted here, with
# the observed value reported for the record.  The reference values are kept
# so a drift of orders of magnitude is still visible in the output.
APPROX_CLAIMS = []

BOUND_CLAIMS = [
    # (battery, json path, upper bound, reference value, where)
    ("pbt_certificate_equivariance", ["stats", "inconsistent_eta_max"],
     1e-14, 3.871e-15,
     "sec:results 'accepted inconsistency radii have maximum ...'"),
    ("pbt_certificate_equivariance", ["stats", "inconsistent_eta_median"],
     1e-15, 9.418e-17,
     "sec:results '... and median ...'"),
]

# Values the paper states as a range.  The LOWER bound here is the soundness
# statement -- "no sampled strict radius is below the shadow value" -- and
# must hold exactly.  The upper bound is descriptive of the sampled corpus.
RANGE_CLAIMS = [
    ("pbt_certificate_equivariance", ["stats", "shadow_ratio_min"], 1.0, 2.0,
     "sec:results 'no sampled strict radius is below the shadow value'"),
    ("pbt_certificate_equivariance", ["stats", "shadow_ratio_max"], 1.0, 2.0,
     "sec:results 'the strict/checker radius ratio ranges from 1 to 2'"),
]

# A hard failure in either battery is a failure regardless of counts.
NO_HARD_FAILURE = [
    ("pbt_certificate_equivariance", ["failure_counts"],
     "sec:results 'zero failure'"),
]


def dig(obj, path):
    """Walk a JSON path, returning None if any key is absent."""
    cur = obj
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def run_battery(name: str) -> dict:
    """Run one property battery and return its parsed JSON output."""
    script = TESTS / f"{name}.py"
    if not script.is_file():
        raise SystemExit(f"missing battery: {script}")
    proc = subprocess.run([sys.executable, str(script)],
                          capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"{name} exited with {proc.returncode}")
    text = proc.stdout.strip()
    start = text.find("{")
    if start < 0:
        raise SystemExit(f"{name}: no JSON found in output")
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name}: cannot parse JSON: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print the expected values without running anything")
    args = ap.parse_args()

    if args.list:
        print("Exact claims:")
        for b, p, v, w in EXACT_CLAIMS:
            print(f"  {b}:{'.'.join(p)} == {v}   [{w}]")
        print("Bound claims (machine scale; exact digits are platform-dependent):")
        for b, p, bd, rf, w in BOUND_CLAIMS:
            print(f"  {b}:{'.'.join(p)} <= {bd:g} (reference {rf:g})   [{w}]")
        print("Range claims:")
        for b, p, lo, hi, w in RANGE_CLAIMS:
            print(f"  {b}:{'.'.join(p)} in [{lo}, {hi}]   [{w}]")
        return 0

    needed = sorted({c[0] for c in
                     EXACT_CLAIMS + APPROX_CLAIMS + BOUND_CLAIMS
                     + RANGE_CLAIMS + NO_HARD_FAILURE})
    results = {}
    for name in needed:
        print(f"running {name} ...", flush=True)
        results[name] = run_battery(name)

    failures = []
    checked = 0

    print()
    print("=" * 78)
    print("Manuscript claim reproduction")
    print("=" * 78)

    for battery, path, expected, where in EXACT_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = got == expected
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {got}  (paper: {expected})")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {got}, "
                            f"paper states {expected}  -- {where}")

    for battery, path, expected, tol, where in APPROX_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = isinstance(got, (int, float)) and math.isfinite(got) and \
            abs(got - expected) <= tol * abs(expected)
        shown = f"{got:.6e}" if isinstance(got, (int, float)) else str(got)
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {shown}  (paper: {expected:.3e}, rel tol {tol})")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {shown}, "
                            f"paper states {expected:.3e}  -- {where}")

    for battery, path, bound, reference, where in BOUND_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = isinstance(got, (int, float)) and math.isfinite(got) and \
            0.0 <= got <= bound
        shown = f"{got:.6e}" if isinstance(got, (int, float)) else str(got)
        drift = (f", {got/reference:.2f}x reference"
                 if isinstance(got, (int, float)) and reference else "")
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {shown}  (must be <= {bound:.0e}{drift})")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {shown}, "
                            f"which exceeds the machine-scale bound "
                            f"{bound:.0e}  -- {where}")

    for battery, path, lo, hi, where in RANGE_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = isinstance(got, (int, float)) and lo - 1e-12 <= got <= hi + 1e-12
        shown = f"{got:.6f}" if isinstance(got, (int, float)) else str(got)
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {shown}  (paper: within [{lo}, {hi}])")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {shown}, "
                            f"paper states [{lo}, {hi}]  -- {where}")

    for battery, path, where in NO_HARD_FAILURE:
        got = dig(results[battery], path)
        checked += 1
        ok = got == {} or got == {} if isinstance(got, dict) else False
        ok = isinstance(got, dict) and len(got) == 0
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"is empty  (paper: zero failure)")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {got}, "
                            f"paper states zero failure  -- {where}")

    print()
    if failures:
        print(f"{len(failures)} of {checked} claims NOT reproduced:")
        for f in failures:
            print(f"  - {f}")
        print()
        print("A mismatch here means a sentence in paper.tex is now wrong.")
        print("Either the code changed behaviour or the manuscript needs an update;")
        print("do not silently adjust the expected values in this file.")
        return 1

    print(f"all {checked} manuscript claims reproduced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
