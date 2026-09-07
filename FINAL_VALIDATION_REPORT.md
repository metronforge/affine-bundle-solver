# Final Validation Report

## Scope

The term *pre-submission audit* in this report refers to internal reproducibility, adversarial-testing, and mathematical checks performed during development. It does not denote completed external peer review.

This release combines the source-provenance rank certificate with the strengthened nearby-status certificate generator and strict verifier, then incorporates the pre-submission audit findings.  The numerical routing logic is unchanged; one meta-API export rule is tightened so a semantically absent solution-quality field cannot appear as a huge finite number:

1. the rank-transition discussion now states explicitly that the repaired `UNDECIDABLE [255,256]` state removes an earlier false deterministic `INFINITE/255` rank claim for a matrix whose exact rank is 256 for every nonzero perturbation;
2. the `well1033` real-matrix control is restored with bundled, checksummed MatrixMarket data plus acquisition and rerun scripts;
3. the 154 affine-translation diagnostics are no longer an unquantified caveat: the contradiction-policy threshold is derived per source row and reproduced by a controlled dyadic-translation gate;
4. for `INCONSISTENT` and `UNDECIDABLE`, the meta API now exports `NaN` in the solution/reference-solution error field (`out[6]`), because no solution witness exists.  The inconsistency residual diagnostic in `out[5]` is retained.

Relative to the preceding pre-submission release, every C/header file is byte-identical except `src/bsolver.c`.  Its only change is the final meta-API export mask for `out[6]`; the routing, rank, certificate, and numerical kernels are unchanged.

## Property-based validation

### Equivalence-orbit battery

- Total checks: **8,335**
- Hard failures: **0**
- Generator-quality diagnostics: **0**
- Extreme-range availability diagnostics: **0**
- Known affine-translation representation diagnostics: **154**

The 154 retained diagnostics are explicitly separated from hard failures and concern the declared representation-scaled contradiction policy under large affine coordinate translations. They are now quantitatively characterized rather than merely labeled:

- no stored affine-translation diagnostic at `2^20`;
- 34 first appear at `2^30` across the relevant stored orbits;
- the dedicated inconsistent sweep records 40/40 at each of `2^40`, `2^50`, and `2^60`.

For a normalized row, the implementation tests

`|rho| > tc * (1 + |beta| + ||x||)`.

Under `x=y+c`, `beta'=beta-a_hat^T c`, the exact residual `rho` is invariant while the threshold grows with the coordinate representation. Along `c=2^e c0`, the manuscript derives two explicit asymmetric bounds.  The sufficient-preservation scale is `(|rho|/tc-B0)/K`; the guaranteed-loss scale is `(|rho|/tc-1+|beta|+||x||)/K`, obtained separately from reverse-triangle inequalities rather than by a sign-symmetric `+B0` substitution.  In the controlled `3x2` exact-inconsistent example, the analytic bracket is

- sufficient-preservation log2 bound: **30.21928094817703**;
- guaranteed-gate-loss log2 bound: **30.219280948754108**.

The router returns `INCONSISTENT` at `e=30` and `UNDECIDABLE` at `e=31`, matching the derived bracket.

### Certificate-equivalence/extreme-range battery

- Total checks: **2,271**
- Failures: **0**
- Maximum inconsistent certificate radius observed: **3.8706114675943495e-15**
- Median inconsistent certificate radius: **9.417587441149346e-17**
- Minimum strict/high-precision shadow ratio: **1.0000000000000002**

Coverage includes independent signed dyadic row scalings through `2^(+/-1000)`, compatible/near-compatible tall systems through `2^(+/-500)`, deep-subnormal global scales through `2^1020`, and high-precision shadow evaluation of the strict radius.

## Router and structural validation

- Structural exact-construction gate: **132/132**, 0 hard failures.
- Large-n blockprefix gate: **1,000/1,000**, 0 hard failures.
- Blockprefix formation escalations: **0** in the reported 1,000-case stress.
- Blockprefix source-QRCP calls: **0** in that stress.
- Certificate API regression: PASS.
- Adversarial verifier regression: PASS.
- Primary/mirror status semantics: PASS.

The full PBT telemetry records 3,780 formation-guard checks, 201 formation escalations, and 365 source-QRCP calls across the complete property workload.

## Rank-boundary behavior

For the 256-dimensional transition construction, the exact rank is 256 for every nonzero weak-direction parameter. The current router returns 20/20 `UNIQUE [256,256]` at each of `1e-8`, `3e-9`, and `1e-9`. Beginning at `3e-10`, 20/20 runs return `UNDECIDABLE [255,256]` rather than promoting unresolved evidence to an exact rank claim.

This is a soundness improvement, not just a conservative policy change. An earlier implementation returned `INFINITE/255` at the smallest tested nonzero perturbations, which was a false point assertion about the exact rank. The repaired interval preserves the source-certified lower bound 255 without asserting the unproved upper endpoint.

## Restored real-matrix control

The release includes `data/well1033.mtx` and `data/well1033_rhs1.mtx`, together with `experiments/acquire_well1033.py` and `experiments/rerun_well1033.py`.

Bundled SHA-256 values:

- `well1033.mtx`: `9953cb6091a268afb6725bd92c26cdea68c8897b2d9a31a0656b0c0022e25f0c`
- `well1033_rhs1.mtx`: `2a9e1c688987c63facdd646cdc8441c447ea5d708de38c8ccdec9fcb91007e31`

The matrix is `1033 x 320` with 4,732 nonzeros and the packaged dense condition estimate is approximately **166.13334**.

Across five constructed compatible right-hand sides `b=A x_*`:

- all five router results are deterministic `UNIQUE`, rank 320, interval `[320,320]`;
- relative residual range: **1.0597e-15 -- 1.1662e-15**;
- `eta_x` range: **2.2865e-16 -- 2.8465e-16**;
- recorded median router time: **121.23 ms**;
- recorded median one-thread DGELSY time: **24.52 ms**.

Thus `well1033` is deliberately a performance negative control while the solution-quality defect that it exposed in an earlier implementation is absent. For the published noisy RHS the router reports incompatibility for the exact-equality task, while DGELSY returns a least-squares fit with relative residual approximately **8.61e-2**; those timings are not task-equivalent.

## Numerical experiment environment

The main quantitative run recorded:

- CPU: Intel Xeon Platinum 8370C @ 2.80 GHz
- L3 cache: 48 MiB
- Python: 3.13.5
- NumPy: 2.3.5
- SciPy: 1.17.0
- OpenBLAS: 0.3.30
- Fast-router OpenMP threads: 4
- BLAS threads: 1

The standard nine-case gate matches the sequential affine-bundle reference in class/rank semantics. The manuscript treats latency ratios as task-specific algorithmic controls, not universal dense-linear-algebra speed claims.

The refreshed 4-thread evidence-layer scaling measurement is approximately **1.57x geometric mean** versus one thread in the recorded run.

## Contextual DGELSY comparison

The six-case contextual DGELSY comparison has a geometric-mean router/DGELSY latency ratio of approximately **69.48x** on the recorded equality-classification tasks. This is explicitly limited to those workloads; DGELSY solves a broader least-squares problem. The restored `well1033` result is separately reported as a negative control where dense DGELSY is faster.

## Applications

All regenerated application families pass their construction-based semantic oracles:

- radio incidence/gauge/reference/disconnected/contradiction systems;
- irregular real spherical-harmonic systems, including exact equatorial rank collapse;
- SIS-like bilinear+PSF semilinear lens matrices.

No semantic failure occurred. Compatible solution residuals remain at approximately machine precision (typically order `1e-15`).

## Certified-audit cost

The previous and strengthened certified checkers were both rebuilt on the same current environment. Across six matched cases, the strengthened all-status audit costs **1.15x-2.19x**, with geometric-mean factor **1.5288x** and median factor **1.4615x**. The numerical fast-routing logic is unchanged; the follow-up `out[6]` mask is an export-only API semantic change, so this overhead still belongs only to optional certificate generation/verification.

## Manuscript validation

- Final PDF: **31 pages**.
- LaTeX build: clean; no undefined references/citations and no overfull/underfull box warnings in the final pass.
- PDF rendered page-by-page after the pre-submission revision.
- New proposition/proof pages, rank-transition discussion, affine-translation robustness text, restored `well1033` section/table, limitations, and bibliography were visually checked for clipping and layout defects.
- No working/internal revision labels are used in manuscript-facing text.

The manuscript does not reuse unverifiable real-matrix timing values: the restored `well1033` table is regenerated by the packaged implementation. Main numerical tables and figures remain those generated from the integrated implementation.  The follow-up C change affects only whether a non-applicable `out[6]` value is exported for statuses without a solution witness; it does not alter those numerical results.

## Clean-release smoke test

Before packaging, the pre-submission candidate tree was copied to a fresh directory without shared libraries or TeX intermediate files and rebuilt there.

- C build and directed-rounding probe: **PASS**.
- LaTeX/bibliography build: **PASS**, 31-page PDF.
- Quick equivalence PBT: **1,939 checks**, 0 hard failures, 35 known affine-translation policy diagnostics.
- Quick certificate-equivalence PBT: **378 checks**, 0 failures.
- Certified API regression: **PASS**.
- Adversarial verifier regression: **PASS**.
- Primary/mirror status semantics: **PASS**.
- Controlled affine-translation gate: analytic bracket `30.21928094817703--30.219280948754108`; observed `INCONSISTENT` through `e=30` and `UNDECIDABLE` from `e=31` in the tested range.
- Meta-API absence regression: `INCONSISTENT` keeps a finite residual diagnostic but exports `NaN` for `out[6]` and `out[10]`: **PASS**.
- Bundled `well1033` SHA-256 verification: **PASS** for both matrix and RHS.
- Fresh-copy `well1033` rerun: 5/5 constructed compatible RHS cases return deterministic `UNIQUE`, rank 320; residual and `eta_x` ranges reproduce the stored numerical-quality values. Timing varies with the host/run and is not used as an archive-integrity assertion.

The final ZIP is additionally checked with `unzip -t`, per-file `sha256sum -c`, and a second extraction after `SHA256SUMS.txt` is regenerated.

## Follow-up audit validation

After the final meta-API absence fix and explicit two-bound notation:

- full equivalence-orbit PBT: **8,335 checks**, **0 hard failures**, 154 known affine-translation representation diagnostics;
- full certificate-equivalence/extreme-range PBT: **2,271 checks**, **0 failures**;
- targeted incompatible meta-API regression: **PASS** (`out[5]` finite diagnostic, `out[6]=NaN`, `out[10]=NaN`);
- `well1033` published-RHS JSON export: `status=INCOMPATIBLE`, finite residual diagnostic, `rx=null`, `eta_x=null`;
- affine threshold formulas stored explicitly as `(|rho|/tc-B0)/K` and `(|rho|/tc-1+|beta|+||x||_2)/K`, reproducing log2 bounds `30.21928094817703` and `30.219280948754108`;
- final LaTeX log: clean; visually checked pages 5-6 show the API absence semantics and asymmetric threshold formulas without clipping or overflow.
