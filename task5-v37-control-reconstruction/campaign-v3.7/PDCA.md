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

## Cycle 3 — Reconstruct and validate the controls

### PLAN

Hypothesis: exact f66 source rebuilt with the frozen recipe plus the bootstrap correction is a stable legacy-equivalent control, while M and A remain their exact immutable binaries. Acceptance requires meaningful equality against the original wherever it safely executes, L/M/A equality on targeted V31-026, ten fresh isolated L/V31-026 completions, correct ABI/exports, valid system/SciPy BLAS checks, sanitizers, and a committed/pushed immutable protocol before candidate timing. Any incomplete workload, mismatch, crash, or identity drift blocks qualification.

### DO

L-v3.7 was rebuilt from exact f66 with GCC 15.2.0, GNU ld 2.46, system OpenBLAS 0.3.32, Unix Makefiles, `-march=native`, and the preserved strict flags. M and A reuse their exact verified binaries. Seven deterministic bundles were regenerated; the three qualification input hashes match v3.6 byte-for-byte. Original versus reconstructed legacy was run on six safe cases spanning shapes/scales/sizes. L/M/A were compared on targeted V31-026. Ten additional isolated reconstructed V31-026 processes were executed. Native system-BLAS, SciPy-OpenBLAS, ASan/UBSan, ENOMEM, header, and export checks were performed. The schedule, manifest, identities, statistics, and gates were frozen.

### CHECK

All six safe original/reconstructed comparisons agree in every meaningful field. Targeted L/M/A agree. Ten of ten fresh L-v3.7 V31-026 processes complete with full output and router count one. System-BLAS checks pass 9/9, SciPy-OpenBLAS checks 8/8, valid ASan/UBSan checks 8/8, and the separately valid ENOMEM test passes. Public header SHA-256 is identical and exported symbol-set SHA-256 is `7116ee323800282ee0bfe6fb977f05725087898460624e478454e1aa92829048` for all arms. Runtime fingerprints show SciPy 4, system OpenBLAS 1, MKL/libiomp/libgomp 1 for L and system OpenBLAS 4/libgomp 1 with forbidden runtimes absent for M/A.

The rebuilt L library differs bytewise from v3.6 because its RUNPATH identifies the new build directory; source tree, produced component hashes, public ABI, workload, and meaningful output equivalence are independently established.

### ACT

Accept Cycle 3 contingent on pushing the immutable manifest/protocol branch. Once pushed, execute exactly the committed qualification once; do not amend its schedule or retry an observation.
