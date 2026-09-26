# Task-5 v3.3 reusable QRCP final report

## Verdict

`CORRECT_OPTIMIZATION_TARGET_NOT_MET`

The reusable QRCP optimization is correct, reviewed, CI-green, and squash-merged. It removes the intended O(n) refactorization loop and improves V31-027 end-to-end by 2.540x. The frozen three-slot geometric mean is 1.453x, below the required 1.5x, so the canonical 27-slot campaign was not started.

## Identity and integration

- Campaign: `task5-v3.3-reusable-qrcp-20260926`
- Solver branch/reviewed head: `perf/task5-v3.3-reusable-qrcp` / `87b239745f38514286a7a9d29f11b1a59f5b8245`
- Solver PR: [#46](https://github.com/metronforge/affine-bundle-solver/pull/46)
- Squash commit: `1621d104a27eef3b12ec291384cac5f517da79f4`
- Parent count/parent: 1 / `f66cd87a7b198497cc53d63b2bb04b85c3e64f53`
- Reviewed and merged tree: `86dd1f677664160e40de72c0121e72fa5e54a83b`
- Harness branch: `perf/task5-v3.3-reusable-qrcp-validation`
- Harness evidence-source commit: `91ba4963380f5592f0856ed640113e6d57110c00`
- Exact-head CI: eleven successful jobs in [run 36234297268](https://github.com/metronforge/affine-bundle-solver/actions/runs/36234297268)

## Proven reuse invariant and implementation

Within one `bs_generate_inconsistent_witness` invocation, row normalization writes `An` once. The least-squares and historical QR helpers consume copies and never mutate `An`. Every null-direction scan iteration used the same 256x128 column-major factorization input (`lda=256`), zero JPVT seed, rank decision, normalization, tolerance, and pivot policy; all 258 baseline target-domain entries had FNV hash `ae484947e5ef1103`.

Private `BSLeftNullQRCP` state owns one column-major factor copy, Householder reflectors, `tau`, `jpvt`, rank metadata, DGEQP3/DORMQR workspaces, and a scratch vector. DGEQP3 runs once after its workspace query. DORMQR applies Q or Qᵀ to reset scratch vectors without materializing full Q or mutating the factorization. Cleanup is deterministic on every initialization failure and normal exit. State is invocation-local and reentrant; public API and ABI are unchanged.

Target-domain QRCP entries fell from 258 to 2; full supported-call entries fell from 262 to 6. The after trace retains the same input hash and records one workspace query plus one execution.

## Correctness and safety

- Merged native CTest: 28/28.
- Exact-library harness: 34/34.
- ASan+UBSan native/leak subset: 14/14; sanitized Python snapshots: 12/12.
- Stream ENOMEM: 2/2; all six owned QRCP allocations injectable.
- Property/differential checks: 10,606, no new failures; 154 pre-existing representation cases remained known failures.
- Reentrancy: 64 calls across four threads.
- Installed consumers: 3/3.
- ABI: unchanged public headers and exported symbol set.
- Official candidate/control meaningful comparisons: 15/15 equal with NaN/Infinity-safe serialization.
- Candidate router executions: exactly one in every retained trial.
- Independent exact-head review: APPROVE, zero Critical/Important/Minor findings.

The local Clang executable was unavailable; exact-head CI's Clang portable job passed. An initial installed-consumer probe was contaminated by a trailing-empty `LD_LIBRARY_PATH` from the sanitized build directory; the retained clean rerun from `/tmp` with that variable unset passed 3/3.

## Official bounded-large performance

All values are uninstrumented, process-isolated, four-thread trials. Each path had one excluded warmup and five eligible alternating trials.

| slot | control median | candidate median | speedup | control/candidate CV | control/candidate RSS |
|---|---:|---:|---:|---:|---:|
| V31-025 | 99.656 ms | 83.644 ms | 1.191x | 27.72% / 7.57% | 89,616 / 89,456 KiB |
| V31-026 | 166.436 ms | 164.322 ms | 1.013x | 7.79% / 9.77% | 88,108 / 87,524 KiB |
| V31-027 | 285.705 ms | 112.474 ms | 2.540x | 3.85% / 8.69% | 87,820 / 87,380 KiB |

Geometric mean: **1.4526577258x**. No slot regressed and median RSS ratios were 0.998, 0.993, and 0.995. Temperatures topped out at 58.05°C, sampled frequencies ranged from 0.4 to 2.508 GHz, and no available throttle signal asserted. The raw timing artifact retains all 30 eligible records plus six warmups, phase timings, CPU times, RSS, and thermal samples.

## Residual profile

The single allowed post-failure profile shows the optimization moved V31-027 from one dominant O(n) QRCP loop to distributed costs: QRCP 17.0%, DGELSY 12.8%, DGESVD 7.4%, and DORMQR 3.0% of instrumented end-to-end time. The combined API was 72.696 ms of a 101.680 ms instrumented total; router, witness-generation, and independent-verification medians were 12.605, 25.122, and 20.441 ms. Outside the uninstrumented candidate combined call, validation alone retained a 25.948 ms median. `perf` was unavailable because `perf_event_paranoid=4`; the LD_PRELOAD fallback drifted -9.6% from the official median and is used only for attribution.

The reusable factorization is therefore no longer the dominant residual cost. V31-025 and V31-026 have no O(n) tall-scan benefit and cap the aggregate gain. No unrelated follow-on optimization was attempted.

## Campaign decision, limits, and integrity

The canonical 27-slot campaign did not run because the mandatory pre-gate failed. There are no canonical checkpoints or result rows to resume. The immutable 27-slot manifest was regenerated twice byte-identically with SHA-256 `d14f3a6daa4bdc16dd9a3d2f458a5a0aa8ce01b3f7d52b8f01785a5dafedaf4e`.

Historical v3/v3.1/v3.2 evidence and the preserved V3 workspace were not modified. `stash@{0}` was not modified or dropped (no stash entry was present in the reconciled repositories). No history rewrite, merge commit, repeated uncertain merge, changed input, weakened tolerance, changed control, or canonical result mixing occurred.

Remaining risk is performance variability—especially V31-025 control CV 27.7%—but the fixed five-trial median was used once as specified and was not retried selectively. Even with V31-027's strong gain, the frozen aggregate remains below its hard threshold.
