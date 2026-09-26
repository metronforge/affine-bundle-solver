# Cycle 3 — Correctness, safety, and branch qualification

## PLAN

Hypothesis: the single optimization is correct, safe, ABI-neutral, and produces
a real production improvement rather than moving work across timing boundaries.
Run the full specified verification matrix. Then execute exactly one immutable
qualification set: one excluded warmup and 11 eligible process-isolated trials
per path/slot, deterministic alternating order, five thread variables fixed to
four, no selective reruns, medians/MAD/CV/paired ratios/bootstrap intervals,
API-only and complete end-to-end comparisons.

## DO

Qualified solver head `5409f2a` (tree `f93452c`). The second commit adds a
test-only allocator seam and proves both remaining unique-verifier allocation
failures restore rounding and recover on the next call. Production builds do
not contain the seam.

Verification results:

- normal/system CTest 30/30;
- portable/system CTest 30/30;
- SciPy-OpenBLAS CTest 30/30;
- exact-library harness 45/45;
- applicable ASan+UBSan native 13/13 and Python semantic 12/12;
- 10,606 property/differential checks, zero hard/new failures, 154 separately
  registered `known-representation` cases;
- installed C/C/C++ consumers 3/3;
- native/portable and system/SciPy comparisons: 30/30 semantic evaluations each;
- headers and exported symbols unchanged;
- structural and ENOMEM tests passed; four-thread/64-call reentrancy passed.

All failed sanitizer probes are retained in
`evidence/cycle-03-qualification.json`. They are pre-existing incompatibilities
between ASan's address-space/runtime-order requirements and the stream fixture
or unsanitized examples, not failures in an applicable changed-path probe.

## CHECK

The single pre-registered qualification produced:

| Slot | API baseline/candidate ms | API speedup | API 95% paired-bootstrap CI | E2E baseline/candidate ms | E2E speedup | projected legacy speedup |
|---|---:|---:|---:|---:|---:|---:|
| V31-025 | 37.559 / 40.609 | 0.925x | [0.717, 1.191] | 80.445 / 82.156 | 0.979x | 1.167x |
| V31-026 | 99.398 / 71.208 | 1.396x | [1.180, 1.832] | 149.613 / 127.955 | 1.169x | 1.184x |
| V31-027 | 65.431 / 57.969 | 1.129x | [1.012, 1.516] | 112.941 / 104.936 | 1.076x | 2.734x |

The API improvement is supported in the two intended slots. Branch API and
end-to-end geometric means are 1.1337x and 1.0721x; applying the branch ratios
to the frozen v3.3 per-slot speedups projects a 1.5573814868x legacy geometric
mean. Meaningful fields agree, every candidate router count is one, all records
are thermally eligible under the available signal, and median RSS ratios are
1.0013, 1.0025, and 1.0018.

However, V31-025's candidate production API median is 8.122% slower, exceeding
the pre-registered 3% limit. The optimized unique-verifier path is not invoked
for V31-025 and the interval is wide (candidate API CV 38.27%), but the protocol
explicitly prohibits a selective retry or post-hoc exemption. Therefore the
qualification gate is false.

## ACT

Reject branch qualification. Do not request independent review, push the
solver branch, open a solver PR, or attempt a second optimization. Retain the
correct unmerged commits and all raw data. Proceed to Cycle 4 only to record the
non-integration terminal decision required by the quartet.

