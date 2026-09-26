# Task-5 v3.6 Isolated-BLAS Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port only the verified unique-row reconstruction optimization onto `bb6c30d`, select a reliable role-isolated BLAS configuration using M/M data, qualify the candidate once, and merge it only after exact-head review, CI, and the complete 27-slot campaign pass.

**Architecture:** Keep solver code and performance evidence on separate branches/worktrees. The candidate branch contains only the row algorithm, its private test hook, and frozen differential coverage; the harness branch contains the immutable protocol, role-specific workers, analysis, checkpoints, and evidence. Input materialization and correctness oracles remain outside timed worker regions; solver workers load no NumPy/SciPy stack, while legacy workers isolate SciPy/MKL from the solver's system OpenBLAS and report direct runtime fingerprints.

**Tech Stack:** C11, CMake/CTest, Python 3.13, `ctypes`, NumPy/SciPy only in input/oracle and legacy-control processes, pytest, threadpoolctl/runtime APIs, `/proc` and sysfs telemetry, Git/GitHub CLI.

**Spec:** User-supplied “Task-5 v3.6 — isolate BLAS runtimes, qualify the row-verifier optimization, and close Task-5” brief dated 2026-09-26.

## Global Constraints

- Use exactly four PDCA cycles and finish with exactly one prescribed terminal verdict.
- Treat `bb6c30d03191a92695b16d21581bfea6dce9942e` / tree `e621eef836c2e6edd633c03d657cc582e0e04344` as the only candidate base.
- Preserve public API/ABI, numerical contract, independent verification, router behavior, one router execution, tolerances, and meaningful fields.
- Never alter the old candidate branch, historical evidence, preserved V3 workspace, or stash state; never force-push or rewrite history.
- Freeze runtime selection and qualification protocols before exposing candidate timings; never selectively exclude or rerun observations.
- Push only the authorized candidate and harness branches; never push directly to main.
- Merge only by one-parent squash after all gates pass and after re-verifying unchanged base/head/tree/CI identities.

## Review Focus

- A solver-role worker must not map SciPy OpenBLAS, MKL, libiomp5, or another competing active pool; tests reject forbidden mapped runtimes.
- A legacy-role worker must give the selected budget to SciPy/MKL and explicitly limit system OpenBLAS to one; tests reject swapped or unequal effective budgets.
- Signed-zero-only endpoint differences must be classified separately and no downstream sign-sensitive observer may consume them before `fabs`; the frozen row differential and source audit cover this.
- Interrupted datasets must retain every completed trial and resume only missing scheduled work without rerunning an eligible observation; checkpoint tests pin this behavior.
- Analysis must fail closed on missing slots, fingerprint mismatches, thermal invalidation, duplicate trials, router counts other than one, or changed input hashes.

---

### Task 1: Cycle 1 candidate port and exact-equivalence evidence

**Files:**
- Modify: candidate `CMakeLists.txt`, `.github/workflows/ci.yml`, `src/status_certificate.c`
- Create: candidate `tests/test_unique_verifier_rows.c`
- Create: harness `task5-v36-isolated-blas/campaign-v3.6/{RECONCILIATION.md,PDCA.md}`
- Create: harness `task5-v36-isolated-blas/campaign-v3.6/evidence/cycle-01/`

**Interfaces:**
- Consumes: old-base commits `7e6c82e` and `0b9f9cf`, corrected source head `69728e3`, and accepted Task-1 main.
- Produces: a candidate whose net production/test delta is the old row-verifier delta overlaid on main with Task-1 duplicates excluded.

- [ ] Record full base/source/parent/tree/worktree/stash/PR/CI identities and categorized diffs before candidate edits.
- [ ] Apply only frozen differential test registration/source and run it against unoptimized main; retain the expected RED log (no observed optimized rows).
- [ ] Overlay the reviewed row algorithm and private hook, excluding FP-gate, ENOMEM, manuscript, and other Task-1 changes.
- [ ] Run the focused test and retain GREEN output proving at least 1,968 calls, 31,160 rows, 1,502,768 entries, exact error equality, and separately counted signed-zero-only endpoints.
- [ ] Audit every downstream use for sign-sensitive behavior and persist the result.
- [ ] Prove the final candidate patch matches the authorized old algorithm/test patch modulo already integrated Task-1 context; run `git diff --check`.
- [ ] Commit with Conventional Commit history.

### Task 2: Cycle 1 complete correctness, safety, ABI, and portability matrix

**Files:**
- Create: harness `task5-v36-isolated-blas/campaign-v3.6/CORRECTNESS-MATRIX.md`
- Create: harness `task5-v36-isolated-blas/campaign-v3.6/evidence/cycle-01/*`

**Interfaces:**
- Consumes: exact candidate head from Task 1.
- Produces: a fail-closed Cycle-1 decision allowing performance work only when no new unregistered failure exists.

- [ ] Build and run full native CTest with system BLAS and SciPy OpenBLAS.
- [ ] Run exact-library harness, valid ASan/UBSan partitions, ENOMEM/failure injection, reentrancy/concurrency, installed C/C++ consumers, ABI/header comparisons, GCC portable/native, and Clang portable when available.
- [ ] Run strict FP gate, both strict PBT batteries, eight claim reproductions, performance inventory, artifact/publication audits, manuscript build, and `git diff --check`.
- [ ] Classify passes, registered pre-existing failures, skips, invalid environments, and new failures separately; stop `CORRECTNESS_BLOCKED` on any new blocker.
- [ ] Persist Cycle-1 CHECK/ACT and commit the evidence branch.

### Task 3: Cycle 2 role-isolated runtime harness and frozen calibration

**Files:**
- Create: `task5v36/{bundle.py,ffi.py,runtime.py,worker.py,protocol.py,analysis.py,campaign.py,__init__.py}`
- Create: `tests/test_v36_isolated_blas.py`
- Create: `task5-v36-isolated-blas/campaign-v3.6/{manifest.json,PROTOCOL.md,COMMANDS.md,ENVIRONMENT.json}`
- Create: `task5-v36-isolated-blas/campaign-v3.6/{timings,analysis,evidence/cycle-02}/`

**Interfaces:**
- Produces: `write_bundle(slot, path)`, `run_worker(role, bundle, library, runtime_policy)`, `run_dataset(schedule, checkpoint)`, `aa_decision(records)`, and immutable runtime fingerprints.
- Runtime policy encodes active runtime, active/inactive thread counts, fixed CPU set, allowed/forbidden mapped libraries, and runtime-specific setters/probes.

- [ ] Write failing tests for C1/C2/C3 schedules, deterministic balanced order, runtime allowlists/budgets, complete telemetry, fail-closed fingerprints, atomic no-rerun checkpoints, and equality/2%/4%/improvement/order-effect analyses.
- [ ] Run focused pytest and retain RED output.
- [ ] Implement stdlib/ctypes solver workers, SciPy-only legacy workers, untimed bundle/oracle preparation, direct runtime setters/probes, `/proc`+sysfs telemetry, and checkpointed orchestration.
- [ ] Run focused and full pytest; retain GREEN output.
- [ ] Commit the manifest, trial counts, warmups, orders, seeds, CPU sets, commands, exclusions, 100,000-resample method, selection rule, terminal gates, C3 diagnostic count, 30-second worker limit, and 30-minute campaign envelope before timing.
- [ ] Build two independent M libraries, run C1/C2 M/M (one warmup + 31 eligible pairs per large slot) and diagnostic C3, retaining all raw/checkpoint data.
- [ ] Apply the frozen eligibility and selection rule exactly; if neither C1 nor C2 qualifies, seal checksums/report and stop `MEASUREMENT_PROTOCOL_UNRELIABLE` without candidate timing.
- [ ] Commit selected runtime identity and final qualification protocol before Cycle 3.

### Task 4: Cycle 3 one-shot L/M/A qualification, review, PR, and exact-head CI

**Files:**
- Create: campaign `timings/qualification.json`, `analysis/qualification.json`, `timings/dense-secondary.json`
- Create: campaign `INDEPENDENT-REVIEW.md`, `PR-CI.md`, Cycle-3 evidence/logs

**Interfaces:**
- Consumes: selected frozen runtime, frozen schedule, L/M/A immutable libraries and bundles.
- Produces: a single sealed pre-PR decision and, only if passing, an independently reviewed draft PR head.

- [ ] Run exactly one fresh L/M/A dataset for V31-025/026/027 (one warmup + 31 eligible paired observations) and atomically seal it.
- [ ] Report M/A API+E2E effects, direct L/A per-slot/geometric-mean speedups and intervals, M/A V31-025 one-sided upper bound, RSS, runtime fingerprints, thermal state, meaningful fields, and router counts.
- [ ] Evaluate all eleven pre-PR gates; on failure, do not expose another candidate/configuration and stop `CANDIDATE_NOT_QUALIFIED`.
- [ ] Freeze inputs then run the one allowed non-gating dense secondary check.
- [ ] Request fresh-context exact-head review covering numerical equivalence, directed rounding, signed zero, aliasing, FP flags/gate, ENOMEM, reentrancy, and attribution.
- [ ] Resolve blocking findings test-first; if timed code changes, invalidate and run at most one fully preregistered replacement qualification.
- [ ] Push candidate, open draft PR titled `perf: accelerate strict unique-row verification`, verify PR head equals reviewed head, and wait for all required exact-head CI; stop `REVIEW_OR_CI_BLOCKED` on failure.

### Task 5: Cycle 4 immutable 27-slot campaign, integration, and final evidence

**Files:**
- Create: campaign `manifest-27.json`, `execution-ledger.jsonl`, `timings/full-campaign.json`, `analysis/full-campaign.json`
- Create: campaign `MERGE-VERIFICATION.json`, `FINAL-REPORT.md`, `SHA256SUMS`, Cycle-4 evidence/logs

**Interfaces:**
- Consumes: exact reviewed, CI-green draft PR head and the frozen selected runtime.
- Produces: the terminal campaign decision and, only on success, a verified squash merge.

- [ ] Generate the immutable v3.6 manifest from the original 27 mathematical slots and verify regenerated matrix/RHS hashes against frozen inputs.
- [ ] Run one excluded warmup and five eligible balanced L/A observations per slot on the exact PR head, retaining every trial/checkpoint and continuing past safe individual failures.
- [ ] Require all 27 eligible slots, direct geometric mean ≥1.5x, no slot >10% slower, 30-second large-worker limit, correctness/meaningful agreement, router count one, RSS ≤10%, thermal/fingerprint validity, 30-minute envelope, and checksum integrity.
- [ ] On failure, leave the PR draft and stop `CAMPAIGN_FAILED_NOT_MERGED`.
- [ ] Reverify review applicability, exact-head CI, unchanged `origin/main`, PR head/tree, then mark ready and squash-merge; reconcile state before any uncertain retry.
- [ ] Verify one parent equal to `bb6c30d`, Conventional title, merged tree equal to reviewed PR tree, `origin/main` at squash commit, and linear first-parent history; emit `MERGE_BLOCKED` or `MERGE_INVALID` if applicable.
- [ ] Complete all four PDCA entries, final report, exact commands, and SHA-256 inventory; push only the harness evidence branch and end `SUCCESS`.

