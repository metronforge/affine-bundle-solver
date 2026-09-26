# Task-5 v3.5 frozen host-qualification protocol

This protocol was committed before any diagnostic, A/A, or qualification timing was collected. Correctness-only builds and tests preceded it. No timing against either pre-correction Branch A or Branch B head exists.

## Fixed identities and hardware controls

The immutable identities and library hashes are in `manifest.json`. Official execution uses logical CPUs `1,3,6,8`, four distinct physical P cores. Every supported thread variable is fixed to `4`: `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `BLIS_NUM_THREADS`, and `NUMEXPR_NUM_THREADS`. Every trial is a new process launched through `taskset`. One process performs exactly one supported combined-API call. The Linux host exposes frequency but no thermal-zone temperature sensor; the pre-existing runner's no-throttle signal is retained without inventing exclusions.

No eligible observation may be deleted or selectively rerun. Process failure stops that dataset and leaves its atomic checkpoint. Warmups are always retained and excluded from estimates. No post-observation thermal exclusion is allowed.

## Registered datasets

1. Diagnostic effect separation: M/F/A, all three slots, one warmup and five eligible paired observations, seed `2026092601`. Diagnostic only.
2. A/A calibration: independently built M1/M2, all three slots, one warmup and 31 eligible paired observations, seed `2026092602`.
3. Thread/library attribution: M, all slots, one warmup and five eligible observations for each Cartesian arm of `OPENBLAS_NUM_THREADS in {1,4}`, `OMP_NUM_THREADS in {1,4}`, and pinned `1,3,6,8` versus unpinned `0-21`; other supported variables remain four. Seed sequence starts at `2026092603`. Diagnostic only.
4. Official qualification: L/M/F/A, all slots, one warmup and 31 eligible paired observations, seed `2026092604`. This dataset is run once only and only after A/A passes.
5. Dense secondary: M/A, seeded dense inputs committed in `task5v35/dense.py`, one warmup and 11 eligible observations, seed `2026092605`. It runs after official data are sealed and is non-gating.

Within eligible datasets, deterministic randomized balanced orders are produced by `task5v35.protocol.balanced_orders`. The immutable bootstrap seed is `2026092699`.

## Frozen analysis

Paired comparisons analyze `log(candidate_time/reference_time)`. Point estimates exponentiate the median paired log ratio. The one-sided 95% upper confidence bound and two-sided 95% interval use a fixed-seed nonparametric paired bootstrap with 100,000 resamples.

A/A passes only if, for API and end-to-end time in every slot:

- the point ratio is in `[0.97, 1.03]`;
- the one-sided 95% upper bound is below `1.03`;
- the absolute estimated order effect is below `log(1.02)` and its two-sided interval contains zero;
- both builds load the same numeric-library basenames.

If A/A fails, qualification does not run and the terminal verdict is `MEASUREMENT_PROTOCOL_UNRELIABLE`. The trial count, affinity, seeds, thresholds, and analysis are not changed.

Branch A's V31-025 API non-inferiority margin is `1.03`; it passes only if the one-sided upper confidence bound for M/A is below `1.03`. The official original performance claim is the contemporaneous per-slot ratio-of-medians `L total_wall / A total_wall`; their three-slot geometric mean must be at least `1.5`. Historical ratios are never multiplied into this result. Other gates are the task-specified correctness, router count, 10% end-to-end regression, 10% RSS, thermal, production-API, and integrity requirements.

## Input/control definitions

L is the frozen f66 solver plus the unnecessary preliminary SciPy `gelsd` solve supplying `xt`. M, F, and A pass genuine NULL `xt`. Every arm otherwise materializes the same frozen slot and runs the same independent standard and contract oracles. M→F isolates the compile-flag commit; F→A isolates the verifier change plus its tests/corrective harness tests; M→A is the full branch effect.

The dense check uses PCG64 and makes `b=A[:,0]`; shapes, seeds, and byte hashes are emitted by `task5v35.dense.dense_manifest` before it runs.
