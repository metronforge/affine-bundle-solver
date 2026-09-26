# Task-5 v3.6 Ralph quartet

Exactly four cycles are authorized. Each ACT entry is terminal for its cycle and gates the next.

## Cycle 1 — Porting correctness and exact equivalence

### PLAN

Hypothesis: the reviewed unique-row reconstruction and its frozen differential can be overlaid on `bb6c30d` without carrying any old-base FP-gate, sanitizer-infrastructure, or manuscript change, while preserving all numerical, ABI, portability, and safety contracts.

Method: install the frozen differential against unoptimized main and retain RED evidence; overlay only the reviewed algorithm/private hook; retain GREEN and net-diff proofs; then run the full required correctness matrix. Acceptance requires no new correctness, ABI, sanitizer, portability, or publication failure, at least 1,968 calls/31,160 rows/1,502,768 entries, and only explicitly classified signed-zero endpoint differences. Any new unregistered failure falsifies the hypothesis and ends `CORRECTNESS_BLOCKED` before timing.

Safety controls: exact immutable identities, separate worktrees/branches, no change to old Branch A or accepted Task-1 content, strict FP flags/gate, test-only hook, no performance observation during Cycle 1.

### DO

Ported the exact reviewed production/test blobs over accepted main, resolving only the two Task-1 workflow regex contexts. Captured the required RED then GREEN differential. Ran three full BLAS/architecture CTest builds, the exact-library harness, sanitizer partitions, failure/reentrancy checks, installed consumers, ABI/header comparison, strict property batteries, all eight claim reproductions, inventory/artifact/publication audits, manuscript build, and whitespace check. Retained and classified two contaminated command environments rather than counting them.

### CHECK

All acceptance criteria passed. The differential covered 1,968 calls, 31,160 rows, and 1,502,768 entries with exact `evec` equality, 228 separately registered signed-zero-only endpoint changes, and zero failures. System portable/native and SciPy builds each passed 31/31 CTests; exact-library harness passed 57/57; valid sanitizer partitions and both strict PBT batteries passed. Public headers and exports are unchanged. Local Clang is an explicit skip pending exact-head CI. No new unregistered correctness, ABI, sanitizer, or portability failure exists.

### ACT

**ACCEPT.** Freeze candidate `dd30ef900ff7f48d4fe97e79aae94b7e64c48741` for measurement-protocol work. Do not expose candidate timing until Cycle 2 selects and freezes an eligible M/M environment.

## Cycle 2 — BLAS/runtime isolation and A/A selection

### PLAN

Hypothesis: at least one preregistered role-isolated configuration passes the
strict 3% M/M non-inferiority gate for API and end-to-end time on all three
bounded-large slots without competing active runtimes. Falsifiers are any
upper bound at or above 1.03, order effect, fingerprint mismatch, unequal
budget, execution failure, incomplete schedule, or thermal invalidation.
Safety controls are M-only data, immutable seeds/orders/checkpoints, direct
runtime probes, fixed affinity, one named warmup only, no reruns, and selection
committed before candidate exposure.

### DO

Implemented and tested role-specific stdlib solver and SciPy legacy workers,
direct per-library thread limits, full process/runtime telemetry, atomic
checkpoints, and fixed-seed paired bootstrap analysis. An unsupported Ninja
prebuild failed before producing a library and was preserved; the generator
was corrected in a new preregistration commit before data. Built independent
M1/M2 libraries, froze input bundles, ran all C1/C2 observations and the C3
diagnostic, and retained every raw record.

### CHECK

C1 passed all gates: 186/186 eligible observations, worst API upper 1.023451,
worst end-to-end upper 1.023410, exact M1/M2 runtime fingerprints, no order
effect, and no throttle invalidation. C2's six timing bounds passed, but one
eligible process incremented package-throttle counters and therefore failed
the frozen thermal gate without rerun. C3 mapped five four-thread runtime pools
and showed a 1.210205 worst API upper plus an order effect; it was diagnostic
and nonselectable.

### ACT

**ACCEPT C1.** It is the only eligible configuration, so the tie-break is not
reached. Freeze C1, L/M/A identities, the one-shot qualification schedule, and
analysis before candidate timing. No C2 rerun or configuration change is
permitted.

## Cycle 3 — One-shot direct qualification and exact-head review

Pending Cycle 2 frozen-evidence commit.

## Cycle 4 — Complete 27-slot campaign and verified integration

Pending Cycle 3 acceptance.
