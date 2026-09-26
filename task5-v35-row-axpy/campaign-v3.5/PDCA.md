# Ralph quartet ledger

## Cycle 1 — identity, correctness, portability, and sanitizer validity

### PLAN

Hypothesis: both pushed branches have the claimed immutable content; A preserves the numerical contract; B remains buildable and internally consistent. Falsifiers are an identity discrepancy that cannot be resolved, an unregistered numerical failure, invalid sanitizer execution, ABI/export drift, or a portability/build failure. Safety controls are isolated worktrees, test-first correction of blocking defects only, and invalidation of timing after any timed-code correction.

### DO

Fetched origin, captured full graphs/trees, checked open PRs, built portable/native GCC configurations, ran workflow regressions, strict properties, exact-library harness tests, system/SciPy BLAS CTest, installed consumers, ABI/export comparisons, row-level differential, reentrancy/failure injection, and valid sanitizer partitions. Clang was unavailable and is a recorded skip. Audited and corrected two blocking test-infrastructure defects test-first.

### CHECK

A passed 31/31 native tests in system portable, system native, and SciPy-OpenBLAS configurations; B passed 30/30 in each. A's direct frozen-row differential compared 1,968 calls, 31,160 rows, and 1,502,768 entries with zero contract failures and 228 contract-equivalent signed-zero endpoint differences. Both strict PBT batteries matched M byte-for-byte; equivalence-orbits reported 8,335 checks and exactly 154 registered pre-existing representation cases, with no new failures; certificate-equivariance reported 2,271 checks with no failure. Public headers and exported symbols were unchanged. Valid M and A sanitizer partitions passed; a contaminated preload attempt is retained as invalid, not pass. The FP gate now demonstrably fails on missing objdump, empty/absent symbol, unsupported architecture, no inspected instructions, and a contracted fixture.

### ACT

Accepted Cycle 1 after corrected immutable identities were established. No performance data predated those corrections. Proceed to adversarial effect separation.

## Cycle 2 — independent adversarial review and effect separation

Pending.

## Cycle 3 — freeze and validate measurement protocol

Pending.

## Cycle 4 — one-shot qualification, manuscript audit, and final report

Pending.
