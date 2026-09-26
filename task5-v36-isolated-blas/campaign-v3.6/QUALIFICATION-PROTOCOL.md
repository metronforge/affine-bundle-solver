# Frozen one-shot qualification protocol

This protocol is committed after C1 selection and before any candidate timing.
It may not be altered after `timings/qualification.json` begins.

## Schedule and boundaries

The only arms are frozen legacy-equivalent L, accepted main M, and candidate A,
with commits, trees, build flags, paths, and SHA-256 identities in
`QUALIFICATION-IDENTITIES.json`. The configuration is C1 exactly as recorded in
`SELECTED-RUNTIME.json`. V31-025, V31-026, and V31-027 use the already committed
bundles and hashes. Seed `2026093604` generates a deterministic position-balanced
three-arm schedule. Each slot/arm has one retained, excluded warmup and 31
eligible observations. There are no exclusions or reruns.

Every observation is a fresh process. L loads the same system solver library
as its one supported API call but runs the frozen SciPy `gelsd` preliminary
solve to supply `xt`; its SciPy OpenBLAS is active at four threads and every
other pool is one. M and A pass NULL `xt`; system OpenBLAS is active at four,
libgomp is one, and SciPy/MKL/libiomp are forbidden. All use affinity
`1,3,6,8`.

`combined_c_api` times exactly one supported combined C API call. `total_wall`
starts immediately before L's preliminary solve (or immediately before the M/A
API call) and ends after the API returns; it is the frozen end-to-end compute
boundary for direct L/A. `worker_process_wall_ns` is measured by the parent and
includes process startup, imports, runtime inspection, and JSON transport; it
is reported but not substituted for either gate. Process CPU nanoseconds and
peak RSS are retained. Input generation, oracles, serialization, runtime
inspection, and meaningful-field comparison are outside the API and end-to-end
boundaries.

The worker invokes the supported combined entry point once. The retained
`router_executions=1` is the established source/test invariant of that entry
point, cross-checked by `test_certified_diag_once`; it is checked for every A
record. It is not inferred from elapsed time.

## Frozen analysis and gates

Paired effects use `log(candidate/reference)`, median log ratios, fixed seed
`2026093699`, and 100,000 paired bootstrap resamples. L/A per-slot point
speedups use the contemporaneous ratio of L and A medians. Their three-slot
point estimate is the geometric mean; an aggregate bootstrap 95% interval is
reported, but the frozen point gate remains `>=1.5`.

Meaningful equality is the established policy: API return; every certified
field; router fields except RELX and SECONDS (already omitted by this worker);
grey counts/rows; core rank interval/QR rank; and formation-guard counters.
`last_orth_eta`, timing, telemetry, paths, and bookkeeping are not meaningful
API fields. Input hashes must match across paired arms.

The one-shot dataset passes only if all of the following hold:

1. Cycle-1 correctness/sanitizer/ABI/portability remains accepted.
2. V31-025 M/A API one-sided 95% upper bound is strictly below 1.03.
3. No slot's A end-to-end median exceeds M by more than 10%.
4. Direct contemporaneous L/A geometric-mean point speedup is at least 1.5.
5. Every A record has one router execution.
6. Meaningful fields agree for L/A and M/A.
7. Each slot's A median RSS is at most 110% of both M and L.
8. No retained process records a throttle invalidation.
9. Every runtime fingerprint matches C1; M and A fingerprints are identical.
10. M/A API ratio-of-medians shows improvement on affected V31-026 and V31-027.
11. Library identities, input hashes, complete schedule, and evidence checksums pass.

Wall, API, end-to-end, CPU, RSS, frequency, temperature/throttle, maps,
runtime settings, router invariant, and meaningful fields are retained for
every trial. If any gate fails, no PR, second candidate, configuration switch,
or rerun is allowed and the verdict is `CANDIDATE_NOT_QUALIFIED`.

## Exact commands

```sh
python3 -m task5v36.protocol \
  --dataset qualification --configuration C1 \
  --arm L=legacy=/home/viktor/task5-v36-legacy-control/build-v36-qualification/libcertified_solver.so \
  --arm M=solver=/home/viktor/task5-v36-main-calibration/build-m1/libcertified_solver.so \
  --arm A=solver=/home/viktor/task5-v36-row-axpy/build-v36-qualification/libcertified_solver.so \
  --bundle-root task5-v36-isolated-blas/campaign-v3.6/bundles \
  --slots V31-025 V31-026 V31-027 \
  --repetitions 31 --warmups 1 --seed 2026093604 --timeout-seconds 30 \
  --checkpoint task5-v36-isolated-blas/campaign-v3.6/timings/qualification.json

python3 -m task5v36.analysis qualification --configuration C1 \
  --input task5-v36-isolated-blas/campaign-v3.6/timings/qualification.json \
  --expected-library L=0980f344efa9242077e3eced897cd7a5e56491e12838e1cb1de5636a21f2a67f \
  --expected-library M=3dd20bd5c63e42cb1d18c192570eebb99ffa69cc2abf35c1d400689cf8d8f4b6 \
  --expected-library A=e66ae3a97f9adcacc249d83674d7ec62a11d57e2ed2d94ebe67241f4e2dc89b6 \
  --output task5-v36-isolated-blas/campaign-v3.6/analysis/qualification.json \
  --samples 100000 --seed 2026093699 --integrity
```

