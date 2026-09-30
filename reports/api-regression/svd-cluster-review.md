# Repeated-singular-subspace review

Scope: frozen abs-apps `ae9b662d7f5755418aa80f31ade1fffcbefebafd`
T8-030/031/032 inputs, bound to A/b SHA-256 by the fixture manifest.
The prior behavior baseline was solver source `49ec7e3`.
The projector source fix is `1933be70ff5105d7b211af97297967b3457a701c`.

## Failure and mathematical premise

CI run 36724899844 reported T8-030 eta_infinite 0.0023350514905808558
instead of 0.0023273682262441543 in GCC and Clang portable jobs.
Run 36734681565 then reported T8-031 3.560395566857552e-05 instead of
3.653795636191648e-05 in GCC native (2.5562478% relative difference).
The 0.5% field tolerance in commit 356112b was inadequate. Increasing it to
3% was investigated and abandoned. These observations alone do not identify
a particular BLAS CPU kernel as the cause.

All three stored matrices satisfy the exact binary64 block identities
`A = [[X, -Y], [Y, X]]`. Over the exact rationals represented by those values,
`A J_n = J_m A`, hence `A^T A` commutes with `J_n`, where
`J = [[0, -I], [I, 0]]`. For a real eigenvector v, Jv is an eigenvector
for the same eigenvalue; v and Jv are orthogonal and J squared is -I.
Every real eigenspace therefore has even dimension. This is an algebraic
proof of paired multiplicity, not an inference from rounded singular values.

Eckart and Young, *The Approximation of One Matrix by Another of Lower Rank*,
Psychometrika 1 (1936), 211–218, [doi:10.1007/BF02288367](https://doi.org/10.1007/BF02288367),
provides the normwise low-rank reference. [LAPACK DGESDD](https://www.netlib.org/lapack/explore-html/df/d22/group__gesdd_ga8941e5ff50de36580dae8940015e9cb0.html)
computes an SVD via divide and conquer. A basis in a repeated subspace is
not unique: selecting its last vector does not fix a rowwise radius.

## Independent reference and result

`python tests/api_regression_svd_reference.py` recomputes the eigensystem of
the exact-input Gram matrix in mpmath at 80 and 120 decimal digits, independent
of LAPACK. Forming the Gram matrix squares the condition number; the high
precision and precision refinement are deliberate. This is a high-precision
reference, not an interval enclosure of eigenvalues. The bottom pair is
isolated from the next pair in these three processed matrices.

| case | smallest singular value of A | next cluster | old baseline radius | projector reference radius |
|---|---:|---:|---:|---:|
| T8-030 | 0.0003042265882519859541 | 0.0003347641518506611862 | 0.0023273682262441543 | 0.0023851515541451746 |
| T8-031 | 0.0003055975629247985521 | 0.0003394950030386720547 | 0.00003653795636191648 | 0.000032584933146147785 |
| T8-032 | 0.0003068416118363787398 | 0.0003444428334376285636 | 0.00003584719872213168 | 0.000032427967532549706 |

Both precisions agree on 45 displayed significant digits of each spectral
value and projector reference radius. The source generator and strict checker
are tested against the reference with absolute radius tolerance 1e-12;
the standalone DGESVD vector is checked with absolute coordinate tolerance
2e-10. These are numerical checks, not proofs about every platform.

The generator groups the smallest singular values using
`64 * epsilon * max(m,n) * sigma_max`, including implicit zeros for wide
matrices. This is a conservative backward-error-scale heuristic; it is not
a validated error bound for LAPACK and is not used as a public rank verdict.
For a multiple cluster it projects the first coordinate with projector
diagonal at least half the maximum. The projector removes basis rotations
in exact arithmetic; the half-maximum rule avoids a poorly conditioned tiny
projection and near-ties in selecting a maximum. Cluster/coordinate threshold
boundaries remain possible sources of proposal changes. This rule promises
neither global rowwise optimality nor bitwise identity on arbitrary inputs.

For these three matrices the chosen coordinate is zero-based index 5.
T8-030's radius increases by about 2.48%; the other two decrease. This is an
explicit quality tradeoff, not an optimization claim. For T8-031, b=0 and
the exact-source oracle proves UNIQUE with ranks 32/32. Its exact rowwise
distance to INFINITE equals min_{||z||=1} max_i |a_i^T z|/||a_i||:
any rank-losing perturbation has at least those row norms, and rowwise
orthogonal corrections attain them while keeping b=0. Normwise SVD does
not solve this minimax problem. A preliminary 2D angular search gave a
smaller candidate near 2.60017e-5; it is not a certified global optimum.

## Acceptance and coverage boundaries

The strict verifier is unchanged. The source generator fix is shared by
DGESVD and DGESDD, with no case-ID special casing. Tests exercise 17 rotated
bases of a known repeated subspace, a separated minimum, implicit wide null
directions, and a zero spectrum. The high-precision test asserts exactly the
three processed IDs. All 36 API cases retain the original float tolerance
1e-10 relative / 1e-12 absolute; changed radii are explicitly reviewed and
updated only for T8-030/031/032. Exact-source oracles and input hashes remain
unchanged. Thread tests compare the 36 cases at 1, 2 and 4 threads, and check
T8-038's operational UNIQUE/rank 132, mask 7, accepted inconsistent witness
and radius 0.9999999890199766 separately.

MC/DC remains exactly three demonstrated pairs and twelve uncovered atoms.
This numerical review adds no MC/DC coverage claim.

## T8-038 premise (separate from the SVD cluster fix)

The earlier source change `49ec7e3` uses a coordinate witness mapped back
from normalized rows when the estimated rank is full row rank. For a
nonzero source right-hand-side coordinate, this gives nonzero `y^T b`.
The checker forms the one-row correction `a_k' = a_k - (A^T y)^T/y_k`;
then `y^T A' = 0`, while an interval excluding zero for `y^T b` proves
the *corrected* system inconsistent. No left-null vector of the original
full-rank matrix is asserted. The strict checker remains authoritative
even if the generator rank estimate is wrong. T8-038's independent exact
source is UNIQUE; accepting this nearby-INCONSISTENT certificate does not
contradict it. The thread test checks acceptance and radius at 1/2/4 threads.

## Local verification before PR CI

Source `1933be70ff5105d7b211af97297967b3457a701c`, with the explicitly
reviewed baseline update and common tolerances restored:

- `python -m unittest tests/test_api_regression_corpus.py tests/test_api_regression_runner.py tests/test_api_regression_oracle.py tests/test_api_regression_decisions.py tests/test_api_regression_svd_reference.py tests/test_certificate_thread_determinism.py -v`: 32/32 passed, including positive/negative child diagnostics and 1/2/4-thread checks.
- `python tests/api_regression_runner.py --expect-count 36 --expect-ids-from manifest`: all 36 IDs completed.
- The same command with `--inject-wrong-expected T8-001:operational_status` returned 1 with `T8-001:operational_status: controlled expectation mismatch`.
- `ctest --test-dir /tmp/abs-cluster-build --output-on-failure`: 48/48 passed in 45.80 s, with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ABS_CERT_UNIQUE_THREADS=1`.
- `python tests/api_regression_qualification.py --expect-unique-cases 36 --output reports/api-regression/qualification.json`: 180/180 invocations, 36 unique cases, zero skips; 0.677255 s, peak RSS 62576 KiB. See the JSON for binary hashes and environment. These are host-specific resource measurements.
- `bash build_paper.sh`: successful 28-page manuscript; changed pages 10/11 visually inspected, no unresolved citations or overfull-box warnings in the final log.

Hosted cross-toolchain results must be checked separately on the new PR HEAD;
these local results do not stand in for GCC/Clang portable or GCC native CI.

PR-head `2335b4d74add84c7dd378de503dd9acfe1eccda9`, hosted run
[36740738316](https://github.com/metronforge/affine-bundle-solver/actions/runs/36740738316),
passed both API regression steps in GCC portable, GCC native and Clang
portable, including the independent reference and controlled negative.
All three jobs subsequently failed `Synthetic benchmark contract` because
the manuscript hash registry still named the pre-edit `paper.tex` hash.
The follow-up changes only that SHA-256 binding: benchmark claims,
artifact hashes, source provenance and assertions remain unchanged.
Locally the 52 contract tests and full `--audit-performance-artifacts .
--require-publication-ready` check then passed. A new full PR run is still
required; the preceding run is not reported as successful CI.
