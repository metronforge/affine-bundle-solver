# Task-5 v3.9 Corrected Verifier Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild and qualify the exact corrected verifier candidate, execute the focused and canonical campaigns once, and squash-merge only after every registered gate passes.

**Architecture:** Keep the immutable two-commit candidate on the exact integration branch and keep protocols, preregistrations, raw observations, analyses, and audit records on a separate evidence branch. Reuse v3.7 only as protocol code and frozen recipes; bind all claims to newly rebuilt binaries and newly generated records.

**Tech Stack:** C11, CMake/CTest, GCC/Clang, ASan/UBSan, Python 3.13, NumPy/SciPy, pytest, ctypes, threadpoolctl, Git/GitHub CLI.

**Spec:** `docs/superpowers/specs/2026-09-26-task5-v39-corrected-verifier.md`

## Global Constraints

- Candidate `40fe4d015d988ce0ea9c6133c8715b424bba51d7` and its history are immutable.
- Base must remain `bb6c30d03191a92695b16d21581bfea6dce9942e` until squash integration.
- Preserve historical v3.6/v3.7/v3.8 evidence, worktrees, bundles, branches, and stash state.
- No reused timing or binary hash, selective rerun/exclusion, force-push, merge commit, release, pre-merge deletion, or second optimization.
- After a verified merge, clean only the v3.9 worktrees and temporary build directories created by this task; preserve remote evidence and all pre-existing historical workspaces.
- Stop at the first terminal gate specified by the user.

## Review Focus

- Non-finite reconstruction, solution-norm, residual, perturbation, source-norm, and quotient bounds must fail closed with positive infinite `eta_up`.
- All early exits after rounding-state capture must restore the caller rounding mode, including allocation failure.
- The row-wide kernel must preserve packed-LU indexing, directed evaluation order, signed-zero semantics, partial-row behavior, and the no-contraction contract.
- Every timing record must bind to the fresh library and input hashes, one registered schedule row, the required runtime fingerprint, and exactly one candidate router execution.
- Canonical accounting must include all 27 slots and must never reuse or silently replace a focused or historical observation.

---

### Task 1: Reconciliation and immutable candidate review

**Files:** Create campaign reconciliation and review records under `task5-v39-corrected-verifier-20260926/`.

**Interfaces:** Produces the exact source identities and a review verdict consumed by every later task.

- [ ] Record local/remote/worktree/branch/stash/PR/history identities and historical checksum verification.
- [ ] Audit the cumulative and correction diffs against every review-focus condition.
- [ ] Run independent overflow regressions red at `dd30ef9` and green at `40fe4d0`, including positive/negative overflow and rounding restoration.
- [ ] Stop `REVIEW_BLOCKED` on any Critical or Important finding; otherwise commit the review evidence.

### Task 2: Fresh builds, identities, and correctness matrix

**Files:** Create fresh L/M/A and sanitizer build directories plus campaign identity/correctness records.

**Interfaces:** Produces the only binaries and hashes eligible for both campaigns.

- [ ] Rebuild L from `f66cd87`, M from `bb6c30d`, and A from `40fe4d0` in new directories with the validated v3.7 runtime construction.
- [ ] Record source/tree/parent, toolchain, flags, BLAS/OpenMP, ABI/loader, headers, symbols, binary/DSO hashes, thread/runtime/affinity, and input identities.
- [ ] Run all requested portable/native/SciPy/Clang, CTest, sanitizer, ENOMEM, consumer, PBT, equivalence, differential, router, ABI, strict-FP, and diff checks.
- [ ] Stop `CANDIDATE_INVALID` on a new hard failure; otherwise commit the complete matrix.

### Task 3: v3.9 harness and focused preregistration

**Files:** Create `task5v39/`, focused harness tests, and immutable focused protocol/manifest/schedule/commands/identity files.

**Interfaces:** Produces deterministic no-rerun orchestration and fail-closed focused/canonical analyses.

- [ ] Add failing tests for new campaign identity, balanced schedules, exact accounting, fresh-hash binding, focused gates, canonical gates, and atomic checkpoint behavior.
- [ ] Implement the smallest v3.9 wrapper/analysis code needed; run focused and full harness tests green.
- [ ] Regenerate authoritative inputs, verify their hashes, generate new seeds/schedule, and commit the focused preregistration.
- [ ] Push, fetch, and verify the remote preregistration commit/tree/file hashes before timing.

### Task 4: One-shot focused qualification

**Files:** Create focused raw checkpoint, analysis, audit, and summary records.

**Interfaces:** A passing decision authorizes Task 5; an incomplete or failed decision terminates.

- [ ] Execute the registered 288-process schedule exactly once and retain every warmup and eligible record atomically.
- [ ] Recompute all statistics and verify correctness/router/RSS/thermal/thread/affinity/order/variance/checksum gates.
- [ ] Stop `FOCUSED_INCOMPLETE` for any missing/invalid scheduled process or `FOCUSED_NOT_QUALIFIED` for a complete failed gate.
- [ ] Commit and push the sealed focused evidence.

### Task 5: Canonical preregistration and 27-slot campaign

**Files:** Create canonical inputs, manifest, ledger, schedule, protocol, raw checkpoint, analysis, and summary.

**Interfaces:** A passing canonical decision authorizes integration.

- [ ] Reconstruct and verify the authoritative 27-slot contract and all input hashes.
- [ ] Commit, push, fetch, and hash-verify the canonical preregistration before timing.
- [ ] Execute all 324 registered L/A processes exactly once within the frozen limits and preserve raw records atomically.
- [ ] Regenerate per-slot/aggregate statistics, verify every frozen gate, and stop with the specified canonical terminal verdict on block, incompleteness, or non-qualification.

### Task 6: Independent audit and immutable evidence closure

**Files:** Create independent audit, inventory, `SHA256SUMS`, and final campaign report.

**Interfaces:** Produces the evidence head bound to the exact candidate and fresh binaries.

- [ ] Audit raw data in fresh context, recompute statistics, and verify complete slot/trial accounting and identities.
- [ ] Generate and verify `SHA256SUMS`; commit, push, fetch, and verify the remote evidence tree.

### Task 7: PR, exact-head CI, squash merge, and post-merge verification

**Files:** Update PR/CI and merge-verification evidence only.

**Interfaces:** Produces exactly one terminal integration verdict.

- [ ] Re-fetch and verify unchanged base, exact integration head/tree, clean worktree, and campaign bindings; push the exact candidate branch.
- [ ] Open one PR with the required title/body, confirm exact head, and wait for every required exact-head CI/review gate.
- [ ] Reverify base/head/tree/evidence and squash-merge only; verify one parent, expected parent/tree/title, origin/main, and linear first-parent history.
- [ ] Run focused post-merge build/correctness smoke without rerunning performance and record the terminal report.
- [ ] After all evidence is safely pushed and merge verification is complete, remove the new v3.9 local worktrees and temporary build directories and record exactly what was cleaned.
