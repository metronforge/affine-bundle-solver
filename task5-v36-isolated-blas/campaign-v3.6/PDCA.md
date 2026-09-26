# Task-5 v3.6 Ralph quartet

Exactly four cycles are authorized. Each ACT entry is terminal for its cycle and gates the next.

## Cycle 1 — Porting correctness and exact equivalence

### PLAN

Hypothesis: the reviewed unique-row reconstruction and its frozen differential can be overlaid on `bb6c30d` without carrying any old-base FP-gate, sanitizer-infrastructure, or manuscript change, while preserving all numerical, ABI, portability, and safety contracts.

Method: install the frozen differential against unoptimized main and retain RED evidence; overlay only the reviewed algorithm/private hook; retain GREEN and net-diff proofs; then run the full required correctness matrix. Acceptance requires no new correctness, ABI, sanitizer, portability, or publication failure, at least 1,968 calls/31,160 rows/1,502,768 entries, and only explicitly classified signed-zero endpoint differences. Any new unregistered failure falsifies the hypothesis and ends `CORRECTNESS_BLOCKED` before timing.

Safety controls: exact immutable identities, separate worktrees/branches, no change to old Branch A or accepted Task-1 content, strict FP flags/gate, test-only hook, no performance observation during Cycle 1.

### DO

In progress.

### CHECK

Pending.

### ACT

Pending.

## Cycle 2 — BLAS/runtime isolation and A/A selection

Pending Cycle 1 acceptance.

## Cycle 3 — One-shot direct qualification and exact-head review

Pending Cycle 2 acceptance.

## Cycle 4 — Complete 27-slot campaign and verified integration

Pending Cycle 3 acceptance.

