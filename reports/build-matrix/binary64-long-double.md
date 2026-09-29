# Isolated portability fix: witness normalization range

On Linux x86_64 and ARM64, `long double` has a wider exponent range than
binary64. On Apple ARM64, it has binary64 precision/range. The original
`row_norm` in `src/certified_api.c` assumed that accumulating squared binary64
values in `long double` prevented overflow and underflow.

The fully green pre-fix workflow at `99295ad5e8d7b3a35e6892fb9594cb527dcc8280`
still exposed six exploratory `range-robustness` findings in the unchanged
property battery. Under uniform binary scalings -1000, -800, -600, +600, +800,
+1000 of its fixed full-column-rank 4x2 fixture, macOS lost the UNIQUE witness
and returned accepted mask 6, whereas Linux retained mask 7. The existing
battery classified these as exploratory rather than hard failures, so its
`--strict` exit status alone did not capture the discrepancy. The raw evidence
is retained under `evidence/36622306536/`.

The platform assumption is visible directly: squaring a value of magnitude
2^600 overflows binary64, while squaring one of magnitude 2^-600 underflows.
Unique generation then rejects a zero row scale (code 5) or a singular packed
witness (code 6). This is an implementation-range problem, not a changed
mathematical rank or a threshold disagreement.

Commit `d940dee` preserves the existing calculation when the accumulated square
sum is normal. If the sum is nonfinite, saturated at `LDBL_MAX`, or below
`LDBL_MIN`, it scales inputs by
an exact power of two determined from the largest component, accumulates the
squares, takes the square root, and rescales. The largest scaled component is
in [0.5,1), so the accumulated sum is finite and normal for valid nonzero input.
Zero/nonfinite inputs retain zero/nonfinite outcomes. The normal-range Linux
path is unchanged.

The saturation guard was added after review: downward/toward-zero overflow
returns the largest finite number rather than infinity. `test_row_norm_range`
checks the actual private helper with exact powers from the smallest binary64
subnormal through 2^1023 under all four rounding modes, and checks preservation
of the caller's mode.

This **does change arithmetic on the previously broken range path**. It does
not change solver algorithms, classification/rank policy, certificate acceptance
thresholds, operational defaults, or public API/ABI. It restores the existing
range semantics on a platform without extended `long double` range.

The new required `test_certificate_extreme_scaling` uses the original property
fixture at those scales plus nine intermediate/partial-underflow controls.
The cross-platform snapshot now includes all 15 scales, comparing router rank,
classification and complete certificate outcomes, not merely successful loading.
Full before/after results and remaining findings are in `phase1-report.md`.
