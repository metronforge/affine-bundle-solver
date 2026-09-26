# PDCA 1 — end-to-end phase decomposition

## PLAN

- Hypothesis: one or two high-level phases explain most one-call certified-diagnostics runtime.
- Frozen inputs: V31-025/026/027 from the immutable v3.2 manifest; solver `f66cd87`; five warm production trials per slot after separate warmups; five separately instrumented trials.
- Method: `time.perf_counter_ns` around process/harness phases and `CLOCK_MONOTONIC_RAW` interposition around the supported API, router, generators, verifiers, and top-level BLAS/LAPACK calls.
- Acceptance: at least 60% of each slot is attributable to its largest two exclusive phases, with exclusive phase totals reconciling to end-to-end time and no additional router call.
- Falsifier: diffuse timing, material unattributed time, or router count other than one.
- Safety: instrumentation is a separate process path; production timings remain uninstrumented; numerical inputs and outputs are unchanged.

## DO

Executed the cycle-1 command in `COMMANDS.md`. The retained JSON contains 36 records: one uninstrumented and one instrumented warmup plus five uninstrumented and five instrumented production records for each of three slots.

## CHECK

The two largest exclusive phases account for 87.6% (V31-025: kernels plus bookkeeping), 67.0% (V31-026: verification plus kernels), and 82.0% (V31-027: kernels plus verification). Every raw exclusive ledger reconciles exactly and has 0 ms unattributed time. Independently aggregated component medians differ from the end-to-end median by +0.148, -0.415, and +0.897 ms (0.19%, -0.27%, and 0.29%) because medians are not additive. Every candidate has one router execution.

Instrumentation/ambient distortion was noisy: instrumented versus uninstrumented medians were -27.5%, +5.4%, and +8.6%. The negative value is scheduling variance, not a claimed profiler speedup. Absolute production medians therefore remain separate from instrumented phase shares.

## ACT

Accept. The primary native lead is V31-027 numerical kernels (72.2%); V31-026 verification is a distinct secondary hotspot. Cycle 2 tests whether V31-027 is explained by a small native function set.
