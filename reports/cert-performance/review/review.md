# Independent review of the inconsistent verifier

The review compares the verifier at `361f068d` with `392e4750` on Linux x86-64, using GCC 14.2 and CPU 3. No solve inputs, timing workloads, or reserved inputs enter this test.

## Arithmetic

For each active row, the maximum `frexp` exponent of the nonzero entries in the augmented row equals the exponent of its largest absolute entry. A row of entirely zero entries contributes nothing. Taking the maximum of these row contributions gives the original common exponent E, including the sentinel for an empty set. The sign interval uses the original directed arithmetic.

A nonzero eligible weight has magnitude at least 2⁻⁵⁰¹ and less than 2⁵⁰⁰ after scaling. Scaling into that range is exact, including when the input is subnormal. A nonzero eligible matrix coefficient has magnitude in [2⁻⁵⁰⁰, 2⁵⁰⁰]. The exact product magnitude therefore lies in [2⁻¹⁰⁰¹, 2¹⁰⁰⁰). Both the old mantissa product and the direct product round in the normal range. Shifting the radix point maps their adjacent binary64 rounding endpoints exactly, so downward and upward rounding yield the same framed products. For every column, the sequence of nonzero products and the addition order are unchanged. Signed-zero differences disappear when taking the absolute bound. This argument also covers a subnormal partial sum created by cancellation since both paths add the same rounded nonzero products.

The strict flags disable contraction, the pass sets its own rounding mode, and the compile-time guard requires binary64 with intermediate evaluation at the declared precision. Out-of-range rows and extended evaluation use the original column loop. The source finite checks include inactive rows, and the sign, norm, pivot-row denominator, and rounding-mode restoration code retain their baseline behavior.

## Independent numerical check

The script generates 1,468 fresh verifier inputs, including 1,300 seeded random cases and 168 boundary or invalid cases. Four standard caller modes give 5,872 baseline/final pairs per build configuration. It compares return codes, all bits of both sign endpoints and the radius, and the caller's rounding mode on return. Output sentinels also check early-rejection behavior.

For every emitted sign interval, Python's exact rational arithmetic computes the independently normalized dot product and checks containment. For every accepted radius it checks the squared inequality
`sum_j (sum_i y_i A_ij)^2 <= eta^2 y_k^2 (b_k^2 + sum_j A_kj^2)`.
This avoids rounding either norm. The suite includes tile widths around 64 and its multiples, positive and negative zero, excluded extrema in inactive rows, adjacent guard endpoints, overflow and underflow exponents, sign cancellation, and normal product cancellation to a subnormal residual.

Both the default build and the x87 extended-evaluation build passed all comparisons, including the exact checks on all 1,172 accepted radii in each. Among the 1,288 sign-accepted inputs, 657 meet the numeric fast-path guard and 631 require the fallback. The x87 build always takes the fallback. The measured interface is the single inconsistent verifier. The environment check covers rounding direction. These runs used GCC on one machine.

## Reproduction

From the repository root with independently built checkouts of the two revisions, set `base` and `final` to their absolute directories. The recorded results use `./build.sh` outputs in `/tmp/cert-base` and `/tmp/cert-final`. Both JSON files carry the SHA-256 digests of their input binaries.

```bash
base=/tmp/cert-base
final=/tmp/cert-final
review=reports/cert-performance/review
taskset -c 3 python3 "$review/check_inconsistent.py" \
  "$base/libstatus_verifier.so" "$final/libstatus_verifier.so"

temporary_build=$(mktemp -d)
for side in base final; do
  source_dir=${!side}
  taskset -c 3 gcc -mfpmath=387 -O2 -shared -fPIC -fopenmp -Iinclude \
    "$source_dir/src/status_certificate.c" -o "$temporary_build/$side.so" \
    -frounding-math -fno-fast-math -ffp-contract=off -lm
done
gcc -mfpmath=387 -dM -E -x c /dev/null | grep '^#define __FLT_EVAL_METHOD__ 2$'
taskset -c 3 python3 "$review/check_inconsistent.py" \
  "$temporary_build/base.so" "$temporary_build/final.so"
```
