# Affine-Bundle Solver

A dense solver for general real linear equality systems `Ax = b` that does not
assume consistency, full rank, or uniqueness. It reports operational classifications
under a numerical policy and independently verifies nearby-system certificates.

Most solvers answer "here is a solution". This one answers a different
question first: *is the system uniquely solvable, underdetermined,
inconsistent, or too close to a rank transition to say?* The classification
comes with separately interpreted nearby proof objects. Exact status of the stored
source requires independent evidence and remains UNKNOWN in ordinary solver calls.

[![build-and-test](https://github.com/metronforge/affine-bundle-solver/actions/workflows/ci.yml/badge.svg)](https://github.com/metronforge/affine-bundle-solver/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22753772-blue.svg)](https://doi.org/10.5281/zenodo.22753772)

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

Operational outputs under the selected policy (legacy APIs use DEFAULT):

| Status | Meaning |
|---|---|
| `UNIQUE` | full-column-rank compatibility under the policy |
| `INFINITE` | rank-deficient compatibility under the policy |
| `INCONSISTENT` | incompatibility under the policy |
| `UNDECIDABLE` | data too close to a rank transition to decide; a **rank interval** `[r₋, r₊]` is returned instead of a point rank |
| `FAIL` | resource failure (e.g. allocation); makes no claim about the data |

`UNDECIDABLE` is the point of the design. A row near the rank boundary is not
forced into a binary answer, and resource exhaustion is never converted into a
status verdict.

Field-by-field semantics, the three decision thresholds, and what each
guarantee does and does not cover are in [`docs/api.md`](docs/api.md), which
is written to be read without the manuscript.

The [versioned operational policy API](docs/operational-policy.md) exposes all four
sensitivity values and separates exact-source evidence from nearby certificates.

### Solve, check, certify

The public API separates three operations instead of selecting them with a
mode flag:

```text
simple solve:                  bsolve(...)
advanced solve configuration: bsolve_ex(..., BSSolveOptionsV1, ...)
candidate evaluation:         abs_check_candidate(...)
nearby-system certification:  bs_certify_candidate(...)
```

Operation choice is represented by the function called. Solve options
configure one solve operation; operational policy separately defines the
criteria used to interpret its numerical evidence. Most callers should use
`bsolve()` and its documented deterministic defaults.

Solving does not imply certification. Candidate checking accepts an arbitrary
finite caller-supplied `x` and never invokes the router or another solver, so
verification can be deferred until after `x` has been stored or transported.
`NOT_ESTABLISHED` means only that the configured quality bound was not
established; it is not rejection. Nearby-system evidence is likewise distinct
from the exact mathematical status of the original finite `A,b`.

See the [API guide](docs/api.md#2-solve-check-and-optionally-certify) for the
versioned result contracts and a complete three-phase C example. Existing
router and combined certified symbols remain supported.

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

The immutable package `results/synthetic-reference.*` contains 29 valid
row-level records from an Intel Core Ultra 9 185H laptop. OpenMP and BLAS were
limited to one thread; each case used one warmup and 11 timed repetitions.
Ratios below are baseline/router, so values above one mean lower router wall
time on that machine.

| Cases | Recorded baseline/router ratios | Baseline |
|---|---|---|
| Tall | 16.318, 32.148, 48.120, 32.838, 82.029 | DGELSY |
| Grouped rows | 12.677, 21.763, 17.182 | DGELSY |
| Square | 0.983, 0.993, 1.083 | DGESV |
| Underdetermined | 0.411, 0.656, 0.383 | DGELSY |
| Extreme 32×12800 | 1.206 | DGELSY |
| Grouped rows | 0.624, 1.603, 0.636 | LSMR |

DGELSY computes a general minimum-norm least-squares result and LSMR is an
iterative solution method; neither comparison establishes equivalent internal
work. The data show lower router wall time on the five tested tall inputs,
mixed square behavior, and higher router wall time on the three moderate or
large underdetermined inputs. They are machine-scoped observations, not
portable speed guarantees. The earlier `results/synthetic.csv` remains in the
repository as historical, non-current output and supplies no manuscript
number.

This is a **dense** solver. Sparse problems need a different implementation.

## Binary SDKs

For the three qualified platforms, see [binary SDK installation and external
dependencies](docs/binary-sdk.md). The next release after pipeline integration
will include Linux x86_64, Linux ARM64, and macOS ARM64 shared-library archives.

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
`-ffast-math` and the proof kernels with
`-frounding-math -fno-fast-math -ffp-contract=off`, but
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

# check direct property evidence and the immutable benchmark package
python3 tests/check_paper_claims.py
python3 tests/check_paper_claims.py --audit-performance-artifacts . \
  --require-publication-ready
```

`check_paper_claims.py` checks the direct property evidence and verifies that
the retained manuscript performance values agree with the immutable package.

## Repository layout

```
src/bsolver.c, bsolver_core.c   fast affine-bundle router
src/formation_guard.c/.h        a-posteriori formation-provenance checker
src/status_certificate.c/.h     independent proof-object checker
src/certified_api.c/.h          solve and audit APIs
src/candidate_check.c           caller-supplied candidate-quality checker
src/rounding_probe.c            build-time directed-rounding check
src/mxcsr_probe.c               build-time FP-mode leak check
include/affine_bundle/          public headers: solve, check, router, stream, certificates
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
  `#pragma STDC FENV_ACCESS`, so the contract rests on `-frounding-math`,
  together with `-ffp-contract=off`: rounding-mode awareness does not forbid
  fused multiply-add, which on FMA-capable targets would make the reported
  radii depend on the build target (soundness is unaffected, because every
  contractible site is an upward-rounded sum of non-negative terms).
  `tools/check_fp_contraction.sh` enforces this at build time.
  Compiler-independent closure would need validated interval arithmetic,
  MPFR-style directed arithmetic, or a formally verified checker.
- Performance claims are restricted to the named laptop, software stack,
  inputs, and single-thread protocol recorded by the immutable package.

## Status

Research prototype. Scientific v2 is prepared as software release candidate
`v0.5.0`; its version-specific Zenodo DOI will exist only after the Zenodo New
Version publication step. The prior `v0.4.4` archive remains available for
historical reproduction. Issues and independent reproduction attempts are
welcome — in particular, reports of the build failing either probe on a
toolchain we have not tested.

## Acknowledgments

This project was initiated by a suggestion from
[Ilya Scheblanov](https://www.linkedin.com/in/ilya-scheblanov-87023727) to
explore whether AI-assisted research could produce a new method for solving
general linear systems from first principles. The author is grateful for the
idea and encouragement that set this work in motion.

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

For the complete Affine Bundle Solver version history, use the
[Zenodo concept DOI 10.5281/zenodo.22753772](https://doi.org/10.5281/zenodo.22753772).
The v2 version-specific DOI is intentionally absent until Zenodo publishes the
new version. Machine-readable metadata are in [CITATION.cff](CITATION.cff).
