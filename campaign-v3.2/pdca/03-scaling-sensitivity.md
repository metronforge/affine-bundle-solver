# PDCA 3 — scaling and sensitivity

## PLAN

- Hypothesis: the leading cost has a computation/repetition signature distinguishable from fixed overhead, memory syscalls, and useful four-thread scaling.
- Matrix: exact V31-025/026/027 at one and four threads, plus four nearby 2:1 tall probes (128x64 through 320x160) at four threads. Four calls per isolated process separate the first cold call from three warm calls.
- Acceptance: QRCP calls grow with null-space scan length, timing grows super-quadratically, and the signal remains present after warmup.
- Falsifier: constant call count, near-fixed timing, or strong positive four-thread scaling.
- Safety: one thread is attribution-only; four threads remains the official baseline; no tolerances, inputs, result fields, or solver code change.

## DO

Executed the bounded cycle-3 matrix. Records include wall time, process CPU utilization, RSS, thermal readings, router count, aggregate QRCP/LAPACK time, and cold/warm identity.

## CHECK

For 2:1 tall shapes, QRCP calls per certified call were 134, 198, 262, and 326—exactly `2*n + 6` in this probe family. Warm wall medians were 8.971, 103.036, 266.053, and 421.775 ms; the fitted exponent versus `n` was 4.24. Aggregate QRCP time fitted 5.02, an empirical local exponent distorted by small sizes and parallel-runtime transitions, not a general complexity proof. The evidence-level inference is repeated cubic factorization whose repetition count grows linearly.

Four threads were slower than one: speedup ratios were 0.560 (V31-025), 0.861 (V31-026), and 0.306 (V31-027). V31-027 changed from 71.161 ms at one thread to 232.330 ms at four. Warm CPU utilization for the large tall four-thread probes was only about 1.38–1.40 CPU equivalents, consistent with synchronization/parallel-runtime overhead around many small QR factorizations. Peak RSS stayed within 85,568–87,268 KiB across the nearby tall probes. All router counts were one and no thermal-throttling signal was observed.

## ACT

Accept with refinement. Repeated factorization is primary; unsuitable four-thread behavior amplifies it, but thread count is frozen by contract and is not the selected optimization. Cycle 4 independently times the public generator and attempts to falsify the attribution using a larger-element-count comparison.
