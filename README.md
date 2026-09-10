# Affine-Bundle Solver

A dense solver for general real linear equality systems `Ax = b` that does not
assume consistency, full rank, or uniqueness — and that reports **which of
those it can actually prove**.

Most solvers answer "here is a solution". This one answers a different
question first: *is the system uniquely solvable, underdetermined,
inconsistent, or too close to a rank transition to say?* The classification
comes with independently checkable proof objects, and the router refuses to
turn a numerical guess into an exact claim.

[![build-and-test](https://github.com/metronforge/affine-bundle-solver/actions/workflows/ci.yml/badge.svg)](https://github.com/metronforge/affine-bundle-solver/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## What it does

The solver state is an **affine bundle** `B = (R, ℓ)` — a subspace of accepted
normal directions plus the right-hand-side functional it carries. For an
incoming row `aᵀz = β`, two quantities decide everything:

```
g = (I − P)a        the part of the row not yet explained
ρ = β − aᵀx         the compatibility residual
```

`g ≠ 0` grows the bundle by one direction. `g = 0` separates a **redundant**
row (`ρ = 0`) from a **contradictory** one (`ρ ≠ 0`). That is the whole exact
calculus; everything else is about doing it safely in floating point.

Outputs:

| Status | Meaning |
|---|---|
| `UNIQUE` | exactly one solution |
| `INFINITE` | consistent, solution set positive-dimensional |
| `INCONSISTENT` | no solution |
| `UNDECIDABLE` | data too close to a rank transition to decide; a **rank interval** `[r₋, r₊]` is returned instead of a point rank |
| `FAIL` | resource failure (e.g. allocation); makes no claim about the data |

`UNDECIDABLE` is the point of the design. A row near the rank boundary is not
forced into a binary answer, and resource exhaustion is never converted into a
status verdict.

Field-by-field semantics, the three decision thresholds, and what each
guarantee does and does not cover are in [`docs/api.md`](docs/api.md), which
is written to be read without the manuscript.

### Certificates

An optional audit API attempts three typed proof objects — nearby exact
systems that are respectively unique, infinite, and inconsistent — and returns
the profile `η = (η_uniq, η_inf, η_inc)` of independently verified upper
bounds on how far the source data is from each class.

Two things to be clear about:

- The **checker owns every radius**. It recomputes bounds from the source data
  with directed rounding; it does not trust anything the fast router says.
- These are **existence upper bounds, not confidence scores**. The three exact
  status sets are not topologically separated: at a compatible rank-deficient
  point all three distances vanish simultaneously. `argmin η` is a diagnostic,
  not a classification rule.

## Where it is fast, and where it is not

Single-threaded BLAS. The baseline differs by shape and must: square systems
compare against `dgesv`, everything else against `dgelsy` — comparing a square
system against a least-squares driver measures the cost of column pivoting
rather than anything about this method.

| Shape | Measured | Baseline |
|---|---|---|
| Overdetermined `m ≫ n` | **20–80× faster**, reproduced from 8000×32 up to 20000×2000 | `dgelsy` |
| Square | **parity**, 1.03–1.06× at n = 256…2000 | `dgesv` |
| Underdetermined `m < n`, moderate aspect | **0.35–0.62×** (slower) | `dgelsy` |
| Underdetermined, `n/m` in the tens or hundreds | **0.02–0.09×** (far slower) | `dgelsy` |

Two of these correct earlier figures, in both directions. The square case was
previously stated as 0.6–0.9× and measures at parity: the method was
understated there. The extreme underdetermined case was covered by a stated
0.24–0.43× that was measured at moderate aspect only; at `n/m` of 44 and 420
the penalty is an order beyond that, and `LPnetlib/lp_fit2d` at 25×10524 runs
at 0.02×. A regression on "overdetermined with heavily grouped rows"
previously reported as 0.56× has not been reproduced — the generator here
comes out faster, not slower — and is recorded as open rather than restated.

Every number above comes from a harness in `experiments/`, and the two
findings documents say what each one does and does not support:
[`docs/benchmark-findings.md`](docs/benchmark-findings.md) and
[`docs/suitesparse-findings.md`](docs/suitesparse-findings.md).
`experiments/synthetic_bench.py` exits nonzero when a claim stops
reproducing, so this table can be checked rather than trusted.

The speed argument applies to overdetermined equality classification only. On
square and underdetermined shapes the argument is the classification output
and rank interval, not wall time. `well1033` from the SuiteSparse collection
is kept in the test set as a deliberate negative performance control.

This is a **dense** solver. Sparse problems need a different implementation.

## Build

Requires a C11 compiler, OpenMP, and Python with SciPy (the build links
against the OpenBLAS shipped inside the SciPy wheel).

```bash
pip install -r requirements.txt
./build.sh
```

Produces `libaffine_bundle_solver.so` (fast router),
`libstatus_verifier.so` and `libcertified_solver.so` (strict proof kernels).

`build.sh` runs two probes and **fails the build** if either fails:

- `rounding_probe` — upward and downward rounding are distinguishable
- `mxcsr_probe` — loading the `-ffast-math` router does not set FTZ/DAZ
  process-wide

The second one matters more than it looks. The fast router is compiled with
`-ffast-math` and the proof kernels with `-frounding-math -fno-fast-math`, but
separate compilation is *necessary and not sufficient*: FTZ/DAZ are runtime
MXCSR state, and on some toolchains a `-ffast-math` link sets them for the
whole process at load time. That would silently flush the subnormals the
certificate battery is built to exercise, and those checks would pass
vacuously.

### Portable build

```bash
ARCH_FLAGS='' ./build.sh
```

The default is `-march=native`, which fixes the instruction set to the build
machine and enables FMA contraction. CI verifies that portable and native
builds agree on classification, rank, and rank interval.

## Test

```bash
# fast regression suite
for t in test_certified_api test_verifier_adversarial \
         test_status_profile_semantics test_meta_api_absent_solution_quality \
         test_threshold_contract test_streaming_equivalence \
         test_public_diagnostics test_core_rank_boundary \
         test_blockprefix_guard test_route_agreement; do
  python3 tests/$t.py
done

# property batteries
python3 tests/pbt_equivalence_orbits.py         # 8,335 checks
python3 tests/pbt_certificate_equivariance.py   # 2,271 checks

# do the paper's numbers still come out of this build?
python3 tests/check_paper_claims.py
```

`check_paper_claims.py` is the one to run after any change. Ordinary tests
answer "did anything crash"; this one fails when a number printed in
`paper.tex` no longer reproduces, even if every test passes. A silently
changed count invalidates a sentence in the manuscript.

## Repository layout

```
src/bsolver.c, bsolver_core.c   fast affine-bundle router
src/formation_guard.c/.h        a-posteriori formation-provenance checker
src/status_certificate.c/.h     independent proof-object checker
src/certified_api.c/.h          audit API
src/rounding_probe.c            build-time directed-rounding check
src/mxcsr_probe.c               build-time FP-mode leak check
include/affine_bundle/          public headers: router, stream, certificates
docs/api.md                     how to call it, without reading the paper
tests/                          regression suites and property batteries
experiments/                    manuscript table reruns
results/                        JSON records behind every manuscript table
paper.tex, references.bib       manuscript source
```

## Scope of the claims

Deliberately narrow, and worth reading before citing:

- The contribution claimed is the **composition**: a canonical affine-bundle
  equality classifier with compact proof objects for all three exact
  solution classes, plus a route-independent verifier. No novelty is claimed
  for LU/QR/SVD kernels, interval arithmetic, sketching, backward-error
  formulas, or the generator/checker pattern individually.
- Property-based testing falsifies many classes of implementation error. It
  does not replace a proof.
- The executable checker is a strict-C research prototype. The soundness
  theorem assumes valid outward arithmetic bounds; GCC does not implement
  `#pragma STDC FENV_ACCESS`, so the contract rests on `-frounding-math`.
  Compiler-independent closure would need validated interval arithmetic,
  MPFR-style directed arithmetic, or a formally verified checker.
- Performance claims are restricted to the tested dense regimes.

## Status

Research prototype, pre-publication. The manuscript is under preparation for
deposit. Issues and independent reproduction attempts are welcome — in
particular, reports of the build failing either probe on a toolchain we have
not tested.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

You may use, modify, and redistribute this code, including commercially,
provided you retain the notices and state significant changes. The licence
also grants an explicit patent licence from contributors, and terminates
that grant for anyone who initiates patent litigation over the work — which
is the reason for choosing it over MIT here.

The manuscript text and figures are not covered by this licence; see the
preprint deposit for their terms.

## Citation

See [CITATION.cff](CITATION.cff).
