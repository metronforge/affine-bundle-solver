# SIMD stage 1 baseline

## Identity and method

* Source: `/projects/affine-bundle-solver`, branch `perf/simd-stage1-baseline`.
* Frozen base: `bb53883e2faff0f424775a9ab558405d7bc6e1a1`.
* Compiler: GCC 15.2.0 (`gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0`).
* Router: `-O3 -march=native -fopenmp -ffast-math`; object inspection found
  256-bit `ymm` AVX2 instructions and FMA.
* BLAS: SciPy bundled OpenBLAS `libscipy_openblas-68440149.so`.

Normal CMake was compared with opt-in `-DABS_DISABLE_ROUTER_AUTOVECTORIZATION=ON`.
That adds `-fno-tree-vectorize -fno-tree-slp-vectorize` only to fast router
objects (including its test-only clone). It does not change BLAS or OpenMP,
and does not reach `formation_guard.c`, `status_certificate.c`,
`certified_api.c`, or probes. Those retain `-O2 -frounding-math -fno-fast-math
-ffp-contract=off`.

Raw artifacts: `/tmp/abs-simd-vec-report`, `/tmp/abs-simd-current{,.csv,.json}`,
`/tmp/abs-simd-scalar{,.csv,.json}`, and their matching build directories.

## Compiler audit

`tools/vectorization_report.sh /tmp/abs-simd-vec-report` compiled only
`src/bsolver.c` under normal fast-router flags. GCC reported 686 optimized
loop reports, 2,203 misses, and 21 possible strided-access reports.

| Kernel | Location | Vectorization evidence | Ownership / conclusion |
|---|---:|---|---|
| `compat_scan_fused` | `bsolver.c:258-268` | OpenMP outer regions: “vectorized 0 loops”; only setup SLP. | Solver C. The audit does not establish effective SIMD of `ax/an2` or `ax/amax` inner reductions; profile it first. |
| `project_cgs2`, `r < 96` | `bsolver.c:87-102` | Short scalar control flow; invoked `dot` has AVX2 reduction code. | Solver C. Fixed `r=96` crossover is not evidence for a workload-dependent change; retain it. |
| CGS2 `r >= 96` | `bsolver.c:100-102` | `DGEMV` twice per pass. | BLAS SIMD, not solver-owned. |
| Fused sketch `cr/e0/e1` | inlined `bsolver_core.c:180` | GCC reports 32-byte vectors; disassembly has broadcast, `vmovupd`, `vmaxpd`, and three `vfmadd213pd` updates. | Solver C. Already effectively auto-vectorized. |
| Serial sketch updates | inlined `bsolver_core.c:189-190` | Multiple 32-byte reports for contiguous updates; surrounding row/control loops missed. | Solver C. Body SIMD is present. |
| Tail/secant `ax/an2/az0/az1` | `bsolver.c:689,693` | Conditional/OpenMP-body control-flow misses; no direct proof of effective inner-loop SIMD. | Solver C. High-priority profile candidate. |
| Core normalization/copies | fast path | Contiguous copies/updates receive 32-byte reports. | Solver C; layout is already SIMD-friendly. |
| `pack_scaled_square_lapack` | `bsolver.c:809-843` | Scalar column/tile structure; parent diagnostics see calls, not a profitable loop. | Solver C feeding LAPACK. Primary demonstrated role is cache/layout conversion, not SIMD. |
| LU refinement residual | `bsolver.c:867` | Inner dot has AVX2 reduction sequences. | Solver C, but LU itself is BLAS/LAPACK. |
| QRCP/SVD/LU | several | `DGEQP3`, `DGESDD`, `DGETRF`, `DGETRS`, `DGECON`, `DGEMV`. | SIMD is internal to OpenBLAS; no replacement case is made. |

Disassembly confirms actual emitted vector instructions, not source inference. The
strict contraction gate passed and strict objects were not SIMD targets.

## End-to-end screening

The existing `experiments/synthetic_bench.py` was used with OpenMP and BLAS
threads fixed at one. Both builds used:

```text
python3 experiments/synthetic_bench.py --driver gelsy --no-large --scale 0.05 \
  --repeats 3 --seed 20260909
```

Times are medians in seconds; ratio is no-autovec/current. This retains square
and wide moderate/large-n routes but scales tall rows, so it is a screening,
not a publication throughput campaign.

| Case | m x n | current | no-autovec | ratio | route/status |
|---|---:|---:|---:|---:|---|
| tall | 400 x 32 | 0.000605 | 0.000117 | 0.19 | UNIQUE, rank 32 |
| grouped full scan | 6553 x 64 | 0.003579 | 0.003308 | 0.92 | UNIQUE, rank 64 |
| compressed/full scan | 819 x 256 | 0.023348 | 0.025233 | 1.08 | INFINITE, rank 205 |
| square/LU available | 256 x 256 | 0.002040 | 0.001734 | 0.85 | UNIQUE, rank 256 |
| square/LU available | 512 x 512 | 0.016793 | 0.010816 | 0.64 | UNIQUE, rank 512 |
| wide | 256 x 2048 | 0.380427 | 0.289271 | 0.76 | INFINITE, rank 256 |

The inconsistent directions are noise/routing/BLAS dominance and too few
repetitions, not evidence that disabling vectorization helps. No `perf stat`
claim is made.

## Correctness and recommendation

Both builds passed configure, rounding, link-contract, MXCSR, and strict
FMA-contraction gates; the focused control-option test passed. Screening rows
had identical status/rank across configurations. Scaled grouped 819x64 and
819x256 inputs fail their expected-UNIQUE oracle in both builds, a pre-existing
scale-sensitive harness limitation, not a vectorization difference.

Separate accounting is essential: solver-owned loops receive compiler SIMD;
DGEMV/QRCP/SVD/LU receive library-internal SIMD; OpenMP is thread-level and was
fixed at one thread here. Stage 2 should first collect route-attributed, CPU-
pinned longer measurements. Only the fused compatibility scan and four-dot
tail/secant scan are credible explicit-SIMD investigations. The multi-output
sketch update already has AVX2/FMA, and packing is primarily locality/layout.

Limitations: three repeats, no affinity/frequency lock, scaled tall systems,
no hardware counters, and compiler diagnostics that prove compilation rather
than hotness. No solver mathematics, thresholds, routing, certificates, API,
ABI, or strict compilation semantics changed.
