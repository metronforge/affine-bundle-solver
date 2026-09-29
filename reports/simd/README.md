# SIMD investigation milestone

This milestone audited solver-owned fast-path kernels on the tested Intel Core
Ultra 9 185H / GCC 15.2 / AVX2 environment. It establishes the current baseline;
it does not make a hardware-portability claim or rule out future improvements
supported by new profiling evidence.

## Stage 1

Established the compiler/BLAS SIMD baseline and the router
no-autovectorization diagnostic control.

## Stage 2A: `compat_scan_fused()`

The actual outlined worker uses compiler-generated AVX2/FMA. Explicit SIMD was
not justified. Compiler-directed reassociation experiments could change boundary
decisions, so the production kernel was retained unchanged. See
[`stage2a-compat-scan.md`](stage2a-compat-scan.md) and its evidence archive.

## Stage 2B: tail/secant scan

All four reductions and both `e0`/`e1` updates use 256-bit SIMD/FMA. The
no-autovectorization control is materially slower, and the audit found no
hot-loop accumulator spills. Explicit SIMD was not justified; the production
kernel was retained unchanged. See
[`stage2b-tail-scan.md`](stage2b-tail-scan.md) and its evidence archive.

## Final decision

**SIMD milestone complete.** The audited solver-owned fast-path kernels already
receive effective compiler-generated SIMD, while BLAS/LAPACK provide their own
optimized SIMD. Strict proof kernels retain their separate floating-point
contract. No ISA-specific implementation is currently justified. Future SIMD
work requires new profiling evidence rather than continuation of this milestone
by default.
