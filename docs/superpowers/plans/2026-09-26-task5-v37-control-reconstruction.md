# Task 5 v3.7 Control Reconstruction Implementation Plan

> **For Codex:** Execute this plan with the executing-plans task workspace. The user-supplied brief is the approved design and fixes all scientific gates.

**Goal:** Diagnose the v3.6 L/V31-026 SIGSEGV, reconstruct and independently validate immutable L/M/A controls, and run exactly one pre-registered three-slot qualification of unchanged candidate `dd30ef900ff7f48d4fe97e79aae94b7e64c48741`.

**Architecture:** Extend the existing v3.6 role-isolated Python harness on a separate evidence branch. Preserve the v3.6 campaign byte-for-byte. Add a versioned v3.7 diagnostic/control layer and new immutable campaign directory. Treat each Ralph cycle as one bounded task with a persisted PLAN/DO/CHECK/ACT record.

**Tech Stack:** Python 3.13, pytest, ctypes, CMake/GCC, gdb, ELF/binutils, threadpoolctl, NumPy/SciPy, git/GitHub CLI.

---

### Task 1: Reproduce and localize the v3.6 SIGSEGV

**Files:**
- Create: `task5-v37-control-reconstruction/campaign-v3.7/RECONCILIATION.md`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/PDCA.md`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/evidence/cycle-01-*`

1. Persist exact identities, retained-v3.6 checksum verification, worktree/branch/stash state, and candidate bundle checksum.
2. Run one exact frozen V31-026 legacy command and capture status/stderr.
3. Run the same construction under gdb; capture faulting thread/module/function/stack.
4. Inventory `ldd`, `readelf`, symbols, BLAS/LAPACK/OpenMP runtimes, hashes, integer ABI, and loader paths.
5. Use phase markers and a bounded minimal reproducer only as needed to localize the failure.
6. Compare observations with the preregistered Cycle 1 hypothesis and persist ACT.

### Task 2: Establish and correct the root cause

**Files:**
- Create: `task5v37/diagnostics.py`
- Create: `tests/test_v37_control_reconstruction.py`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/evidence/cycle-02-*`
- Update: `task5-v37-control-reconstruction/campaign-v3.7/PDCA.md`

1. Write a failing regression test for the demonstrated infrastructure or legacy-control defect.
2. Change one causal factor at a time; include a negative control and explicit falsification.
3. Implement only the minimal semantic-preserving reconstruction correction.
4. Verify original workload completion, output completeness, focused correctness, and valid sanitizers/memory diagnostics.
5. Persist primary and independent corroborating evidence plus Cycle 2 ACT.

### Task 3: Reconstruct, validate, and pre-register immutable controls

**Files:**
- Create: `task5v37/{__init__,worker,protocol,analysis}.py`
- Update: `tests/test_v37_control_reconstruction.py`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/{manifest.json,PROTOCOL.md,CONTROL-IDENTITIES.json,SEMANTIC-EQUIVALENCE.json}`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/evidence/cycle-03-*`
- Update: `task5-v37-control-reconstruction/campaign-v3.7/PDCA.md`

1. Freeze L-v3.7, M-v3.7, and unchanged A-v3.7 source/build/runtime/binary identities.
2. Validate L-original versus L-v3.7 wherever original is safe across bounded small, medium, edge, and targeted V31-026 cases.
3. Verify meaningful fields, status/rank/certificate, full workload, ABI/exports, router invariant, BLAS partitions, and sanitizers.
4. Run at least ten fresh isolated L-v3.7 V31-026 processes without failure.
5. Test manifest/protocol invariants first, then freeze schedule, trials, affinity/thread policy, failures, statistics, and gates.
6. Commit and push the immutable manifest before any qualification timing; record commit and manifest SHA-256.

### Task 4: Execute one-shot qualification and close evidence

**Files:**
- Create: `task5-v37-control-reconstruction/campaign-v3.7/timings/qualification.json`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/analysis/qualification.json`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/INDEPENDENT-REVIEW.md`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/FINAL-REPORT.md`
- Create: `task5-v37-control-reconstruction/campaign-v3.7/SHA256SUMS`
- Update: `task5-v37-control-reconstruction/campaign-v3.7/PDCA.md`

1. Execute the committed manifest once, retaining all raw records before analysis and performing no selective reruns.
2. Check completeness, meaningful-field agreement, router count, runtime policy, RSS, thermal state, order effects, variance, and exact statistics.
3. Obtain an independent fresh-context review of manifest compliance, arithmetic, record completeness, and checksums.
4. Run final focused/full harness verification and `git diff --check`.
5. Persist exactly four completed PDCA cycles, final report, exact commands, and comprehensive SHA-256 inventory.
6. Commit and push the analysis/evidence branch. Do not create a solver PR, merge, or 27-slot campaign.
