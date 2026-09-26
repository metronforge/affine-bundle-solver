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

### PLAN

Hypothesis: A's two-pass verifier is equivalent to M and acceleration is algorithmic rather than a flag artifact. Falsifiers are changed per-accumulator term order, unsafe aliasing, mode leakage, mutable state, changed allocation failure, or an M→F effect comparable to F→A. Safety controls are source-only adversarial review, frozen direct differential, and a five-pair diagnostic excluded from qualification.

### DO

Reviewed the verifier, gate, build modes, aliasing, allocation paths, and v3.4 comparison. Ran the preregistered M/F/A diagnostic on all three slots.

### CHECK

No blocking semantic or ownership finding remains. M→F API ratios stayed near one. F→A was approximately 2.248× API on V31-026 and 1.148× on V31-027; V31-025 was approximately 0.992× and noisy. Branch A and v3.4 are distinct transformations; A's row-pass/fenv reduction has the stronger direct differential and no-contraction evidence.

### ACT

Accepted the equivalence and attribution hypothesis for diagnostic purposes. It does not qualify performance. Proceeded to the frozen A/A protocol.

## Cycle 3 — freeze and validate measurement protocol

### PLAN

Hypothesis: 31 paired observations on fixed P cores can distinguish a 3% V31-025 regression from host noise. Acceptance requires all A/A point ratios in `[0.97,1.03]`, one-sided uppers below 1.03, bounded/no-significant order effect, and identical loaded-library fingerprints. Failure forbids qualification without adaptation.

### DO

Committed protocol/analysis/tests as `292e1b3` before timing. Synthetic equality, 2% regression, 4% regression, and clear-improvement tests passed. Ran M1/M2 once using 31 eligible pairs per slot, then the full 100,000-resample analysis. Ran the preregistered diagnostic thread/library matrix without changing the decision.

### CHECK

The A/A point window and library-fingerprint checks passed. V31-027 upper bounds were 1.043563 API and 1.046280 end-to-end; order-effect magnitude also failed on V31-026/027. The host maps MKL, SciPy OpenBLAS, system OpenBLAS, libiomp, and libgomp in the same runner. Four-thread pinned results were materially slower than one-OpenBLAS-thread pinned results.

### ACT

Rejected the measurement-reliability hypothesis. Froze terminal verdict `MEASUREMENT_PROTOCOL_UNRELIABLE`; made no protocol changes and collected no official qualification data.

## Cycle 4 — one-shot qualification, manuscript audit, and final report

### PLAN

Hypothesis: official qualification is authorized only after A/A passes; Branch B can independently be classified READY or NOT_READY. A/A failure is an explicit falsifier that prohibits the L/M/F/A and dense stages.

### DO

Honored the stop gate and did not run official or dense qualification. Audited every Branch B change against source, constants, paths, retained claims, the built manuscript, and registry; reran all eight claims and publication/inventory audits with the qualified libraries, then restored tracked generated artifacts.

### CHECK

Branch B is buildable and publication-ready: 27 pages, final pass with zero unresolved references/citations and zero overfull boxes, all eight claims reproduced, registry hash exact, inventory/audit ready. It does not claim Branch A. Branch A remains numerically/safety qualified but has no permitted performance qualification result.

### ACT

Completed exactly four cycles. Terminal verdict: `MEASUREMENT_PROTOCOL_UNRELIABLE`. Recommend no Branch A PR authorization from this evidence, yes Branch B PR authorization, and yes redesign of the future benchmark thread/runtime configuration before a new preregistered host-qualification attempt.
