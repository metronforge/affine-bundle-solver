# Isolated portability fix: fast-math non-finite validation

This is a compiler-specific validation bug, not a numerical-policy change.

At source `46babd62f645b7f1d455be4a2c68b1200a9f4576`, macOS ARM64 Apple
Clang 17.0.0 failed the unchanged `test_public_diagnostics` non-finite input
checks and the `test_operational_policy` custom-quality overflow check. Linux
x86_64 and ARM64 GCC/Clang passed them.

The router already avoided `isfinite`, because `-ffast-math` implies
`-ffinite-math-only`. However, Apple Clang also recognized its nonvolatile
`memcpy`/integer exponent-bit check as a finiteness test and folded it to false.
The retained standalone reproducer is `tests/diagnose_nonfinite.c`. Compile its
object with `-O3 -ffast-math`, then link without fast math, and pass a hexadecimal
binary64 bit pattern. Actual [Actions run 36621966466](https://github.com/metronforge/affine-bundle-solver/actions/runs/36621966466)
printed:

```text
bits=7ff0000000000000 by_value=0 by_pointer=1 volatile_bits=1 sizeof(long double)=8
bits=7ff8000000000000 by_value=0 by_pointer=1 volatile_bits=1 sizeof(long double)=8
bits=3ff0000000000000 by_value=0 by_pointer=0 volatile_bits=0 sizeof(long double)=8
```

The first two inputs are +infinity and a quiet NaN. Both must be rejected.
The third is 1.0 and must remain accepted.

Commit `48664e3` makes the existing private `finite_bits` helper observe the
representation through a volatile integer and routes `bs_nonfinite` through
that helper. It does not change any arithmetic expression, threshold,
classification/rank policy, certificate, public header or layout. This also
protects the helper's existing overflow/workspace uses. It restores the
documented input/overflow behavior on the affected compiler. No performance
claim is made for the added integer observation.

`test_nonfinite_boundary` adds NaN, +infinity and -infinity cases in matrix,
RHS and streaming inputs, followed by a valid streaming retry. The unchanged
public-diagnostics and operational-policy regressions remain required on all
platforms. Full baseline and platform results are recorded in `phase1-report.md`.
