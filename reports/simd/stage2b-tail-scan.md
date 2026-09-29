# Stage 2B: tail/secant scan SIMD audit

## Decision

**Stop SIMD optimization of this kernel for now; retain the production arithmetic.**
All four reductions and both subsequent updates already use 256-bit AVX/FMA on
this AVX2 machine. No accumulator spills occur in either hot loop. Compiler SIMD
has a substantial measured benefit. Explicit AVX2 is not justified by a missing
vectorization opportunity or demonstrated register bottleneck.

The scan is material on selected rank-deficient workloads, but is not a universal
router hot path. Its estimated contribution is about 8–38% in the route-confirmed
single-thread cases below. This is reason to retain good generated code, not
proof that intrinsics will improve it. No compiler-directed reassociation,
unrolling, loop fusion or SIMD directive experiment was attempted: the assembly
provided no concrete missing-SIMD limitation to address. Consequently no stable
restructuring improvement is claimed. No production speedup is claimed either:
the normal production library is byte-identical to integrated Stage 2A.

## Source and execution identities

Canonical repository: `/projects/affine-bundle-solver`.
Branch: `perf/simd-stage2b-tail-scan`.
Integrated local main/base: `984dece8aef30c27b101e80e3eff6a5a8995da0f`.
Stage 2A was fast-forwarded into local main at the user's request; this Stage 2B
branch has not been merged or pushed.

Both measured builds were frozen from clean source commit
`7ff034cf8a143bf27770b449efd8b1f25616b22a`, tree
`8a5a8258aea8bf9f100e96dae04aeefa0d060178`:

* A: `/tmp/abs-stage2b-measured-normal`.
* B: `/tmp/abs-stage2b-measured-control`, with
  `ABS_DISABLE_ROUTER_AUTOVECTORIZATION=ON`.

No solver or C diagnostic code changed during these campaigns. The primary
reviewed campaign uses harness `dcf0430`; common-prefix and two-thread campaigns
use `ed5701d`. Full SHAs are in each benchmark JSON's `protocol.harness_commit`.
Earlier source checkpoints and exploratory/pre-review results are retained as
historical evidence, not mixed into the final tables. Documentation is committed
separately; `git log -1 --format=%H -- reports/simd/stage2b-tail-scan.md` identifies it.
Every build manifest includes repository/branch/commit/tree, dirty state,
compiler/CPU/BLAS identities, compile/link commands and library/object hashes.
Input and microprobe vector hashes are per case; prefix Q/x hashes are recorded.

Measured on 2026-09-29: Intel Core Ultra 9 185H, GCC 15.2.0, AVX2/FMA, no AVX-512.
SciPy OpenBLAS is the solver BLAS; its file/hash is frozen in each manifest.
Router flags remain `-O3 -march=native -fopenmp -ffast-math -fPIC`.
B adds only `-fno-tree-vectorize -fno-tree-slp-vectorize` to router objects;
scalar FMA and BLAS SIMD remain enabled. Strict flags remain
`-O2 -frounding-math -fno-fast-math -ffp-contract=off`.

## Production paths and reachability

There are exactly two four-reduction scan bodies, both in `try_secant_tail`:
current `src/bsolver.c:700` (OpenMP worker) and `:704` (serial path), corresponding
to pre-instrumentation lines 689 and 693. This function has one production caller,
`solve_blockprefix_qr`. The block route is exported through `bsolve_block_api`
and selected by `solve_router_raw` after its first source rows all grow the probe,
the square-LU proposal declines (return 0), and `n >= 192`. A successful LU,
the LU return-2 global-QR route, and the ordinary auto-QR route bypass the tail.

Before the call, the first `p=min(n,m)` rows must yield a certified prefix rank
without unresolved core ambiguity, with prefix residual at most `1e-11`, and
rank strictly below n. The explicit call guard is `n>=192 && n-pre.r<=256`.
Allocation failure, an inconsistent prefix, formation failure/source arbitration,
or a full-rank prefix can return before the scan. The while loop additionally
requires `i<m`, consistent state and rank below n. Reaching the helper does not
by itself prove any rows were scanned; counters record actual rows.

Serial processing is the default and the only path with `OMP_NUM_THREADS=1`.
An OpenMP window requires all of:

* initial prefix rank at least `n/2` and maximum thread count greater than one;
* at least 32 consecutive non-growing rows, `i>=covered`;
* `(m-i)*n >= 1000000`.

Windows hold up to W=2048 source rows, distributed statically among workers.
Each worker uses its own e0/e1 and f storage; the parent combines them afterward.
A zero-norm row skips updates. Every other block row updates e0/e1. In serial,
nonzero rows update E only when `i>=covered`. After a hit in a pre-scanned window,
covered remains at that window's end, so subsequent serial revisits can execute
the four reductions without another E update. Selected rows enter the existing
certified insertion path. Growth refreshes/downdates secants; prefix-exceeding
rank is subsequently resolved by the source arbiter, never silently promoted.

The benchmark `rankdef` family uses Gaussian rows with one exactly zero column
(rank n-1); `half` has only its first n/2 columns active. RHS is A times a generated
anchor. These intentionally reach the route, unlike the ordinary full-rank
control. Widths 64 and 128 cannot reach this tail through production; their
microprobe numbers are context-only. Typical measured routed widths are
192, 193, 196, 256 and 512. Single-thread row counts are exactly m-n (3,903–32,576),
with one E update per scanned row and no insertions/growth. These are controlled
route-representative synthetic cases, not evidence of application-wide incidence.
No claim is made that most real user systems take this path.

## Assembly findings

Evidence is actual production-object disassembly, including
`try_secant_tail._omp_fn.0` and `try_secant_tail.constprop.0`, not merely parent
compiler summaries. The GCC all-vectorization reports retain both optimized and
missed diagnostics. Reports identify four-dot and update loops with 32-byte and
16-byte vectors; outer row-loop misses reflect surrounding control flow.

| Operation | Production serial and OpenMP inner loops |
|---|---|
| an2 | One YMM accumulator, `vfmadd231pd acc,v,v`, four doubles/iteration |
| ax | One YMM accumulator, FMA with loaded row and x memory operand |
| az0 | One YMM accumulator, FMA with row and Z[0:n] memory operand |
| az1 | One YMM accumulator, FMA with row and Z[n:2n] memory operand |
| e0/e1 | Subsequent vector loop: coefficient broadcasts, two packed FMAs, two unaligned stores; no cross-element reduction |

Production worker reduction addresses 0x4d00–0x4d23:

```asm
vmovupd      ymm0, [row+offset]
vfmadd231pd  ymm3, ymm0, [x+offset]
vfmadd231pd  ymm1, ymm0, [Z0+offset]
vfmadd231pd  ymm2, ymm0, [Z1+offset]
vfmadd231pd  ymm4, ymm0, ymm0
```

The serial main reduction is at 0x10140–0x10163 with the same four accumulator
chains. Each reduction horizontally combines high/low 128-bit halves using
`vextractf128` and `vaddpd`, then high/low doubles with `vunpckhpd` and addition.
Two-element remainders use XMM packed operations and the final element uses
scalar FMA; small widths have scalar/two-element entry paths. Width 193 therefore
adds a scalar tail and changes row stride relative to 192.

Worker update loop 0x5000–0x5027 and serial update loop 0x11740–0x11766 each load
four row elements and update both E vectors with `vfmadd213pd` and `vmovupd`.
The compiler versions the update loops for possible aliasing, retaining scalar
fallback and XMM/scalar remainders. There is no aligned-memory precondition:
`vmovapd` here also appears in register-to-register copies, not evidence that
input buffers must be aligned.

Four independent vector reduction chains are present, one per quantity, not
multiple partial accumulators per quantity. Neither the reduction backedge nor
the update backedge contains stack loads/stores of vector accumulators. Surrounding
setup, pointer bookkeeping and calls do use the stack; the much larger serial
function also contains unrelated vector work and spills. Those are not evidence
of spills in the target inner loop.

The purported six-stream case is two consecutive loops, separated by norm,
hash and coefficient computation. The row is intentionally read again for the
updates, and E is read/modified/stored; this is not register-spill traffic.
There is no demonstrated additional hot-loop reload caused by register pressure.
Serial and outlined code have materially the same vector arithmetic, with
different dispatch, alias checks, pointer setup and scalar bookkeeping.
The control worker has scalar `vfmadd...sd` operations and no YMM loop.
The extracted row microprobe also retains all four YMM FMA chains and vector
updates; focused microprobe disassembly is retained separately.

No cycle/stall/cache hardware counters were available: `perf stat` fails under
`perf_event_paranoid=4`. Thus assembly rules out observable inner-loop spilling,
not every possible throughput, dependency, bandwidth or front-end limit.

## Measurement boundaries

`experiments/tail_scan_probe.c` includes the actual router translation unit.
The installed production library has unchanged exports. Three diagnostic
libraries are built under the same router flags and linked to unchanged strict
objects with local symbol binding:

* `libtail`: uninstrumented real-helper replay, plus the row microprobe.
* `libtrace`: counters and capture of the real private prefix BState. Used only
  outside every benchmark interval. It copies the prefix and owns it until
  replay finishes; capture failure is checked.
* `libprofile`: boundary clocks around the real while loop, with row counters
  disabled. Used in separate profiling invocations, never as the timed router.

The real helper replay includes allocation/state copy, secant construction,
scan, selected-row handling if any, validation and final compatibility scan.
It is a tail-subsystem measurement, **not** a pure four-dot timing. Main-table
replays use each build's own prefix; prefix hashes differ between A and B.
The separate common-prefix campaign passes A's exact captured prefix to both
builds and checks/records helper return codes on every repetition. All these
replays return 1 (a result), INFINITE, with expected rank and accepted_random=1.

For narrow isolation, `tail_scan_row.inc` is the verbatim production serial row
body. Build-time comparison refuses a drift from `src/bsolver.c`. Its wrapper
uses covered=m for four-dot-only and covered=0 for E updates, preserving the real
row-major layout and the body's arithmetic/branch/update order. It counts hits
instead of inserting selected rows, with fixed random x/Z. It includes norm and
hit decisions, coefficient hashing, allocation/zeroing of E and final E checksum
reduction. It is explicitly a **source-extracted contextual microprobe**, not
an end-to-end production execution or a newly optimized implementation. Every row
registers a hit in these retained microprobe timings, whereas the actual routed
scans have zero insertions: the fixed random x/Z exercises a different hit-branch
distribution. Its
common A/b/x/Z inputs make it the narrowest A/B comparison; extrapolation to a
real route is supported separately by actual helper replay and phase profiling.

Primary timing pins to CPU 0, with all four thread controls at 1. Three warmups
precede 21 measured repetitions, deterministically interleaving A/B order.
Tables show median ± MAD in milliseconds; MAD is dispersion, not a confidence
interval. No builds or regression suites ran during the final timing campaigns.
CPU frequency was not locked and the host was not exclusively reserved.
The earlier pre-review campaign is retained separately as historical evidence.

Profile clocks exclude prefix construction, capture, setup and final validation.
They include the while loop, which can contain insertions/downdates on other
inputs. Here zero insertions means the phase consists of scan and loop handling.
**Contribution = separate phase median / uninstrumented router median**, an
estimate, not an exact accounting identity. The profile build still captures
state outside its phase timer, so its full-call time has extra copying and may
perturb caches. It is not used as the denominator. Timing in separate runs,
compiler context and frequency/cache drift also limit precision; profile/router
ratios in raw data make this perturbation visible.

## Single-thread microprobe measurements

A is normal, B is no-autovec. B/A is slowdown without compiler vectorization.
The final full-rank row is a microprobe/bypass control, not tail hotness evidence.

| Family / m × n | Four-dot A | Four-dot B | B/A | +updates A | +updates B | B/A |
|---|---:|---:|---:|---:|---:|---:|
| rankdef:8192x64 | 0.254 ± 0.017 | 0.794 ± 0.043 | 3.12× | 0.466 ± 0.014 | 1.349 ± 0.009 | 2.90× |
| rankdef:8192x128 | 0.650 ± 0.051 | 1.633 ± 0.011 | 2.51× | 1.028 ± 0.020 | 2.767 ± 0.017 | 2.69× |
| rankdef:4096x192 | 0.375 ± 0.004 | 1.291 ± 0.007 | 3.45× | 0.753 ± 0.008 | 2.082 ± 0.009 | 2.76× |
| rankdef:4096x193 | 0.430 ± 0.009 | 1.404 ± 0.007 | 3.27× | 0.825 ± 0.016 | 2.205 ± 0.008 | 2.67× |
| rankdef:32768x192 | 4.236 ± 0.185 | 12.823 ± 0.425 | 3.03× | 6.679 ± 0.143 | 17.225 ± 0.189 | 2.58× |
| rankdef:32768x193 | 7.260 ± 0.168 | 12.293 ± 0.379 | 1.69× | 9.800 ± 0.108 | 16.678 ± 0.025 | 1.70× |
| rankdef:32768x196 | 4.245 ± 0.227 | 13.035 ± 0.249 | 3.07× | 6.325 ± 0.160 | 17.295 ± 0.239 | 2.73× |
| rankdef:32768x256 | 5.210 ± 0.140 | 16.342 ± 0.449 | 3.14× | 7.942 ± 0.140 | 24.211 ± 0.559 | 3.05× |
| rankdef:16384x512 | 5.082 ± 0.213 | 17.394 ± 0.473 | 3.42× | 7.035 ± 0.054 | 24.408 ± 0.401 | 3.47× |
| half:32768x256 | 5.213 ± 0.081 | 16.417 ± 0.302 | 3.15× | 7.579 ± 0.104 | 23.555 ± 0.521 | 3.11× |
| full:8192x192 | 0.711 ± 0.047 | 2.493 ± 0.029 | 3.51× | 1.937 ± 0.084 | 4.103 ± 0.051 | 2.12× |

For route-relevant shapes the four-dot control is 1.69–3.45× slower, and the
update control 1.70–3.47× slower. This demonstrates effective compiler SIMD in
this context, not a speedup introduced by this task. The 193-column large case
is slower even in A than nearby divisible widths; remainder/stride/cache effects
are credible explanations, not established causal conclusions. No counter data
separates them. No arithmetic changes were tried to exploit that local difference.

## Actual production-route timings and estimated contribution

All routed entries below scan exactly m-n rows, once, and update E on every row.
Both builds have matching route counters and raw class/rank/fallback/random flags.
The small widths and full-rank control have zero tail entries and are excluded
from contribution attribution. Full-router A/B differences include every fast-TU
kernel and potentially numerical routing effects; they are not tail-only speedups.

| Family / m × n | Helper replay A | Helper replay B | Router A | Router B | A scan phase | Estimated share |
|---|---:|---:|---:|---:|---:|---:|
| rankdef:8192x64 | bypass | bypass | 1.531 ± 0.017 | 3.200 ± 0.028 | 0.000 ± 0.000 | 0.0% |
| rankdef:8192x128 | bypass | bypass | 4.618 ± 0.084 | 8.531 ± 0.186 | 0.000 ± 0.000 | 0.0% |
| rankdef:4096x192 | 1.075 ± 0.007 | 3.202 ± 0.012 | 7.556 ± 0.143 | 9.833 ± 0.062 | 0.761 ± 0.039 | 10.1% |
| rankdef:4096x193 | 1.218 ± 0.023 | 3.448 ± 0.039 | 7.695 ± 0.660 | 9.659 ± 0.586 | 0.733 ± 0.036 | 9.5% |
| rankdef:32768x192 | 10.476 ± 0.236 | 27.025 ± 0.192 | 21.289 ± 0.263 | 42.257 ± 0.478 | 6.605 ± 0.085 | 31.0% |
| rankdef:32768x193 | 16.169 ± 0.113 | 26.112 ± 0.235 | 26.231 ± 0.463 | 41.206 ± 0.525 | 9.894 ± 0.151 | 37.7% |
| rankdef:32768x196 | 10.171 ± 0.183 | 26.738 ± 0.236 | 20.682 ± 0.447 | 41.907 ± 0.328 | 6.926 ± 0.199 | 33.5% |
| rankdef:32768x256 | 13.066 ± 0.131 | 39.781 ± 0.935 | 30.242 ± 0.490 | 62.691 ± 1.024 | 7.916 ± 0.131 | 26.2% |
| rankdef:16384x512 | 13.539 ± 0.227 | 42.212 ± 0.596 | 95.557 ± 1.230 | 129.663 ± 1.163 | 7.331 ± 0.083 | 7.7% |
| half:32768x256 | 13.925 ± 0.163 | 38.719 ± 0.861 | 23.335 ± 0.377 | 56.835 ± 0.814 | 7.650 ± 0.139 | 32.8% |
| full:8192x192 | bypass | bypass | 2.129 ± 0.324 | 3.816 ± 0.405 | 0.000 ± 0.000 | 0.0% |

The main large 192/193/196/256 cases spend about 26–38% in the scan; at 512
columns it is only 7.7%, with substantial time outside the tail loop. The
smaller 4096-row cases spend about 10%. These proportions make a hypothetical
whole-loop elimination an upper bound, not an achievable SIMD gain. Ordinary
full-rank and n<192 routes get no benefit from this target at all.

Common-prefix replay eliminates A/B differences in prefix construction from the
replay input. It still includes the helper's final compatibility scan and setup:

| Family / m × n | A | B | B/A |
|---|---:|---:|---:|
| rankdef:32768x192 | 10.316 ± 0.347 | 26.306 ± 0.454 | 2.55× |
| rankdef:32768x193 | 15.953 ± 0.178 | 25.836 ± 0.201 | 1.62× |
| rankdef:32768x256 | 13.161 ± 0.391 | 37.522 ± 1.157 | 2.85× |
| rankdef:16384x512 | 13.448 ± 0.150 | 39.525 ± 0.405 | 2.94× |
| half:32768x256 | 13.021 ± 0.134 | 37.950 ± 0.559 | 2.91× |

## OpenMP-capable path

Supplementary measurements use OMP_NUM_THREADS=2, CPUs 0 and 1 (different physical
cores), with all BLAS thread controls still 1. They are not mixed into the
single-thread results or used to claim parallel scaling. Each case reaches six
2048-row windows (12,288 block rows); remaining serial rows are 3,903 at n=193
and 3,840 at n=256. Every nonzero row updates E and neither case inserts a row.

| Shape | Shared-prefix helper A | B | Router A | B |
|---|---:|---:|---:|---:|
| rankdef:16384x193 | 5.692 ± 0.196 | 8.526 ± 0.230 | 15.825 ± 0.646 | 20.518 ± 0.751 |
| rankdef:16384x256 | 6.732 ± 0.330 | 11.886 ± 0.277 | 23.391 ± 0.310 | 34.828 ± 2.309 |

A separate growth trace uses n=256, m=16384, a rank-128 prefix, and a new direction
starting halfway through the rows. It verifies serial revisits without E updates
and source arbitration after growth: 4,127 serial scans versus 3,840 serial
updates (287 update-free revisits), 12,288 block scans/updates and one insertion/
growth, identically in A/B. Both finish INFINITE/rank129/fallback1/random0.
It is reachability evidence only, not a
performance result. See `growth-telemetry.json` for exact counts and decisions.

## Correctness, strict boundary and limitations

| Validation | Result |
|---|---|
| Normal full CTest | 35/35 passed, 16.85 s |
| No-autovec full CTest | 35/35 passed, 17.07 s |
| Counter instrumentation vs corresponding production | 96 comparisons, zero decision or residual diagnostic changes |
| Timer-only instrumentation vs production | Same 96 comparisons, exact checked outputs unchanged |
| Row boundary differential A vs B | 960 cases; 42 hit-decision changes, 290 E/f diagnostic changes |
| Diagnostic-only subset of preceding row | 269 cases (21 had both a hit change and diagnostic change) |
| Full-router A vs B boundary cases | One fallback change; no class/rank/random-acceptance change |
| Retained compatibility/quality battery vs Stage 2A | 2700 cases; zero decision or diagnostic changes |
| Strict object hashes and flags | Identical formation guard, verifier and certified API objects across base/A/B; no native/fast flags leaked |
| Installed production exports | Identical base/A/B export sets |

The complete suites include strict FMA-contraction gates, rounding/MXCSR,
certified API/verifier, and link/build-contract checks. `contract.json` retains
the explicit flag and hash verification.

The tail boundary battery covers 20 widths (including vector remainders), zero
rows, scales 1e-200 and 1e200, an eight-byte buffer shift, and compatibility probes
at factors 0.99, 1 and 1.01 of the fixed analytical threshold. These are row-hit
changes, not evidence of changed final classifications. Router probes additionally
cover rank defects/growth/full rank and scales 1e-150, 1, 1e150. The one control
router difference is full/192/1e-150: both return UNIQUE/rank192/random0, but
fallback changes from 0 to 1. There is no separate quality gate inside the row
body; quality equivalence of retained normal code is covered by the 2700-case
compatibility/quality battery. No quality-equivalence claim is made for B.

Normal production library SHA-256:
`4381c68a4e30d7c37ca49edd4f77e8ef7e4169ce22bfc0c19a55608399a9fbe3`.
Control production library SHA-256:
`2e14f6d76f0e1084d8ad905f54c6dd9ff0fc9ee2408890651750f1dcaa20c5b4`.


No operational thresholds, classification/rank policies, fallback, random
acceptance policy, source/candidate arbitration, certificate arithmetic, public
API or ABI were changed. No protected strict source was modified. The only
production-source additions are opt-in diagnostic macros that preprocess to
no-ops normally; byte identity is stronger evidence than a finite semantic test
for the retained normal binary on this compiler/build. No intrinsics or
arithmetic-reordering experiments were introduced, even transiently.

The row boundary battery intentionally demonstrates that no-autovec is not
universally decision-equivalent. It is a diagnostic control only. Since no
restructuring variant was attempted, there is no accepted/rejected optimization
variant and no basis for claiming compiler-directed restructuring helps. Future
reassociation would still require fixed-threshold differential testing, even
if all broad tests passed.

Limitations: one CPU/compiler/BLAS environment; controlled synthetic rank defects;
no application-wide route-frequency survey; no hardware counters; separate
phase timings with possible compiler/cache perturbation; limited two-thread
coverage; no confidence intervals or frequency lock. The contextual row probe
has a different surrounding function and fixed candidate vectors. Same-state
helper replay includes other work. Strictly pure four-FMA throughput and memory
bandwidth dominance are not established. The finite semantic battery is not a
universal equivalence proof for diagnostic builds or the no-autovec control.

## Recommendation and answers

1. **Already AVX2/FMA?** Yes: actual serial and outlined worker bodies use YMM FMAs.
2. **All four reductions?** Yes, one independent packed accumulator for each.
3. **Updates SIMD-efficient?** Yes: both use packed FMA/load/store loops with tails.
4. **Register pressure limiting?** No observed inner-loop spilling; no counter-based
   proof of a different bottleneck. Two consecutive loops avoid six live reductions.
5. **Actually hot?** Yes on these selected rank-deficient routes; bypassed by tested
   ordinary full-rank and small-width routes. General incidence is unknown.
6. **Router fraction?** About 8–38% in the measured routed single-thread cases,
   subject to the phase-timing qualifications above.
7. **No-autovec cost?** Row microprobe about 1.69–3.45× four-dot and 1.70–3.47× with
   updates for routed shapes; common-prefix whole-helper replay 1.62–2.94×.
8. **Restructuring stable improvement?** Not attempted; no demonstrated missing SIMD
   or spill limitation warranted it. No improvement claimed.
9. **Restructuring semantics?** None attempted. Instrumentation comparisons are
   unchanged; no-autovec itself changes boundary hits and one tested router fallback.
10. **Explicit AVX2 justified?** No, not from this evidence; no intrinsics implemented.
11. **Next step?** Stop this SIMD stage. If application traces establish this route
    dominates, investigate cache/stride and surrounding QR/validation costs first,
    preserving current arithmetic decisions. Otherwise move profiling effort to
    another demonstrated solver-owned cost rather than rewriting these FMAs.

## Reproduction and retained evidence

Committed archive: `reports/simd/stage2b-evidence.tar.gz`, 870,460 bytes.
SHA-256: `68cf1af9972a74ce2330af88cccaa2f0c610712bc83620eb4f8077852d1e3fd1`.
It contains 62 files: frozen manifests, focused assembly, optimized/missed
compiler reports, raw benchmark/profiling/route JSON and logs, full CTest logs,
semantic differentials and contract checks. It contains no binaries/build trees.
`SHA256SUMS.json` verifies the individual evidence files. The extracted staging
copy is `/tmp/abs-stage2b-evidence`; prior runs are classified in its README.

Build from clean named branch/commit 7ff034c; use the final harness revision for
measurement commands (later changes affect only Python validation/selection):

```sh
python3 experiments/tail_scan_bench.py build /tmp/abs-stage2b-measured-normal
python3 experiments/tail_scan_bench.py build /tmp/abs-stage2b-measured-control --scalar
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
python3 experiments/tail_scan_bench.py bench \
  --variant normal=/tmp/abs-stage2b-measured-normal \
  --variant control=/tmp/abs-stage2b-measured-control \
  --cases rankdef:8192x64,rankdef:8192x128,rankdef:4096x192,rankdef:4096x193,rankdef:32768x192,rankdef:32768x193,rankdef:32768x196,rankdef:32768x256,rankdef:16384x512,half:32768x256,full:8192x192 \
  --repeats 21 --output /tmp/abs-stage2b-primary-reviewed.json
python3 experiments/tail_scan_bench.py bench \
  --variant normal=/tmp/abs-stage2b-measured-normal \
  --variant control=/tmp/abs-stage2b-measured-control \
  --cases rankdef:32768x192,rankdef:32768x193,rankdef:32768x256,rankdef:16384x512,half:32768x256 \
  --modes tail_shared --repeats 21 --output /tmp/abs-stage2b-shared.json
OMP_NUM_THREADS=2 python3 experiments/tail_scan_bench.py bench \
  --variant normal=/tmp/abs-stage2b-measured-normal \
  --variant control=/tmp/abs-stage2b-measured-control \
  --cases rankdef:16384x193,rankdef:16384x256 --modes tail_shared,router \
  --threads 2 --cpus 0,1 --repeats 21 --output /tmp/abs-stage2b-block.json
OMP_NUM_THREADS=2 python3 experiments/tail_scan_bench.py trace \
  --variant normal=/tmp/abs-stage2b-measured-normal \
  --variant control=/tmp/abs-stage2b-measured-control \
  --cases growth:16384x256 --output /tmp/abs-stage2b-growth-telemetry.json
ctest --test-dir /tmp/abs-stage2b-measured-normal --output-on-failure
ctest --test-dir /tmp/abs-stage2b-measured-control --output-on-failure
python3 tests/test_tail_scan_diagnostics.py \
  --normal /tmp/abs-stage2b-measured-normal --control /tmp/abs-stage2b-measured-control \
  --output /tmp/abs-stage2b-semantics.json
```

All valuable diagnostic source is committed on this branch. No worktrees or
alternative source trees were created. Temporary directories contain builds and
reports only; no source implementation is stranded there. Previous build/run
directories remain retained. Final report/evidence commit follows the tooling
checkpoints; no release or automatic Stage 2B merge is performed.
