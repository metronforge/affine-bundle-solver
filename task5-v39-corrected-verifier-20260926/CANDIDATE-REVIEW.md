# Exact corrected-candidate review

Reviewed range: `bb6c30d..40fe4d0`; correction range: `dd30ef9..40fe4d0`.

## Source and contract audit

- `unique_row_pass` keeps each column accumulator's additions in increasing
  `k`, initializes from positive zero, reads packed U row `k` at stride one,
  reads the L factor from packed row `lr`, and substitutes the exact unit
  diagonal. The private `noinline` boundary follows each explicit rounding-mode
  change. The build applies `-O2 -frounding-math -fno-fast-math
  -ffp-contract=off`; disassembly of the independent review library contained
  no fused multiply-add/subtract instruction.
- The selected source row is `idx[ks]`, the factor row is `perm[ks]`, and both
  arrays are validated. Square, tall, partial-row `130x129`, random, near
  consistent, wide-exponent, subnormal, signed-zero, and diagonal Task-5
  shapes are exercised by the row differential. Invalid zero-sized unique
  problems retain their documented validation failure.
- Every derived unique-verifier bound is checked before it can influence an
  accepting comparison: solution norm; both row endpoints and their absolute
  bound; row norm; residual; combined RHS perturbation; perturbation norm;
  source norm; and final quotient. A non-finite value sets `best` to positive
  infinity and cannot be overwritten, so NaN comparison behavior cannot fail
  open and `eta_up` cannot remain zero.
- Validation exits occur before the verifier changes the rounding mode.
  Allocation failure after the saved mode restores it. The normal/non-finite
  exit frees every owned allocation and restores the saved caller mode.
- The private test hook is compiled only into the dedicated test target. Public
  headers, data structures, exported declarations, certificate fields, and
  router sources are unchanged. Full rebuilt symbol/ABI comparison is reserved
  for the fresh correctness matrix.

## Independent overflow RED/GREEN

The same external dynamic-library test was compiled with strict flags and run
against newly compiled review libraries. It covers all four caller rounding
modes, positive reconstruction overflow, negative reconstruction overflow,
solution-norm overflow, positive-infinite `eta_up`, rounding restoration, and
an ordinary signed-zero identity case.

Against unchanged `dd30ef9`, it failed as required:

```text
positive-reconstruction-overflow mode=0 rc=0 eta=0x0p+0 after=0
negative-reconstruction-overflow mode=0 rc=0 eta=0x0p+0 after=0
solution-norm-overflow mode=0 rc=0 eta=0x0p+0 after=0
exit=1
```

Against exact `40fe4d0`, it passed:

```text
non-finite derived bounds fail closed and ordinary signed-zero case is stable: PASS
exit=0
```

Thus positive and negative derived infinities and solution-norm overflow return
code `7`, set `eta_up` to positive infinity, and restore every starting rounding
mode in the corrected candidate.

## Differential, signed zero, and allocation evidence

The exact candidate's focused row differential reported:

```text
unique verifier rows: 1968 calls, 31160 rows, 1502768 entries compared; 228 signed-zero-only endpoint differences; 0 failures
```

All selected rows reached the hook; no measurable reconstruction path was
silently skipped. Entrywise absolute error bounds were bit-identical to the
frozen reference. Endpoint differences were limited to the preregistered sign
of exact zero and were removed by `fabs` before radius formation.

An independent allocation shim failed each of the five allocations in turn.
The returned codes were `3,4,6,6,6`, caller rounding remained
`FE_TOWARDZERO`, `eta_up` stayed positive infinite, and the outstanding
allocation count returned to zero:

```text
unique verifier ENOMEM positions 1..5 restore fenv and leak no allocation: PASS
```

## Gate verdict

No Critical or Important candidate defect was found. The exact immutable
candidate passes the review gate. This is a source/behavior review, not a
performance qualification; all full builds and measurements remain fresh and
pending.
