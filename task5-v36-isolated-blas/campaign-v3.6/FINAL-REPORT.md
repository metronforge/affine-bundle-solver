# Task-5 v3.6 final report

## 1. Terminal verdict

`CANDIDATE_NOT_QUALIFIED`

The role-isolated measurement protocol was reliable, but the one-shot
qualification was incomplete: every legacy-control V31-026 worker terminated
with SIGSEGV. Selective reruns are forbidden, so the direct three-slot L/A
geometric mean cannot be established. No PR, campaign, or merge was attempted.

## 2. Verified base

Accepted main is `bb6c30d03191a92695b16d21581bfea6dce9942e`, tree
`e621eef836c2e6edd633c03d657cc582e0e04344`, with sole parent
`1621d104a27eef3b12ec291384cac5f517da79f4`. PR #47's reviewed head is
`521a3e5e1d078ff54d3440aaa72ae742bd415413`; exact-head runs 36249296448 and
36249296446 succeeded. Full reconciliation is in `RECONCILIATION.md`.

## 3. Candidate identity

Candidate commit is `dd30ef900ff7f48d4fe97e79aae94b7e64c48741`, tree
`a89ce2def1fc1b2ef4644cc4d17f13c533b099b7`, parent `bb6c30d...`, title
`perf: accelerate strict unique-row verification`. The worktree was clean when
qualification started.

## 4. Porting and net-diff proof

The candidate contains only four paths: `CMakeLists.txt`, the CI workflow,
`src/status_certificate.c`, and `tests/test_unique_verifier_rows.c`. Production
and differential-test blobs exactly match the reviewed old candidate; the CI
resolution retains Task-1's already merged fail-closed regex context and adds
only the new test token. FP-gate, sanitizer infrastructure, ENOMEM, and
manuscript changes were not duplicated. `RECONCILIATION.md` contains the full
40-character identities and categorized diffs.

## 5. Correctness, sanitizer, ABI, and portability

| Gate | Outcome |
|---|---|
| Frozen differential | pass: 1,968 calls; 31,160 rows; 1,502,768 entries; 228 signed-zero-only endpoints; 0 failures |
| System BLAS portable/native CTest | 31/31 pass in each build |
| SciPy OpenBLAS native CTest | 31/31 pass |
| Exact-library harness | 57/57 pass |
| ASan/UBSan partitions and ENOMEM | pass in valid environments |
| Reentrancy/concurrency | pass |
| Installed C/C++ consumers | 3/3 pass |
| ABI/public headers | identical to accepted main |
| GCC portable/native | pass |
| Local Clang | unavailable; explicit skip, not a pass |
| Strict FP contraction | pass/fail-closed fixtures pass |
| Strict PBT batteries | 8,335 checks with 154 registered cases; 2,271 checks with 0 failures |
| Eight claims, inventory, artifact/publication audit | pass |
| Manuscript | pass, 27 pages |
| `git diff --check` | pass |

Two contaminated preliminary environments are retained and classified invalid,
not counted as passes. Details and exact logs are in `CORRECTNESS-MATRIX.md` and
`evidence/cycle-01/`.

## 6. Runtime fingerprints and A/A

| Config | Active/inactive design | Result |
|---|---|---|
| C1 | solver: system OpenBLAS 4, libgomp 1; legacy: SciPy OpenBLAS 4, all other pools 1; CPUs 1,3,6,8 | pass; worst API upper 1.023451, worst E2E upper 1.023410 |
| C2 | every pool 1; CPU 1 | timing bounds pass, but one package-throttle invalidation; ineligible without rerun |
| C3 | system/SciPy OpenBLAS, MKL, libgomp, libiomp5 all 4; CPUs 1,3,6,8 | diagnostic only; worst API upper 1.210205 and order effect |

All process maps, libraries, direct requested/effective limits, affinities,
topology, governors, turbo, frequencies, temperatures, and throttle counters
are in the raw JSON. C1 was selected because it was the only eligible
configuration; the tie-break was not reached. See `CALIBRATION.md`,
`SELECTED-RUNTIME.json`, `timings/aa-*.json`, and `analysis/aa-*.json`.

## 7. One-shot direct qualification

The raw checkpoint contains all 288 scheduled records. Thirty-two failed: the
L/V31-026 warmup plus all 31 eligible L/V31-026 processes died with SIGSEGV.
There were no M or A execution failures.

Available paired results are retained but cannot replace the missing direct
three-slot result:

| Slot | L/A E2E speedup | M/A API speedup | M/A E2E speedup |
|---|---:|---:|---:|
| V31-025 | 1.2630x | 0.9934x | 0.9935x |
| V31-026 | unavailable | 4.9201x | 4.9177x |
| V31-027 | 2.2473x | 1.4995x | 1.4994x |

The V31-025 M/A API one-sided 95% upper ratio is 1.016115, which individually
passes the 1.03 non-inferiority limit. All 93 M/A meaningful comparisons pass;
all 93 A calls carry the one-router invariant; A runtime/thermal checks pass;
and A median RSS ratios versus M are 1.0057, 1.0038, and 1.0027. Nonetheless,
the complete-set/no-execution-failure gates fail and the direct L/A three-slot
geometric mean and interval are undefined. `analysis/qualification-failure.json`
contains the paired intervals and exact failure classification.

## 8. Dense secondary

Not run after the failed pre-PR gate. See `DENSE-SECONDARY.md`.

## 9. Independent review

Not requested because qualification did not pass. See `INDEPENDENT-REVIEW.md`.

## 10. PR and exact-head CI

No v3.6 candidate PR was opened and the candidate was not pushed. No candidate
CI was started. See `PR-CI.md`.

## 11. Complete 27-slot campaign

Not authorized or run; no historical rows were mixed. See `FULL-CAMPAIGN.md`.

## 12. Integration

No squash merge was attempted, so there is no squash SHA, parent, title, or
merged tree. See `MERGE-VERIFICATION.json`.

## 13. Evidence locations

Campaign root:
`/home/viktor/task5-v36-isolated-blas/task5-v36-isolated-blas/campaign-v3.6`

- `RECONCILIATION.md`, `CORRECTNESS-MATRIX.md`, and `PDCA.md`: identities,
  correctness matrix, and exactly four PDCA cycles.
- `PROTOCOL.md`, `COMMANDS.md`, `ENVIRONMENT.json`, `BUILD-IDENTITIES.json`,
  and `BUNDLE-HASHES.txt`: preregistration and inputs.
- `CALIBRATION.md`, `CALIBRATION-SHA256SUMS`, `SELECTED-RUNTIME.json`, raw
  `timings/aa-*.json`, and `analysis/aa-*.json`: C1/C2/C3 evidence.
- `QUALIFICATION-IDENTITIES.json`, `QUALIFICATION-PROTOCOL.md`, raw
  `timings/qualification.json`, and `analysis/qualification-failure.json`:
  one-shot qualification.
- `evidence/cycle-01/` and the Cycle-2/3 evidence files: raw test and decision
  logs.
- `SHA256SUMS`: final artifact inventory.

Historical evidence, preserved workspaces, the old Branch A, and stash state
were not modified. No force-push, history rewrite, direct main push, release,
or publication occurred.

