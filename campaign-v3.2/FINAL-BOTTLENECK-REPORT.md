# Task-5 v3.2 bottleneck report

## Verdict

`BOTTLENECK_IDENTIFIED`

The dominant future optimization target is the repeated QR-with-column-pivoting factorization in the compatible-tall inconsistent-witness availability fallback. On V31-027, native interposition attributes 255.786 ms (73.6% of instrumented end-to-end time) to 262 `dgeqp3_` calls. An independently linked C driver attributes 44.288 ms (72.2% of the 61.345 ms public combined call) to `bs_generate_inconsistent_witness`. The same generator is 42.37x faster on V31-026 despite V31-026 having more matrix elements.

No solver optimization was implemented, no solver PR was opened, and the canonical 27-slot campaign was not started.

## Frozen identity and reconciliation

- Campaign: `task5-v3.2-bottleneck-20260926`
- Analysis branch: `perf/task5-v3.2-bottleneck-analysis`
- Harness measurement baseline: `1827f2d458bcf55b0ade81a1174d1fa2ceb9d9ad`
- Solver: `f66cd87a7b198497cc53d63b2bb04b85c3e64f53`
- Solver parent/tree: `0ace47c78b7ed2e7b067a77254326bd17f2e2623` / `4173cef889e0f1ec3ef60bc8aeadad26937a1711`
- Certified library SHA-256: `3e44f86e3a4bdf6418e9b343fabb63142329f7997221745c24687ce2328f6535`
- Solver PR/CI: [PR #45](https://github.com/metronforge/affine-bundle-solver/pull/45), [merged CI run](https://github.com/metronforge/affine-bundle-solver/actions/runs/36197900181)

Initial reconciliation confirmed PR #45 was already squash-merged, `origin/main` matched `f66cd87`, and the solver commit has one parent. The v3.1 harness baseline and dedicated solver worktree were clean. The preserved v3 workspace remained at `770fb9c` and was not modified. A separate `/projects/affine-bundle-solver` checkout contained pre-existing unrelated files and was not used or changed. Contrary to the historical note, `stash@{0}` was absent from every relevant repository inspected; no stash was created, applied, modified, or dropped.

Environment: Ubuntu kernel 7.0.0-34, Intel Core Ultra 9 185H, 22 logical CPUs, Python 3.13.5, NumPy 2.3.1, SciPy 1.16.1, GCC 15.2.0, system OpenBLAS and libgomp. `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `BLIS_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` were all frozen to 4 for official measurements. Detailed versions and hashes are in `environment.json`.

## Four-cycle result

| Cycle | Primary evidence | Decision |
|---:|---|---|
| 1 — phase decomposition | Five production plus five separate instrumented trials/slot; largest two exclusive phases explain 67.0–87.6% | Accept |
| 2 — native hotspots | `dgeqp3_` is 73.6% of V31-027 with 262 calls; selected memory syscalls total 5.151 ms | Accept |
| 3 — scaling/sensitivity | Tall QRCP count is `2*n+6`; local warm-wall exponent 4.24; four threads slow V31-027 by 3.26x versus one | Accept/refine |
| 4 — reproduction/falsification | Independent public-generator timing gives 72.2%; V31-027 generator is 42.37x V31-026 | Accept; stop |

The PLAN/DO/CHECK/ACT record for each cycle is preserved under `pdca/`; `pdca-ledger.md` is the concise index.

## End-to-end phase decomposition

Values are median exclusive milliseconds and percent of the separately instrumented end-to-end total. Parenthetical milliseconds are inclusive where nesting exists.

| Phase | V31-025 | V31-026 | V31-027 |
|---|---:|---:|---:|
| Python/control preparation | 0.967 (1.3%) | 1.031 (0.7%) | 0.941 (0.3%) |
| FFI/API boundary | 0.170 (44.541 incl.; 0.2%) | 0.176 (123.115 incl.; 0.1%) | 0.203 (285.803 incl.; 0.1%) |
| Router execution | 6.077 (28.577 incl.; 7.9%) | 15.388 (9.8%) | 13.070 (4.2%) |
| Selected numerical kernels | 36.415 (47.5%) | 44.810 (28.7%) | 224.239 (72.2%) |
| Solution reconstruction | 0.967 (13.173 incl.; 1.3%) | 4.588 (37.682 incl.; 2.9%) | 17.929 (230.006 incl.; 5.8%) |
| Residual/status certification | 0.092 (0.1%) | 0.397 (10.666 incl.; 0.3%) | 0.266 (4.406 incl.; 0.1%) |
| Independent verification | 1.345 (1.8%) | 59.893 (38.3%) | 30.631 (9.9%) |
| Serialization/harness bookkeeping | 30.780 (40.1%) | 29.610 (18.9%) | 24.260 (7.8%) |
| Instrumented total | 76.666 | 156.309 | 310.641 |
| Uninstrumented production total | 105.768 | 148.232 | 286.066 |

Each raw trial reconciles exclusive phases exactly with 0 ns unattributed. Because component medians are independently aggregated, their sums differ from the median total by +0.148 ms (+0.19%), -0.415 ms (-0.27%), and +0.897 ms (+0.29%). Inclusive parent values overlap and are never summed.

## Ranked bottlenecks

| Rank | Component/function | Inclusive time | Self time | End-to-end share | Evidence strength | Uncertainty |
|---:|---|---:|---:|---:|---|---|
| 1 | V31-027 repeated `dgeqp3_` inside `bs_generate_inconsistent_witness` null-direction scan | 255.786 ms | unavailable | 73.6% | Strong: native call counts, phase trace, scaling, direct C reproduction | Absolute time varies with process/runtime state; direct route independently gives 72.2% for the containing generator |
| 2 | V31-026 independent verification aggregate | 59.893 ms | 59.893 ms at phase boundary | 38.3% | Medium: exclusive high-level timing | Not instruction-sampled and not dominant across other slots |
| 3 | V31-025 serialization/harness bookkeeping | 30.780 ms | 30.780 ms | 40.1% | Medium: exclusive monotonic timing | Outside the supported native one-call path; includes process-side observations |
| 4 | `dgelsy_` least-squares kernels | 11.569–18.511 ms | unavailable | 3.3–16.4% | Strong call-boundary timing | Kernel self time and nested BLAS unavailable |
| 5 | Router exclusive work | 6.077–15.388 ms | 6.077–15.388 ms at phase boundary | 4.2–9.8% | Strong phase timing and count=1 | Inclusive router work overlaps kernels on V31-025 |
| 6 | `dgesvd_` kernels | 6.534–9.276 ms | unavailable | 1.9–8.2% | Strong call-boundary timing | Kernel self time unavailable |

`perf 7.0.14` was preferred but prohibited by `perf_event_paranoid=4`; its exact failure is retained. The fallback resolves application functions separately from OpenBLAS/LAPACK symbols. Consequently, exact instruction-level self time is deliberately reported as unavailable rather than inferred.

## Native mechanism

In `src/certified_api.c`, `bs_generate_inconsistent_witness` scans `qi=rank+1..m-1` when a compatible tall system's first computed left-null direction cannot provide a positive-norm pivot. Each iteration calls `left_null_vector_qrcp`, which allocates workspaces, copies the same normalized matrix into column-major storage twice, runs a QR workspace query and a full `dgeqp3_`, then applies one Q column. V31-027 therefore performs 262 QRCP calls per supported combined call, versus four in V31-025/026.

The `strace` probe found only 5.151 ms in selected memory/thread syscalls, so syscall-level allocation is not dominant. Allocator-internal overhead and matrix-copy cost remain embedded in generator exclusive time, but QRCP alone already accounts for the dominant measured share.

## Scaling and thread sensitivity

For 2:1 tall probes from 128x64 to 320x160, QRCP counts were 134, 198, 262, and 326 and warm medians were 8.971, 103.036, 266.053, and 421.775 ms. The local empirical exponents are 4.24 for wall time and 5.02 for QRCP aggregate time; these values are regime-sensitive and are not asserted as asymptotic complexity. The robust inference is linear growth in the number of repeated QR factorizations.

One-thread/four-thread warm medians were 8.861/15.836 ms, 58.082/67.448 ms, and 71.161/232.330 ms for V31-025/026/027. Four threads remained the official baseline; one thread was attribution-only. The poor four-thread behavior amplifies the repeated-work bottleneck but does not replace it as the optimization target. Full results, RSS, CPU utilization, and cold/warm identities are in `scaling-sensitivity.md` and cycle-3 raw evidence.

## Independent reproduction and falsification

| Slot | Direct combined median (ms) | Direct inconsistent-generator median (ms) | Generator share | Combined CV |
|---|---:|---:|---:|---:|
| V31-025 | 5.677 | 0.897 | 15.8% | 13.26% |
| V31-026 | 59.392 | 1.045 | 1.8% | 1.30% |
| V31-027 | 61.345 | 44.288 | 72.2% | 1.22% |

The original broad falsification metric—V31-027 versus V31-026 total combined time—was inconclusive at 1.033x because V31-026 has a separate verification cost. The independently timed public generator is the discriminating test: V31-027 is 42.37x slower even though V31-026 has 12.5% more matrix elements. Thus generic size/memory traffic does not explain the generator hotspot.

V31-027 returns generator code 6 because a compatible system correctly has no inconsistent witness; the driver leaves verifier sentinel 99 because there is no witness to verify. The supported combined API returned zero in all trials. This expected negative-generator path is exactly where the wasted scan occurs.

## Correctness, router, memory, and thermal status

- Final focused suite: 26 passed, 3 skipped, 0 failed.
- Full cycle-4 differential: all meaningful candidate/control fields agree for all three slots.
- Candidate trials checked: 15; observed router execution values: `{1}`.
- Direct C supported API: five successful calls per slot after warmup.
- Peak-RSS candidate versus legacy control: 89,220/89,408 KiB, 87,740/87,780 KiB, and 87,292/87,884 KiB (candidate changes -0.21%, -0.05%, and -0.67%).
- Every retained official trial reported `ELIGIBLE_NO_THROTTLE_SIGNAL`; sensor temperatures and sampled frequencies are retained raw.

Fresh full-harness control/candidate medians were 77.990/91.041 ms (0.857x), 167.055/152.995 ms (1.092x), and 306.387/346.608 ms (0.884x), for a 0.939x geometric mean. These values reproduce the prior performance failure but are diagnostic only; no canonical rows were written.

## Profiler overhead and variance

Cycle-1 instrumented/uninstrumented median differences were -27.5%, +5.4%, and +8.6%. The negative V31-025 value reflects scheduling variance and is not interpreted as speedup. Cycle-4 uninstrumented medians changed by -10.2%, +3.4%, and +0.8% from cycle 1. V31-027—the selected bottleneck—therefore remained stable without instrumentation, and the independently structured direct C route had only 1.22% CV.

Absolute times from the Python/interposition and standalone-C routes are not mixed. The conclusion relies on their agreeing 72.2–73.6% shares and on the independent call-count/scaling evidence.

## Rejected or narrowed hypotheses

- Unnecessary preliminary `xt` solve: already removed in v3.1 and only about 0.4–0.9 ms in retained controls; not material.
- Generic matrix size: rejected for the generator by the 42.37x V31-027/V31-026 generator ratio despite V31-026's larger element count.
- Allocation syscalls: rejected as dominant; selected syscalls totaled 5.151 ms versus 255.786 ms QRCP.
- Fixed Python/FFI overhead: rejected for V31-027; preparation plus exclusive FFI boundary is below 0.4%.
- Serialization as the native bottleneck: rejected; it is 7.8% on V31-027 and lies outside the certified call.
- One universal bottleneck for every slot: rejected. V31-026 has a separate verification hotspot and V31-025 has material harness overhead, but neither prevents a defensible V31-027 target.
- Thread count as the next target: narrowed rather than denied. Four-thread overhead is real, but thread count is frozen and repeated factorization remains dominant under both one and four threads.

## Amdahl bounds and 1.5x feasibility

The two independent leading fractions are 0.7359 and 0.7219. Eliminating that component gives a V31-027 theoretical maximum speedup of 3.79x and 3.60x, respectively. To make V31-027 itself 1.5x faster with everything else unchanged, 45.3–46.2% of the leading component must be removed, equivalent to speeding that component up by about 1.83–1.86x.

For the three-slot geometric mean, if V31-025 and V31-026 do not improve, V31-027 must reach 3.375x. That requires removing 95.6–97.5% of the measured leading component. Complete elimination yields a geometric-mean ceiling of 1.559x–1.532x. Therefore 1.5x remains mathematically plausible without changing the numerical contract, but the margin is narrow: the next optimization must eliminate nearly all repeated QRCP work or also help other slots, with negligible regression.

## Best next optimization target and proposed scope

The next task should hoist a single QRCP factorization of the normalized tall matrix out of the null-direction loop and reuse its implicit-Q representation to test completion directions, preferably in a block application. It should also reuse workspace and column-major storage. The strict verifier, rank decision, row normalization, pivot selection, return-code behavior, router count, and all certificate semantics must remain unchanged.

Suggested bounded scope:

1. Add a failing exact V31-027 reproducer that asserts numerical equivalence and exposes repeated QRCP count/performance.
2. Introduce an internal reusable QRCP context for the inconsistent-witness path; do not form a full `m x m` Q unless memory evidence supports it.
3. Validate threshold-neighborhood, exact-rank-deficient, zero-row, compatible and inconsistent cases, including generator-unavailable code 6.
4. Run normal, sanitizer, ABI, installed-consumer, and exact-head A/B suites at four frozen threads.
5. Require the three-slot geometric mean and per-slot non-regression criteria before a reviewed squash merge.

This report proposes that work but does not implement it.

## Remaining uncertainty and risks

- Instruction-level self time and hardware counters were unavailable; inclusive LAPACK boundary timing is the strongest available native evidence.
- Frequency changed between samples under `intel_pstate`/`powersave`; thermal sensors showed no throttling, but firmware-level throttling cannot be ruled out absolutely.
- V31-025/026 process timings have 10–16% CV; they are not used to establish the primary V31-027 share.
- Reusing one factorization must be proven numerically equivalent across pivoting, normalization, and fallback order; changing which valid certificate is produced may still alter meaningful fields.
- Removing the leading V31-027 cost will expose V31-026 verification and V31-025 harness overhead as the next limits.
- The three-slot 1.5x bound has little theoretical headroom if only V31-027 improves.

## Evidence inventory

- Immutable manifest: `manifest.json`
- Environment/tool versions: `environment.json`
- Raw records and summaries: `evidence/cycle-01-*.json` through `cycle-04-*.json`
- Phase ledger: `phase-ledger.json`
- Scaling/RSS table: `scaling-sensitivity.md`
- Correctness record: `correctness-checks.json`
- Exact commands: `COMMANDS.md`
- Four PDCA reports and ledger: `pdca/` and `pdca-ledger.md`
- Integrity inventory: `SHA256SUMS`

Historical v3/v3.1 evidence was read only. No historical result row was imported, no N138 or 177-case run occurred, no canonical 27-slot campaign began, no history was rewritten, and no solver branch, commit, PR, or merge was created by this diagnostic task.
