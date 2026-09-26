# PDCA 4 — performance validation and terminal decision

## PLAN

Hypothesis: removing the repeated QRCP materially improves V31-027 and makes the frozen three-slot target achievable. The immutable control was solver `f66cd87` plus the unchanged preliminary SciPy `gelsd` solve and supplied `xt`; the candidate was squash commit `1621d104` with genuine NULL `xt`. Acceptance required geometric-mean end-to-end speedup at least 1.5x, no slot more than 10% slower, target-domain QRCP count O(1), exact meaningful-field agreement, one router execution, thermally eligible trials, and no median RSS regression above 10%.

## DO

Each of V31-025/026/027 received one excluded warmup for each path and five eligible process-isolated trials in deterministic alternating order. All supported BLAS/OpenMP variables were fixed to four. No profiler was attached. The raw record retains every total/phase/CPU/RSS/thermal observation. The candidate library was rebuilt from detached immutable merge commit `1621d104`; the control library remained the frozen `f66cd87` build.

After the gate failed, exactly one residual profile was run. `perf` was prohibited by `perf_event_paranoid=4`, so the retained safe fallback used monotonic LD_PRELOAD interposition around the supported API, witness generators/verifiers, and BLAS/LAPACK calls. That profile is diagnostic and excluded from official timing.

## CHECK

| slot | control trials (ms) | candidate trials (ms) | control median | candidate median | speedup | control CV | candidate CV | RSS ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|
| V31-025 | 99.656, 84.326, 80.656, 139.278, 144.923 | 98.587, 83.644, 89.376, 83.372, 83.287 | 99.656 | 83.644 | 1.191x | 27.72% | 7.57% | 0.998 |
| V31-026 | 166.436, 179.414, 159.898, 161.379, 191.231 | 143.039, 162.293, 188.321, 164.322, 167.438 | 166.436 | 164.322 | 1.013x | 7.79% | 9.77% | 0.993 |
| V31-027 | 270.502, 285.776, 301.571, 284.617, 285.705 | 119.181, 112.474, 99.370, 102.465, 120.718 | 285.705 | 112.474 | 2.540x | 3.85% | 8.69% | 0.995 |

The three-slot geometric mean is **1.4526577258x**, so the 1.5x gate fails. Every other gate passes: exact meaningful fields for all 15 pairs, candidate router count exactly one, all thermal records eligible with no throttle signal, no slot slower, and candidate median RSS slightly lower in every slot. V31-027 target-domain QRCP calls are 2 (one query and one execution), down from 258; full supported-call count is 6, down from 262.

The residual V31-027 profile attributes 17.327 ms (17.0% of instrumented end-to-end) to the six remaining QRCP entries, 12.979 ms (12.8%) to four DGELSY entries, 7.481 ms (7.4%) to two DGESVD entries, and 3.006 ms (3.0%) to 133 DORMQR entries. API, router, witness-generation, and verification medians were 72.696, 12.605, 25.122, and 20.441 ms respectively. Cost is now distributed; the removed O(n) QRCP loop is no longer dominant. The profiler-route median was 101.680 ms versus the uninstrumented 112.474 ms median, a 9.6% drift, so it is used only for ranking residual costs.

## ACT

Accept the optimization as correct and materially effective on its intended tall path, but reject the performance hypothesis for the frozen three-slot aggregate. Per the pre-gate rule, do not start the canonical 27-slot campaign and do not begin another optimization. Terminal verdict: `CORRECT_OPTIMIZATION_TARGET_NOT_MET`.
