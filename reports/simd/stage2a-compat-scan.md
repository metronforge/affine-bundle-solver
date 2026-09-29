# Stage 2A: compat_scan_fused SIMD evaluation

## Decision

**Stop optimization of this kernel for now. Retain the Stage 1 implementation.**
It already uses 256-bit SIMD in both inner reductions. Three compiler-directed
experiments did not deliver a consistent improvement while preserving decisions.
No intrinsics are justified by this evidence. The next investigation can audit
the tail/secant scan, starting with its actual inner-loop assembly.

This is a completed negative optimization experiment: no performance improvement
is claimed for the delivered solver. Its library is byte-identical to the Stage 1
production build. Experimental implementations remain reachable in Git history.

## Source and frozen execution identities

Repository: `/projects/affine-bundle-solver`.
Branch: `perf/simd-stage2a-compat-scan`.
Base/latest main at start: `e90e781bd91b486fc798baa981a2fa12e2ebfb62`.

| Configuration | Frozen source commit | Build directory |
|---|---|---|
| A, Stage 1 production + diagnostic adapter | `adea492446365950cd4b99486c9f3fe5fa2ed4bf` | `/tmp/abs-stage2a-baseline` |
| B, no auto-vectorization | same as A | `/tmp/abs-stage2a-control` |
| C, OpenMP SIMD reductions | `615b1073059ee4b38ea959fd7caf88435e54cd79` | `/tmp/abs-stage2a-simd` |
| D, four independent accumulation streams | `75062b6e13055025ce7580289b82f80c98ad12ca` | `/tmp/abs-stage2a-accum4` |
| E, GCC unroll-four hint | `cde14e13c2f4c7442183794735257e21cdb4d635` | `/tmp/abs-stage2a-unroll4` |
| Retained production and control | `7ed4c1a4c33269d57f10ce492af17f4d0abf10a2` | `/tmp/abs-stage2a-final`, `/tmp/abs-stage2a-final-control` |

Final implementation/tooling SHA before this documentation-only checkpoint:
`33ab77d4e28ac5b589988c4cfc812d5c3c3dac4b`. This adds untimed route telemetry to
the harness; the final measured solver source is `7ed4c1a`. The documentation
commit is identifiable with `git log -1 --format=%H -- reports/simd/stage2a-compat-scan.md`.

All builds began from clean commits; each `freeze.json` records repository,
branch, commit, tree, dirty status, complete compile commands, probe link command,
compiler/CPU identity, BLAS path/hash, strict-object hashes, and library hashes.
The source was not changed within any frozen build. Benchmark matrices and RHS
have per-case SHA-256 identities in the raw results. Harness revision for the
final 21-run comparison is `33ab77d`.

Production library SHA-256 (Stage 1, fresh A, and retained build all match):
`4381c68a4e30d7c37ca49edd4f77e8ef7e4169ce22bfc0c19a55608399a9fbe3`.

## Machine and build contract

Measured 2026-09-29 on Intel Core Ultra 9 185H, 22 logical CPUs, 24 MiB L3,
AVX2/FMA, no AVX-512. Primary measurements pinned to CPU 0; its SMT sibling is
CPU 5. Linux, GCC `15.2.0 (Ubuntu 15.2.0-16ubuntu1)`, CMake 4.2.3, Python 3.13.5,
NumPy 2.3.1, SciPy 1.16.1. CPU frequency governor was `powersave`; no frequency
lock or exclusive machine reservation was applied.

Solver BLAS is SciPy OpenBLAS 0.3.28, Haswell dispatch, pthreads,
`libscipy_openblas-68440149.so`. NumPy matrix generation uses MKL
2023.1-Product outside timers. Both remain at one thread, as does OpenMP:
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=BLIS_NUM_THREADS=1`.

Router compilation remains `-O3 -march=native -fopenmp -ffast-math -fPIC`.
B additionally uses the existing, opt-in CMake setting
`ABS_DISABLE_ROUTER_AUTOVECTORIZATION=ON`, applying
`-fno-tree-vectorize -fno-tree-slp-vectorize` only to router objects.
Scalar FMA and BLAS SIMD remain enabled in B.

Strict compilation retains `-O2 -frounding-math -fno-fast-math -ffp-contract=off`.
Formation guard, status verifier, and certified API object hashes are identical
across **all seven builds**. Their compile commands contain neither native/fast
flags nor no-vectorization flags. The final diff against main has no changes
under `src/`, `include/`, or `CMakeLists.txt`. The Stage 1 switch is retained.

## Correction to Stage 1 and compiler evidence

Stage 1 incorrectly treated the parent function's “vectorized 0 loops” report
as evidence that the inner scan reductions were unproven. The parent dispatches
OpenMP workers; their diagnostics explicitly report the inner loops:

```text
src/bsolver.c:262:90: optimized: loop vectorized using 32 byte vectors
src/bsolver.c:262:90: optimized: loop vectorized using 16 byte vectors
src/bsolver.c:265:91: optimized: loop vectorized using 32 byte vectors
src/bsolver.c:265:91: optimized: loop vectorized using 16 byte vectors
```

The outer row loop misses vectorization because of control flow; this does not
prevent SIMD within a row. A single-threaded OpenMP region still executes the
outlined worker containing these instructions. Function-specific disassembly
is retained for each configuration.

| Production inner loop | Main four-double iteration | Remainders / dependencies |
|---|---|---|
| `n >= 192`, `compat_scan_fused._omp_fn.0` | `vmovupd ymm`, two `vfmadd231pd ymm` chains for `ax` and `an2` | Horizontal XMM reductions, 128-bit/scalar tails; one dependent accumulator per reduction |
| `n < 192`, `compat_scan_fused._omp_fn.1` | `vmovupd ymm`, `vandpd`, `vmaxpd`, `vmulpd`, `vaddpd` | Main dot loop is not fused; 128-bit/scalar tails use FMA; dot and max each have a dependent chain |
| No-vector control | Scalar arithmetic, no YMM reduction instructions in either worker | BLAS unchanged; scalar FMA still allowed |

All accesses are unaligned loads, consistent with the public API. Neither
alignment assumptions nor new `restrict` contracts were introduced. The source
streams are read-only, so stronger alias promises offer no demonstrated benefit
for these reductions. Slow-path norms and the long-double residual accumulation
were preserved in every experiment.

Experiments, all restricted to the two inner loops:

* **C:** `omp simd reduction(+:ax,an2)` and
  `omp simd reduction(+:ax) reduction(max:amax)`. Main vector width and arithmetic
  remain substantially the same; reduction/tail handling changes rounding.
* **D:** four contiguous quarter-row streams, each with independent dot and
  norm/max accumulators, followed by combination and a remainder loop. More
  independent vector chains are emitted, but each worker grows from roughly
  241/267 disassembly lines to 579/613. Stream setup and extra horizontal
  reductions cost more on most shapes.
* **E:** `#pragma GCC unroll 4` on the original reductions. SIMD iterations are
  unrolled while preserving their accumulation chains on this compiler. Worker
  size grows to 273/309 lines. This is not consistently faster either.

There are dependency chains, but the measured attempts to relieve or amortize
them do not establish that they dominate normal end-to-end performance.

## Methodology

`experiments/compat_scan_probe.c` includes the real router translation unit,
exposing its private scan only in a diagnostic library. It links the unchanged,
separately compiled formation guard. Production libraries have no added API.
The build helper takes the actual router compile command from CMake, adds GCC
vectorization reporting, and records the resulting object and library identities.
The probe uses internal symbol binding; end-to-end timings use the ordinary
production shared library and `bsolve_router_meta_api`.

Matrices reuse `synthetic_bench.gen_tall`, with a known random anchor and RHS
computed outside the timer. The primary shapes span 32–100 MiB of matrix data,
including 188, 191, 192, 193, and 196 columns near the branch boundary. Smaller
4096-row cases assess cache effects. All variants use the same arrays and input
hashes within a case. Three warm-up calls per variant precede **21 measured
calls**, with deterministic randomized variant order on each round. No builds
or test suites run concurrently with the final timing campaign.

The isolated timer includes one complete scan, its OpenMP dispatch, norm/quality
logic, long-double aggregation, and a ctypes call. The solver timer includes the
full public router invocation, input validation, allocation, and BLAS work.
Raw timings, median, MAD, min/max, output vectors and observed decision sets are
retained. Routing counters and the raw `accepted_random` flag are collected by
additional calls **outside** the timing interval.

## Main measurements

Isolated scan median ± MAD in milliseconds. A is production; B is no-autovec;
C is OpenMP SIMD; D is four streams; E is unroll-four. MAD describes dispersion,
not a confidence interval.

| m × n | A | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| 131072 × 32 | 3.398 ± 0.462 | 5.095 ± 0.229 | 3.065 ± 0.240 | 4.579 ± 0.196 | 3.239 ± 0.286 |
| 131072 × 64 | 4.743 ± 0.093 | 11.520 ± 0.214 | 4.907 ± 0.173 | 10.071 ± 0.117 | 5.305 ± 0.117 |
| 65536 × 128 | 4.919 ± 0.222 | 12.038 ± 0.204 | 4.765 ± 0.116 | 4.948 ± 0.199 | 5.134 ± 0.084 |
| 65536 × 188 | 7.687 ± 0.442 | 20.642 ± 0.453 | 7.897 ± 0.287 | 11.745 ± 0.131 | 12.703 ± 0.181 |
| 65536 × 191 | 12.019 ± 0.129 | 21.693 ± 0.491 | 11.973 ± 0.069 | 12.143 ± 0.073 | 12.638 ± 0.047 |
| 65536 × 192 | 7.680 ± 0.291 | 18.395 ± 0.199 | 7.922 ± 0.315 | 8.990 ± 0.174 | 8.242 ± 0.223 |
| 65536 × 193 | 11.800 ± 0.312 | 18.498 ± 0.370 | 11.782 ± 0.261 | 8.757 ± 0.143 | 12.280 ± 0.180 |
| 65536 × 196 | 7.877 ± 0.342 | 19.009 ± 0.602 | 8.274 ± 0.284 | 11.260 ± 0.374 | 11.910 ± 0.313 |
| 32768 × 256 | 4.684 ± 0.084 | 14.443 ± 0.311 | 4.758 ± 0.169 | 5.073 ± 0.109 | 4.943 ± 0.101 |
| 16384 × 512 | 4.944 ± 0.301 | 15.309 ± 0.250 | 4.645 ± 0.210 | 5.321 ± 0.132 | 4.927 ± 0.090 |

Full router medians in milliseconds; raw artifacts also contain MAD/min/max:

| m × n | A | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| 131072 × 32 | 6.062 | 11.195 | 6.897 | 7.939 | 6.079 |
| 131072 × 64 | 10.734 | 23.169 | 10.701 | 15.688 | 10.841 |
| 65536 × 128 | 10.179 | 23.950 | 10.552 | 10.746 | 10.896 |
| 65536 × 188 | 15.731 | 39.829 | 15.716 | 19.582 | 20.403 |
| 65536 × 191 | 69.361 | 114.576 | 68.754 | 68.480 | 69.647 |
| 65536 × 192 | 15.452 | 37.002 | 15.518 | 16.728 | 16.089 |
| 65536 × 193 | 19.655 | 37.206 | 19.639 | 16.755 | 20.102 |
| 65536 × 196 | 16.340 | 102.455 | 16.840 | 19.493 | 20.219 |
| 32768 × 256 | 12.254 | 27.411 | 12.347 | 11.923 | 12.904 |
| 16384 × 512 | 16.143 | 32.926 | 15.839 | 16.559 | 16.161 |

Unweighted geometric mean speedups A/variant over these ten cases:

| Variant | Isolated scan | Full router |
|---|---:|---:|
| C: OpenMP SIMD | 1.005× | 0.983× |
| D: independent streams | 0.830× | 0.904× |
| E: unroll-four | 0.884× | 0.935× |

These aggregates describe this chosen workload set, not application-wide gains.
C's roughly half-percent aggregate isolated gain is within observed variability;
its small wins vary between repeated campaigns. D's real local win at 193
columns is **1.348× isolated / 1.173× end-to-end**, but at 64 columns it runs at
only 0.471× baseline scan speed and it changes boundary decisions. E preserves
the measured numerical results but has no consistent large-scan gain.

The retained implementation has **1.000× structural speedup**: unchanged source
and identical production binary, with no claimed new throughput improvement.
The no-vectorization control takes about 1.50–3.10× the production isolated
time across the ten large cases, confirming the existing compiler SIMD matters.

## Branch, cache and routing interpretation

The max branch is not intrinsically demonstrated to be materially worse: 188
columns takes 7.687 ms while 196 columns takes 7.877 ms on the other branch,
roughly equal per-element throughput. The 191- and 193-column cases are both
slower than 192 columns despite belonging to different branches. Remainders,
row stride/alignment, and per-row overhead confound a simple threshold comparison.

For production, a 4096×192 scan takes 0.263 ms versus 7.680 ms at 65536×192:
about 24 versus 13 GB/s of matrix bytes per second. At 256 columns the respective
figures are about 24 versus 14 GB/s. Cache residency materially affects the scan.
However, **memory bandwidth is not proven to be the dominant limit**: these
figures are effective payload rates, not memory-controller counters or a measured
bandwidth ceiling. Norm/quality decisions, horizontal reductions and row-level
long-double work also remain. `perf stat` was unavailable (`perf_event_paranoid=4`);
no elevated counters or machine-policy changes were requested.

Every timed case/variant returned UNIQUE, rank n, deterministic certainty,
fallback 0, and accepted_random 0, with accepted quality. There are nevertheless
internal route differences in B:

* At **65536×196**, B performs one formation check; A/C/D/E perform none.
  B takes 102.455 ms versus A's 16.340 ms.
* At **4096×192**, A/C/D/E perform one formation check; B performs none.
  B takes 2.120 ms versus A's 10.864 ms.
* Source-QRCP counters are zero in these cases. Therefore the counters identify
  entry into guarded candidate work, not source-QRCP escalation. Inspection of
  `solve_router_raw` shows that LU quality failure can route into global QR
  without changing the public fallback flag; this is a plausible explanation,
  not a complete dynamic call trace. The exact intervening internal route was
  not instrumented. The other measured cases have matching counters.

These two B end-to-end comparisons mix arithmetic cost with numerical routing;
they must not be advertised as pure SIMD speedups. B disables auto-vectorization
throughout the fast TU, so changes elsewhere in candidate generation also matter.
Only the isolated fixed-anchor scan directly attributes its A/B difference to
this kernel and its norm helper. For several ordinary large shapes the isolated
scan time is roughly half the solver time, indicating substantial scan work;
this is a timing comparison, not a sampled call-time profile of the solve.

## Semantic regression and acceptance

All full CTest runs used the single-thread environment above:

| Build | Result | Elapsed |
|---|---|---:|
| Retained normal | 35/35 | 16.65 s |
| Retained no-autovec | 35/35 | 17.28 s |
| C, OpenMP SIMD | 35/35 | 16.87 s |
| D, four streams | 35/35 | 16.73 s |
| E, unroll-four | 35/35 | 16.79 s |

This includes classification/rank regressions, certified API and verifier tests,
directed-rounding/MXCSR/link contracts and the strict FMA-contraction gates.
No certificate/verifier regression was observed in these suites.

`tests/test_compat_scan_variants.py` additionally checks 2,700 fixed-anchor
cases: 20 widths including vector remainders and the 192 threshold, zero rows,
zero-row contradictions, scales 1e-200 through 1e200, shifted buffers, and
probes near compatibility and quality decision thresholds. It reports decision
changes separately from diagnostic rounding changes and has an explicit
`--require-equal` gate for retained variants.

| Variant vs A | Compatibility decision changes | Quality decision changes | Diagnostic changes |
|---|---:|---:|---:|
| B, no-autovec | 84 | 88 | 2189 |
| C, OpenMP SIMD | 17 | 21 | 903 |
| D, four streams | 78 | 80 | 1831 |
| E, unroll-four | 0 | 0 | 0 |
| Retained normal | 0 | 0 | 0 |

C/D disagreements occur in the factor-1.0 probes constructed at the analytical
decision boundary. They remain real decisions, despite green broad suites.
For example C at quality/n=7/seed=2 changes reported backward error from
9.994114890745228e-15 to 1.0001243360710096e-14, crossing the unchanged 1e-14
quality threshold. Such a change can affect candidate acceptance or quality repair.
These experiments were rejected rather than changing a tolerance.

B also has one change at factor 1.01, quality/n=192/seed=1: 1.0051083592171356e-14
versus 9.950021508520635e-15. This is a diagnostic-control numerical dependency,
not a proposed production change. The raw report records every disagreement and
the deterministic test script reproduces the inputs. E and retained normal pass
`--require-equal`, including diagnostics. This finite battery is not a proof of
universal equivalence; retaining the original source avoids introducing a new
ordering contract.

## Reproduction and evidence

Raw evidence is committed in `reports/simd/stage2a-evidence.tar.gz` (763,522 bytes),
SHA-256 `58f04a612434f8437da7c09db0b665a79ea8038bf46e9cfc0baa6339a6256fa7`.
It contains the final `abs-stage2a-measured.json`, earlier comparison campaigns,
all freeze manifests, compiler reports, focused worker disassembly, differential
semantics and complete CTest output. It contains no binaries or build trees.
Temporary compiled artifacts remain at the build paths above; no source tree
was copied to `/tmp` and no worktree was created or removed.

To reproduce, use clean named branches at the frozen commits in the identity
table (or named worktrees under the prescribed `/projects/.worktrees` location).
At each revision run the tracked helper, choosing a fresh artifact directory:

```sh
python3 experiments/compat_scan_bench.py build /tmp/abs-stage2a-baseline
python3 experiments/compat_scan_bench.py build /tmp/abs-stage2a-control --scalar
# At each respective candidate commit, build its separately named directory.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
python3 experiments/compat_scan_bench.py bench \
  --variant baseline=/tmp/abs-stage2a-baseline \
  --variant control=/tmp/abs-stage2a-control \
  --variant simd=/tmp/abs-stage2a-simd \
  --variant accum4=/tmp/abs-stage2a-accum4 \
  --variant unroll4=/tmp/abs-stage2a-unroll4 \
  --shapes 131072x32,131072x64,65536x128,65536x188,65536x191,65536x192,65536x193,65536x196,32768x256,16384x512,4096x191,4096x192,4096x193,4096x256 \
  --repeats 21 --cpu 0 --output /tmp/abs-stage2a-measured.json
ctest --test-dir /tmp/abs-stage2a-final --output-on-failure
ctest --test-dir /tmp/abs-stage2a-final-control --output-on-failure
python3 tests/test_compat_scan_variants.py \
  --variant baseline=/tmp/abs-stage2a-baseline \
  --variant retained=/tmp/abs-stage2a-final --require-equal retained \
  --output /tmp/abs-stage2a-retained-semantics.json
```

Use the final harness revision for the comparison/replay commands. Supply every
variant to the differential script to reproduce the full disagreement report.
Build flags and exact source/binary identities are more authoritative than the
example directory names. Build helper refuses a dirty checkout.

## Limitations and next step

Measurements are local to one hybrid laptop CPU/compiler/BLAS configuration.
CPU affinity and one-thread execution improve comparability but cannot eliminate
thermal/frequency drift, OS interference, or allocator-address effects. Some MADs
are appreciable; small apparent gains are not accepted as improvements. Memory
bandwidth dominance and exact per-function solver time remain unproven without
counters or intrusive profiling. Multithread performance was not benchmarked;
existing thread/fenv regression tests passed. The finite semantic battery does
not exhaust all inputs. No claim of an exhaustive search over all possible C
loop transformations is made.

Compiler SIMD is already effective. Directives alone do not materially improve
it, reassociation risks current decisions, and unrolling regresses representative
large scans. **Explicit AVX2 is not justified; stop here and audit/profile the
tail scan as a separate task.** No tail, packing, BLAS, strict-proof, threshold,
API/ABI, or classification-policy changes were retained, and no release or merge
was performed.
