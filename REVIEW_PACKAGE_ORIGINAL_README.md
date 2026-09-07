# Affine-Bundle Solver Reproducible Release

This package contains the manuscript, dense C research implementation, independent proof kernels, property-based tests, real-matrix data, and numerical experiment harnesses used for the August 2026 results.

**Procedural status.** The package has undergone an internal pre-submission reproducibility, adversarial-testing, and mathematical audit. This is not a claim of external peer review; the archive is prepared for such review.

## Numerical contract

The fast router treats sketches, compressed cores, QRCP, and SVD as proposal mechanisms. A compressed path may increase the deterministic source-rank lower bound only after an independent source-provenance certificate. Nearby-status proof objects are checked by a separate strict arithmetic verifier.

The inconsistent-certificate path is row-scaling equivariant in normalized augmented coordinates. The strict verifier evaluates left-null products in a common exponent frame, avoiding avoidable overflow/underflow without rescaling the stored witness.

For affine coordinate translations, exact compatibility residuals are invariant but the fast contradiction policy is intentionally representation-scaled. For a normalized source row, the gate is

`|rho| > tc * (1 + |beta| + ||x||)`.

Under `x = y + c`, `beta' = beta - a_hat^T c`, the residual `rho` is unchanged while the right-hand side can grow. The manuscript derives explicit, asymmetric sufficient-preservation and guaranteed-loss bounds along dyadic rays.  The upper/loss formula comes from a separate reverse-triangle inequality and is written explicitly rather than inferred by sign symmetry. The controlled `3x2` gate predicts the transition at `log2(scale)=30.21928...` and observes `INCONSISTENT` at `2^30` versus `UNDECIDABLE` at `2^31`.

## Main validation results

- Equivalence/metamorphic PBT: 8,335 checks, 0 hard failures.
- Certificate-equivalence PBT: 2,271 checks, 0 failures.
- Large-n blockprefix gate: 1,000/1,000, 0 hard failures.
- Structural gate: 132/132 checks, 0 hard failures.
- The 31 former generator-quality and 6 former extreme-range availability diagnostics are eliminated.
- The remaining 154 diagnostics are explicitly classified affine-translation representation sensitivity and are quantitatively characterized by the declared contradiction-policy threshold: none occur at the stored `2^20` level, 34 first occur at `2^30`, and the dedicated inconsistent sweep records 40/40 at each of `2^40`, `2^50`, and `2^60`.
- Independent signed dyadic row scalings are exercised through `2^(+/-1000)`; compatible/near-compatible tall cases through `2^(+/-500)`; global verifier scaling extends from deep subnormal values through `2^1020`.
- High-precision shadow checking found no underestimated constructive inconsistency radius in the focused battery.
- The numerical-rank transition now removes an earlier false point claim: for every nonzero weak-direction parameter the exact test matrix has rank 256; unresolved small nonzero perturbations are returned as `UNDECIDABLE [255,256]` rather than `INFINITE/255`.

## Build

Requirements include GCC, Python, SciPy/OpenBLAS, NumPy, and a LaTeX installation with `pdflatex` and `bibtex8`.

```bash
./build.sh
./build_paper.sh
```

The fast numerical route is compiled separately from the proof kernels. `formation_guard.c` and the nearby-status checker use `-frounding-math -fno-fast-math`; `build.sh` also executes a directed-rounding probe.

## Core tests

```bash
python3 tests/pbt_equivalence_orbits.py --mode full --strict \
  --output results/pbt_integrated_8335.json

python3 tests/pbt_certificate_equivariance.py --mode full \
  --output results/pbt_certificate_equivariance_2271.json

python3 tests/test_certified_api.py
python3 tests/test_verifier_adversarial.py
python3 tests/test_status_profile_semantics.py
python3 experiments/rerun_blockprefix_stress.py
python3 experiments/affine_translation_policy_gate.py
```

## Real-matrix control

The release restores `well1033`, a non-Hadamard real surveying least-squares matrix, as a numerical-structure and negative-performance control. Checksummed copies of the matrix and published RHS are bundled under `data/`.

To reacquire and verify the public artifacts:

```bash
python3 experiments/acquire_well1033.py
```

To rerun the current dense equality-classification control:

```bash
python3 experiments/rerun_well1033.py
```

On five constructed compatible right-hand sides, the packaged rerun returns `UNIQUE`, rank 320 in all five cases, with router residuals about `1.06e-15`--`1.17e-15` and `eta_x` about `2.29e-16`--`2.85e-16`. In the recorded environment the router is slower than one-thread DGELSY on this matrix, so this is intentionally a performance negative control. The published noisy RHS compares different tasks: exact equality classification versus least-squares fitting.

## Numerical experiments

For resource-constrained environments the numerical suite can be run section by section:

```bash
python3 experiments/rerun_numerical_suite.py --sections standard --out results/standard.json
python3 experiments/rerun_numerical_suite.py --sections rank --out results/rank.json
python3 experiments/rerun_numerical_suite.py --sections guard --out results/guard.json
python3 experiments/rerun_numerical_suite.py --sections scaling --out results/scaling.json
python3 experiments/rerun_numerical_suite.py --sections structural --out results/structural.json
python3 experiments/rerun_numerical_suite.py --sections lapack --out results/lapack.json
python3 experiments/rerun_applications.py
python3 experiments/rerun_well1033.py
python3 experiments/affine_translation_policy_gate.py
```

`results/numerical_final_suite.json` contains the consolidated synthetic/application data used in the manuscript; `results/well1033_reviewed.json` and `results/affine_translation_policy_gate.json` contain the two pre-submission-audit controls. DGELSY numbers are contextual task-specific comparisons, not a claim of general superiority over LAPACK.

## Performance layers

The certificate changes do not alter the fast-router source. On six matched cases rebuilt on the same current environment, the strengthened all-status certified audit costs 1.15x-2.19x the preceding certified audit implementation (geometric-mean factor 1.53). This cost belongs to optional proof-object generation/verification, not to the fast routing path.

## Package map

- `paper.tex`, `paper.pdf`, `references.bib`: manuscript and bibliography.
- `src/`: fast router, source-provenance guard, certificate generator, and strict verifier.
- `tests/`: equivalence PBT, certificate-equivalence PBT, telemetry, and adversarial/regression tests.
- `experiments/`: reproducible numerical, real-matrix, policy-threshold, and application harnesses.
- `data/`: checksummed `well1033` MatrixMarket matrix and published RHS.
- `results/`: final PBT, numerical, real-matrix, policy-threshold, application, and matched audit artifacts.
- `figures/`: figures included by the manuscript.
- `FINAL_VALIDATION_REPORT.md`: detailed release validation summary.
- `REVIEW_NOTES.md`: concise record of the changes arising from the pre-submission audit.

The implementation is a dense CPU research prototype. The strict proof kernels are independently checkable numerical code, not formal machine-checked proofs.


## Meta-API absence semantics

For `INCONSISTENT` and `UNDECIDABLE`, the router does not claim a solution witness.  Consequently the meta-API solution/reference-solution error field (`out[6]`, reported as `rx` by the audit harness) is `NaN`; JSON harnesses serialize it as `null`.  An inconsistency residual diagnostic may still be finite in `out[5]`.
