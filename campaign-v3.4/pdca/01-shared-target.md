# Cycle 1 — Identify one shared production target

## PLAN

Hypothesis: one avoidable production component is material in at least two of
V31-025/026/027 and has enough leverage to raise the frozen 1.4526577258x
geometric mean to 1.5x. Use identical phase boundaries, five post-warmup
production trials per slot, five separately instrumented trials, an independent
direct verifier probe, exact structural counts, and a same-mode `fesetround`
microbenchmark. Accept only a production/API target supported in two slots with
a projected geometric mean of at least 1.5x. Instrumented data cannot serve as
production timing.

## DO

- Built solver `1621d104` cleanly and re-ran 28/28 native tests plus 5/5
  focused harness tests.
- Recorded phase-separated production runs in
  `evidence/cycle-01-raw.json`: API, caller preparation, correctness validation,
  and harness-only work are separate.
- Interposed API, router, witness generators, each verifier, BLAS/LAPACK, and
  `fesetround` using `native_trace.so`; every observed API trial executed the
  router once.
- Ran a second direct C route that generates one unique witness, repeatedly
  verifies it, and compares the old materialized triangular product kernel with
  a direct packed-LU diagnostic kernel.
- Counted the exact baseline work: `n^3+n^2` temporary writes and `2*n^3`
  dot terms. The direct domain requires no row/column temporary writes and
  4,755,520 terms at n=192 or 1,414,528 terms at n=128.
- Measured same-mode `fesetround` independently over 11 million-call trials.

Exact command: `python -m task5v34.cycle1` with every supported thread variable
fixed to four. Raw stdout, commands, thermal/frequency observations, and result
objects are retained without selective reruns.

## CHECK

Median phase separation (ms):

| Slot | production API | caller prep | correctness validation | harness-only | total |
|---|---:|---:|---:|---:|---:|
| V31-025 | 66.133 | 0.952 | 32.046 | 9.963 | 106.517 |
| V31-026 | 100.593 | 1.014 | 42.723 | 15.934 | 160.892 |
| V31-027 | 66.732 | 0.914 | 33.940 | 10.309 | 111.893 |

The first hypothesis—redundant per-product rounding setup in the inconsistent
verifier—was rejected. V31-026 made only 1,159 such calls because its witness is
sparse; a same-mode call costs a median 10.405 ns, insufficient leverage.

The refined shared target is the unique verifier's triangular reconstruction.
It is invoked by V31-026 and V31-027, with instrumented medians of 63.969 ms and
27.338 ms. The independent direct probe measured baseline/direct kernels at
48.687/13.816 ms (V31-026) and 14.141/3.907 ms (V31-027). All numeric interval
values agreed; 283 and 545 internal comparisons differed only in zero sign
(`max_abs=0`), which is not exposed. Full verifier outputs were deterministic.
The tracer is slower than the direct route, so its timings are attribution only.

Using the independent measured savings against the frozen v3.3 candidate total
times gives removable end-to-end fractions 21.221% and 9.099% for V31-026/027.
V31-025 is unaffected. The registered Amdahl projection is 1.6235208607x with
per-slot projected speedups 1.191x, 1.286x, and 2.794x. The target is inside the
production API and independent verification remains present and independently
computed.

Other shared costs were rejected for this task: DGELSY and QRCP are required
decompositions without a newly proven reuse domain; DGESVD is smaller and
required for the independent rank/certificate path; allocation/workspace and
rounding-call costs alone lack sufficient measured leverage; V31-025's
bookkeeping is outside production and prohibited as a solver claim.

## ACT

Accept exactly one target:
`unique_verifier_triangular_zero_and_copy_work`. Cycle 2 may replace temporary
L/U row/column materialization and products by structural zeros with a private
direct packed-LU interval product. It must retain directed rounding, summation
order over all nonzero terms, public API/ABI, output tolerances, error cleanup,
rounding-mode restoration, independence, and reentrancy. No other production
optimization is authorized in this quartet.
