# Immutable v3.7 reconstructed-control qualification protocol

This protocol and manifest are committed and pushed before qualification.
Candidate-performance data are not exposed before that push.

## Fixed construction

Arms are exactly those in `CONTROL-IDENTITIES.json`. Inputs are regenerated
from the v3.6 mathematical manifest and match the v3.6 V31-025/026/027 hashes
byte-for-byte; no v3.6 observations are reused. The only protocol correction is
the root-cause-qualified OpenBLAS bootstrap for L: start at four threads, then
use direct DSO-specific controls to retain SciPy OpenBLAS at four and lower
system OpenBLAS to one. M and A remain system-OpenBLAS four-thread workers with
SciPy/MKL/libiomp forbidden. All roles use affinity `1,3,6,8`, OMP/libgomp one,
dynamic teams disabled, and deterministic Python hashing.

`combined_c_api` times exactly one supported API invocation. `total_wall`
starts immediately before L's required SciPy `gelsd` witness solve (or before
the M/A API call) and ends after API return. Generation, serialization,
telemetry, and validation are outside both boundaries.

The committed `schedule.json` has one excluded warmup and 31 eligible paired
observations for each of L/M/A on each slot (288 processes total, 279 eligible).
Seed `2026093704` produces deterministic balanced order. No observation may be
excluded or rerun. Any required missing or invalid process yields
`QUALIFICATION_INCOMPLETE`.

## Statistics and gates

Paired effects use log(candidate/reference), median log ratios, and a fixed
100,000-resample bootstrap with seed `2026093799`. Report two-sided 95%
intervals and one-sided 95% upper ratios. L/A per-slot point speedup is the
ratio of contemporaneous total-wall medians; the three-slot point estimate is
their geometric mean. Report aggregate bootstrap uncertainty without replacing
the registered `>=1.5x` point gate.

The run passes only if:

1. all 279 eligible observations and all nine excluded warmups complete;
2. all L/A and M/A meaningful fields agree;
3. every candidate call records exactly one router execution;
4. V31-025 M/A `combined_c_api` one-sided 95% upper ratio is `<=1.03`;
5. direct three-slot L/A total-wall geometric-mean speedup is `>=1.5x`;
6. no A/M slot total-wall median ratio exceeds 1.10;
7. A median RSS is at most 110% of L and M on every slot;
8. no thermal/throttle invalidation or affinity/thread-policy deviation occurs;
9. M/A API medians improve on affected V31-026 and V31-027;
10. library, input, manifest, schedule, raw-record, and analysis checksums pass.

Order effects and variance are assessed and reported but do not create an
unregistered threshold. Any unexplained anomaly invalidates the run.

## Exact commands

```sh
python3 -m task5v37.protocol --dataset qualification-v3.7 --configuration C1 \
  --arm L=legacy=/home/viktor/task5-v37-control-reconstruction/build-l-v37-control/libcertified_solver.so \
  --arm M=solver=/home/viktor/task5-v36-main-calibration/build-m1/libcertified_solver.so \
  --arm A=solver=/home/viktor/task5-v36-row-axpy/build-v36-qualification/libcertified_solver.so \
  --bundle-root task5-v37-control-reconstruction/campaign-v3.7/validation-bundles \
  --slots V31-025 V31-026 V31-027 --repetitions 31 --warmups 1 \
  --seed 2026093704 --timeout-seconds 30 \
  --checkpoint task5-v37-control-reconstruction/campaign-v3.7/timings/qualification.json

python3 -m task5v37.analysis qualification --configuration C1 \
  --input task5-v37-control-reconstruction/campaign-v3.7/timings/qualification.json \
  --expected-library L=7536975097bf05107a0deed26bc1e961f4c3e66c5066c72be3053e62c11703e9 \
  --expected-library M=3dd20bd5c63e42cb1d18c192570eebb99ffa69cc2abf35c1d400689cf8d8f4b6 \
  --expected-library A=e66ae3a97f9adcacc249d83674d7ec62a11d57e2ed2d94ebe67241f4e2dc89b6 \
  --output task5-v37-control-reconstruction/campaign-v3.7/analysis/qualification.json \
  --samples 100000 --seed 2026093799 --integrity
```
