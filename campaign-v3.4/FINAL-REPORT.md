# Task-5 v3.4 shared production-overhead closure

## Terminal verdict

`CORRECT_CHANGE_NOT_BENEFICIAL`

The one optimization is correct and improves both intended unique-verifier
slots, but the single pre-registered branch qualification failed its no-slot
production-API-regression gate. Per the task contract, no solver PR was opened
and neither post-merge nor canonical measurements were run.

## Exact identity and integration state

- Campaign: `task5-v3.4-shared-overhead-20260926`
- Solver base: `1621d104a27eef3b12ec291384cac5f517da79f4`
  (tree `86dd1f677664160e40de72c0121e72fa5e54a83b`)
- Local solver branch: `perf/task5-v3.4-shared-overhead`
- Correct unmerged solver head: `5409f2a0ce35e6471b158b92e32eb3af91f68cf6`
  (tree `f93452c2c4f4735b57b6643f2640de835a973535`)
- Solver commits:
  - `a87b140` `perf: skip structural zeros in unique verifier`
  - `5409f2a` `test: cover unique verifier allocation failures`
- Harness branch: `perf/task5-v3.4-shared-overhead-validation`
- Harness baseline: `28d2722750852e0ddbf95a2cc375d89c2b81d5ab`
- Harness evidence commits before closure: `190cbdc`, `731b935`, `44612dc`
- Solver PR, CI, merge, parent count: not applicable; Cycle 3 did not authorize
  any integration action.
- `origin/main` remains `1621d104` and was not rewritten.

## Known-failure audit

The 154 `known-representation` cases are registered in
`results/pbt_full_strict_guard_telemetry.json`, date to public commit `48b9fce`,
and predate v3.3. The telemetry, equivalence, and certificate result files are
byte-identical between `f66cd87` and `1621d104`. The v3.4 full property run
executed 8,335 equivalence checks and reproduced exactly 154 registered cases
(24 `affine_translation_2^30`, 130 inconsistent translation sweep), with zero
hard failures. The certificate battery added 2,271 checks with zero failures.
No unregistered failure was accepted.

## Production, validation, and harness separation

Cycle-1 uninstrumented medians use identical boundaries and five post-warmup
trials per slot. Times are milliseconds.

| Slot | production API | required caller preparation | correctness validation | harness-only | total wall |
|---|---:|---:|---:|---:|---:|
| V31-025 | 66.133 | 0.952 | 32.046 | 9.963 | 106.517 |
| V31-026 | 100.593 | 1.014 | 42.723 | 15.934 | 160.892 |
| V31-027 | 66.732 | 0.914 | 33.940 | 10.309 | 111.893 |

Only production API time justified the solver change. Correctness validation,
independent test oracles, serialization, logging, process management, and
harness bookkeeping were neither removed nor used as a performance claim.

## Ranked shared production costs

The figures below are instrumented medians and therefore attribution evidence,
not production timing. The direct C verifier probe provides the independent
route for the selected target.

| Component | V31-025 ms | V31-026 ms | V31-027 ms | Decision |
|---|---:|---:|---:|---|
| Unique verifier | 0.000 | 63.969 | 27.338 | selected; shared across 026/027 and avoidable structural work proven |
| QRCP (`dgeqp3`) | 47.364 | 22.436 | 21.699 | rejected; required decomposition, no new reuse invariant |
| DGELSY | 23.471 | 14.120 | 16.572 | rejected; required solve, no bounded equivalent replacement |
| DGESVD | 17.259 | 8.401 | 10.299 | rejected; required independent certificate/rank role |
| Router | 36.583 | 14.561 | 11.780 | rejected; not one common removable component |
| Same-mode `fesetround` | immaterial | sparse inconsistent path | immaterial | rejected; median 10.405 ns/call and insufficient leverage |

The independent probe measured the old/direct unique reconstruction kernels at
48.687/13.816 ms on V31-026 and 14.141/3.907 ms on V31-027. Instrumented verifier
timing was slower (profiler/counter distortion), so the lower-overhead direct
route was used for the Amdahl estimate. The measured removable fractions against
the frozen end-to-end candidate times were 21.221% and 9.099%; V31-025 was zero.
The projected geometric mean was 1.6235208607x, sufficient to select the target.

## Implementation invariant and structural counts

The unique witness stores unit-lower `L` and upper `U` in one packed n-by-n
array. For entry `(L*U)[lr,j]`, both factors can be nonzero only when
`k <= min(lr,j)`. The helper now reads those packed values directly under the
same explicit downward then upward rounding passes and preserves the nonzero
summation order. It never materializes full `lrow` or `ucol` arrays.

| Domain | baseline dot products | candidate dot products | removed temporary writes |
|---|---:|---:|---:|
| n=4 structural test | 128 | 60 | 80 |
| V31-026, n=192 | 14,155,776 | 4,755,520 | 7,114,752 |
| V31-027, n=128 | 4,194,304 | 1,414,528 | 2,113,536 |

The production state remains stack/local and reentrant. `pos[m]` and `evec[n]`
remain owned allocations; `lrow[n]` and `ucol[n]` are removed. Both remaining
allocation failures return safely and restore rounding. Test-only counters and
allocator seams are absent from installed binaries and add no exported symbol.

## Correctness and safety

| Suite | Result |
|---|---:|
| Native system-BLAS CTest | 30 passed, 0 failed |
| Portable system-BLAS CTest | 30 passed, 0 failed |
| SciPy-OpenBLAS CTest | 30 passed, 0 failed |
| Exact-library harness | 45 passed, 0 failed |
| Applicable ASan+UBSan native | 13 passed, 0 failed |
| Applicable ASan+UBSan Python semantics | 12 passed, 0 failed |
| Property/differential checks | 10,606; 0 hard/new failures; 154 registered known cases |
| Installed C/C/C++ consumers | 3 passed, 0 failed |
| Native/portable semantics | 30/30 evaluations agree |
| System/SciPy BLAS semantics | 30/30 evaluations agree |
| Reentrancy | 64 calls, 4 threads, 0 failures |
| Bounded meaningful differential | all pairs agree; every candidate router count is 1 |

Public headers and dynamic symbol sets are unchanged. NaN/Infinity-safe
canonical comparisons passed. Sanitizer failures retained in the evidence are
limited to stream fixtures that intentionally set `RLIMIT_AS` below ASan's
shadow/fake-stack requirement and unsanitized examples loading sanitizer-built
libraries; all applicable changed-path probes passed. Local clang was absent.

Independent review was not requested: the task authorizes review and a PR only
after the branch qualification gate passes.

## Branch qualification: single retained dataset

Protocol: one excluded warmup, 11 eligible trials per path/slot, deterministic
alternating order, process isolation, all supported thread variables fixed to
four, no profiler, no exclusions, and no selective reruns. MAD/CV and paired
bootstrap confidence intervals are in the raw record.

| Slot | API baseline/candidate ms | API speedup | API CV baseline/candidate | API paired median (95% CI) | E2E baseline/candidate ms | E2E speedup | E2E paired median (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| V31-025 | 37.559 / 40.609 | 0.925x | 20.93% / 38.27% | 0.919x [0.717,1.191] | 80.445 / 82.156 | 0.979x | 1.004x [0.860,1.050] |
| V31-026 | 99.398 / 71.208 | 1.396x | 17.87% / 19.13% | 1.456x [1.180,1.832] | 149.613 / 127.955 | 1.169x | 1.191x [1.093,1.515] |
| V31-027 | 65.431 / 57.969 | 1.129x | 21.77% / 30.65% | 1.046x [1.012,1.516] | 112.941 / 104.936 | 1.076x | 1.016x [0.960,1.266] |

Branch API and end-to-end geometric means are 1.1337269682x and
1.0720911465x. Combining the end-to-end branch ratios with the frozen v3.3
per-slot evidence gives 1.167x, 1.184x, and 2.734x, geometric mean
1.5573814868x. Thus the aggregate target would be plausible.

The mandatory no-regression predicate nevertheless fails: V31-025's production
API median is 8.122% slower, above 3%. V31-025 does not execute the changed
unique verifier, and its wide interval is consistent with the known noisy slot,
but the prospective rule permits neither a post-hoc exemption nor a selective
retry. This single false predicate determines the terminal verdict.

Median RSS ratios are 1.0013, 1.0025, and 1.0018; there is no material memory
regression. Every record reports `ELIGIBLE_NO_THROTTLE_SIGNAL`; temperature and
frequency samples are retained. The host exposes no stronger throttle counter.

## Integration and canonical campaign

Cycle 3 failed, so the solver branch was not pushed, no PR or exact-head CI was
created, and no merge was attempted. Therefore no official post-merge 11-trial
set exists. The hard pre-campaign gate was never reached and the canonical
27-slot campaign was correctly not started.

## Rejected hypotheses and remaining risk

- Same-mode rounding setup: insufficient measured leverage.
- QRCP/DGELSY/DGESVD: material but required; no safe new reuse boundary was
  established for this bounded task.
- V31-025 harness/bookkeeping: explicitly outside the production claim.
- A second optimization: prohibited and not attempted.

The main uncertainty is V31-025 noise (candidate API CV 38.27%). A future task
may pre-register stronger machine isolation or a robust equivalence/noninferiority
design before collecting data. It must not reuse this result as permission for
selective reruns. The unmerged optimization remains technically defensible for
V31-026/027 but is not qualified under this task's frozen gate.

## Artifacts

Primary artifacts are under `campaign-v3.4/`: immutable `manifest.json`,
`identity.json`, `initial-reconciliation.json`, `known-failure-audit.json`,
`environment.json`, raw Cycle-1 and Cycle-2 evidence, property reports,
`timings/branch-qualification.json`, four PDCA reports, `correctness.json`,
`COMMANDS.md`, this report, and `SHA256SUMS`. Diagnostic source and generators
are under `task5v34/`; regression tests are under `tests/`. Exact hashes are in
`SHA256SUMS`.

Historical campaigns and the preserved V3 worktree were not modified.
`stash@{0}` was not modified or dropped. No benchmark inputs, seeds, tolerances,
controls, numerical semantics, router behavior, independent verification,
history, or `main` were changed.
