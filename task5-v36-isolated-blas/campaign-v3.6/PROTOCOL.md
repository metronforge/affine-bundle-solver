# Task-5 v3.6 frozen isolation and calibration protocol

Protocol identity: `task5-v3.6-isolated-blas-20260926`.

This file, the harness implementation, `manifest.json`, `COMMANDS.md`, and
`ENVIRONMENT.json` are committed before the first eligible timing observation.
Only accepted main `bb6c30d03191a92695b16d21581bfea6dce9942e` is used in
calibration. Candidate timing is forbidden until calibration is sealed and a
configuration is selected.

## Builds and inputs

Two independent clean CMake build directories from the immutable accepted-main
worktree provide M1 and M2. Both use GCC 15.2, system BLAS,
`ABS_ARCH_FLAGS=-march=native`, testing off, and examples off. The three
bounded-large inputs are V31-025, V31-026, and V31-027 from the preserved
27-slot mathematical manifest. Input materialization, oracles, file I/O,
serialization, runtime inspection, and correctness validation are outside the
timed API region. Bundle matrix and RHS hashes must equal the frozen manifest
hashes.

Each observation is a new process. Its complete `/proc/self/maps`, numerical
libraries, threadpoolctl inventory, direct requested/effective runtime limits,
thread count, affinity, topology, governors, turbo state, frequencies,
available temperatures and throttle counters, and thread environment are
retained. An observation is ineligible if this record is incomplete, its
affinity or active budget is wrong, an effective runtime limit is wrong, a
forbidden runtime is mapped, a throttle counter rises, or execution fails.
Missing platform temperature/throttle files are reported as unavailable and
are not invented.

## Frozen configurations

- C1: fixed affinity `1,3,6,8` (four distinct P cores). Solver workers load
  only system OpenBLAS as active at four threads; libgomp and every other
  mapped pool are directly limited to one. Legacy workers make SciPy OpenBLAS
  active at four threads; system OpenBLAS, MKL, libiomp5, and libgomp are
  directly limited to one. Environment variables are secondary controls;
  direct threadpoolctl evidence is mandatory.
- C2: fixed affinity `1`. Every mapped numerical/OpenMP runtime is directly
  limited to one thread in both roles.
- C3: fixed affinity `1,3,6,8`, all mapped runtimes at four threads, with the
  solver and SciPy stack deliberately co-loaded. It is a five-pair diagnostic
  reproduction of the previous mixed-runtime condition and cannot be selected.

## Calibration schedule and statistics

C1 seed is `2026093601`, C2 seed is `2026093602`, and diagnostic C3 seed is
`2026093603`. Per slot and arm there is one excluded warmup. C1 and C2 have 31
eligible paired observations; C3 has five. Orders are deterministic balanced
rotations produced by `task5v36.protocol.balanced_orders`. The only exclusion
is the named warmup. Failures remain in the checkpoint, make the configuration
ineligible, and are never selectively rerun. An interrupted command resumes
only observation IDs missing from its atomic checkpoint.

For each slot and each of API time (`combined_c_api`) and end-to-end worker
compute time (`total_wall`), analysis uses paired `log(M2/M1)` values and the
median log ratio. With seed `2026093699` (offset deterministically by slot and
metric), it draws 100,000 paired bootstrap samples with replacement. The
one-sided 95% upper bound is `exp(sorted_draws[floor(0.95*N)])`; the two-sided
interval uses the analogous 0.025 and 0.975 indexes. The preregistered order
effect check splits ratios by whether M2 ran first: its median-log difference
must be smaller than `log(1.02)` in magnitude and its two-sided 95% bootstrap
interval must contain zero.

C1 or C2 is eligible only when all six one-sided upper bounds are strictly
below `1.03`, all six order checks pass, fingerprints match exactly between
M1/M2, runtime policy and fixed affinity pass, active-compute budgets are
equal, no throttle invalidation occurs, all 186 eligible records exist, and no
execution fails. Synthetic equality, 2% regression, 4% regression, clear
improvement, and order-effect datasets were tested before collection.

Selection is frozen: discard ineligible configurations; select the eligible
configuration with the smallest maximum API upper bound across the three
slots. If the difference is at most `0.005`, select the lower aggregate M
end-to-end median. C3 is never selectable. If neither C1 nor C2 passes, no
candidate timing may be exposed and the terminal verdict is
`MEASUREMENT_PROTOCOL_UNRELIABLE`.

## Limits and later frozen gates

Per-worker timeout is 30 seconds. The later complete campaign has a 30-minute
wall envelope. These bounds are frozen before calibration and are not changed
after results. Qualification seed is `2026093604`; dense-secondary seed is
`2026093605`; complete-campaign seed is `2026093606`; all later schedules use
the selected configuration unchanged. Qualification gets one warmup and 31
eligible paired observations per arm/slot. The complete campaign gets one
warmup and five eligible L/A observations per slot. No historical row is
eligible in either dataset.

