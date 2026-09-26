# Ralph quartet ledger

## Cycle 1 — Reproduce and localize the SIGSEGV

### PLAN

Hypothesis: the v3.6 L/V31-026 crash is deterministic and localizable to a native process phase and library boundary. The smallest sufficient experiment is one exact frozen worker invocation followed by one gdb invocation of the same command. Acceptance requires exit 139 plus a symbolized faulting thread/module/stack; non-reproduction or an unsymbolized stack falsifies it. Safety controls are the immutable v3.6 inputs/binary, fixed affinity and environment, no qualification reuse, and no historical writes.

### DO

The exact v3.6 command was executed with C1 affinity `1,3,6,8`, the original environment, V31-026 bundle, Python 3.13.5, and legacy library SHA-256 `0980f344efa9242077e3eced897cd7a5e56491e12838e1cb1de5636a21f2a67f`. It exited 139 with no stdout/stderr. The identical command was executed once under gdb. Bounded phase probes then separated the SciPy preliminary solve from the solver API.

### CHECK

gdb stopped thread 3 in SciPy-bundled OpenBLAS 0.3.28 at `dgemm_itcopy_HASWELL`, below `inner_thread`, while thread 1 was in `scipy_dgemm_`, `scipy_dgebrd_`, `scipy_dgelsd_`, and `f2py_rout.flapack_dgelsd`. The solver API had not started. A solver-free reproducer with `OPENBLAS_NUM_THREADS=1` followed by a direct threadpoolctl increase to four also exited 139. Keeping one thread completed. Initializing SciPy OpenBLAS at four completed, and loading the legacy solver plus limiting system OpenBLAS to one also completed with status/rank/router `1/192/1`.

Alternative explanations bounded here: the fault does not require the solver library, system OpenBLAS, its ABI, or the candidate; it does require the unsafe upward mutation in this workload. The retained gdb log contains loaded-library mappings and all thread stacks.

### ACT

Accept Cycle 1. Root-cause hypothesis for Cycle 2: initializing SciPy OpenBLAS 0.3.28 with a one-thread pool and then raising it to four through threadpoolctl leaves its `dgelsd`/`dgemm` worker state unsafe for the 192x192 workload. Preserve the active budget but bootstrap the legacy process at four, then directly limit inactive system OpenBLAS to one.

## Cycle 2 — Establish and correct the root cause

### PLAN

Hypothesis: the one-to-four SciPy OpenBLAS mutation is sufficient to predict failure, and initializing the DSO at four while lowering only inactive system OpenBLAS is a semantic-preserving correction. Acceptance requires a RED harness test, GREEN minimal change, failure/non-failure predictions, a negative control, explicit falsification, full V31-026 output, and valid native memory checks. A solver or algorithm change, skipped work, or a merely caught signal falsifies acceptance.

### DO

The RED test required the legacy bootstrap environment to expose its active four-thread budget and failed because `task5v37.runtime` did not exist. The minimal implementation adds `bootstrap_environment`, setting the shared OpenBLAS bootstrap variable to `max(system, scipy)` while retaining all v3.6 direct per-DSO limits. A v3.7 protocol records the bootstrap setting and preserves child stderr/return codes on failure. The original and reconstructed configurations were probed as shown in `ROOT-CAUSE.md`. The exact f66 source was rebuilt with the frozen compiler, native flags, and system BLAS. Normal and ASan/UBSan native partitions were run.

### CHECK

The two initial tests and the frozen-schedule test pass; the complete v3.6 plus v3.7 harness suite is 19/19. The exact reconstructed worker returns complete UNIQUE/rank-192 output with router count one. Eight valid ASan/UBSan native tests pass. The intentional address-space-limited ENOMEM test fails before test logic under ASan because ASan cannot map TLS/fake-stack state, so it is invalid in that partition; it passes in the normal build. Header hashes and exported ABI agree. The gdb route and solver-free route independently identify the same SciPy pool-transition cause.

Uncertainty: the precise internal OpenBLAS allocation invariant is not observable without rebuilding third-party OpenBLAS with debug symbols, but it is unnecessary to distinguish because the causal interface action is isolated and fully predicts the outcome.

### ACT

Accept Cycle 2. Use a newly rebuilt, explicitly labeled L-v3.7 binary from exact f66 source plus the v3.7 bootstrap correction. Do not call it the original v3.6 control and do not alter v3.6 evidence.
