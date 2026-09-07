# Pre-submission Audit Follow-up

This revision addresses three points raised during a pre-submission reproducibility, adversarial-testing, and mathematical audit of the packaged release. These checks were internal to the development process and do not constitute external peer review.

## 1. Rank-transition wording

The manuscript now states the substantive fact directly: in the transition construction the exact rank is 256 for every nonzero perturbation. Therefore the previous `INFINITE/255` point verdict at the smallest nonzero levels was false. The current `UNDECIDABLE [255,256]` result is a soundness repair, not merely a more conservative choice of language.

No C source change was required for this audit item; the implementation had already been repaired and the manuscript wording is brought into line with the actual mathematical improvement.

## 2. `well1033` restored

The real non-Hadamard `well1033` control is restored because its matrix and published RHS remain available in the earlier reproducibility assets. The pre-submission release now makes this control self-contained by including:

- `data/well1033.mtx`;
- `data/well1033_rhs1.mtx`;
- `experiments/acquire_well1033.py` with byte-level SHA-256 verification;
- `experiments/rerun_well1033.py`;
- `results/well1033_reviewed.json`.

The current implementation returns machine-scale residuals and finite `eta_x` on five constructed compatible RHS cases, while remaining slower than one-thread DGELSY on this dense real-matrix control. This is intentionally retained as a negative performance control.

## 3. Affine-translation diagnostics quantified

The 154 representation-sensitive affine-translation diagnostics are no longer described only empirically. The manuscript derives the relevant fast-policy threshold.

For a normalized source row, the contradiction test is

`|rho| > tc (1 + |beta| + ||x||)`.

Under `x=y+c` and `beta'=beta-a_hat^T c`, the exact residual `rho` is invariant, but the threshold is not. Along a dyadic ray `c=2^e c0`, triangle and reverse-triangle bounds provide a sufficient interval in `e` for preservation and for guaranteed loss of contradiction evidence.

The controlled `3x2` gate gives a threshold bracket at `e=30.219280948...`; the implementation returns `INCONSISTENT` at `e=30` and `UNDECIDABLE` at `e=31`.

This mechanism is separate from the deterministic-unique `eta_x` quality acceptance rule.

## Validation status

The numerical solver core and all certificate kernels remain unchanged.  Relative to the preceding pre-submission release, only `src/bsolver.c` differs, and only in the final meta-API export mask for `out[6]`.  The full PBT remains 8,335 checks with 0 hard failures and the focused certificate battery remains 2,271 checks with 0 failures.


## Follow-up audit fixes

- The affine-translation proposition now names both logarithmic bounds explicitly: `e_keep = log2((|rho|/tc-B0)/K)` and `e_drop = log2((|rho|/tc-1+|beta|+||x||)/K)`.  The second comes from a separate reverse-triangle bound and is not the naive `(+B0)` counterpart of the first.
- The router meta API now exports `NaN` for `out[6]` whenever status is `INCONSISTENT` or `UNDECIDABLE`, because no solution witness exists.  The `well1033` JSON harness maps this to `null`; the residual diagnostic `out[5]` remains available for `INCONSISTENT`.
