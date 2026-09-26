# PDCA 05 — final control and telemetry overhead

## PLAN

Hypothesis: sampling all CPU frequencies is avoidable harness overhead. Frozen inputs: V3.1 slots 025–027, merged solver `f66cd87`, OpenBLAS/thread variables all set to 4. Falsifier: an end-to-end geometric speedup below 1.5x over the required legacy-equivalent control.

## DO

Added a regression that requires one representative frequency sample, then changed telemetry from all online cores to CPU0. The control and candidate run in fresh processes, alternate deterministically, have one warm-up each, and take three eligible trials each. The only control/candidate semantic difference is the control's preliminary SciPy `gelsd` solve used to supply `xt`; candidate passes a genuine NULL pointer.

## CHECK

`pytest -q tests` passed 21 tests. All retained trials report one router execution and exact meaningful-field agreement. The final comparison is `timings/bounded-large-cycle-05.json`: V31-025 0.963x, V31-026 0.998x, V31-027 0.863x; geometric mean 0.940x. Peak RSS is lower for candidate on each median. Thermal state reports `ELIGIBLE_NO_THROTTLE_SIGNAL`; no throttling signal was present. An earlier retained run (`cycle-04`) was 1.172x, still below threshold.

## ACT

Rejected. The candidate already removes the sole permitted extra computation. Further changes would alter the stipulated control or the numerical contract, so no compliant PDCA hypothesis can reach the 1.5x criterion.
