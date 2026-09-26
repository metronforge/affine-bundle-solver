# V31-026 legacy SIGSEGV root cause

## Finding

The v3.6 legacy process initialized SciPy OpenBLAS 0.3.28 with
`OPENBLAS_NUM_THREADS=1`, then `threadpoolctl` raised that DSO to the active
four-thread budget. On the 192x192 `gelsd` path, a newly activated worker
faulted in `dgemm_itcopy_HASWELL`. This happened in the preliminary SciPy solve,
before `bsolve_certified_diag_api` began.

This is a harness/runtime bootstrap defect, not a solver or candidate defect.
The correction is to initialize all OpenBLAS DSOs at the maximum OpenBLAS
budget required by the role. The existing direct per-DSO policy then retains
SciPy OpenBLAS at four and lowers the inactive system OpenBLAS DSO to one.
No algorithm, input, tolerance, workload boundary, solver binary, or candidate
behavior is changed.

## Predictions and results

| Probe | SciPy initial/direct threads | Solver loaded | Result |
|---|---:|---:|---|
| exact v3.6 V31-026 | 1 → 4 | yes | SIGSEGV 139 |
| minimal solver-free negative control | 1 → 4 | no | SIGSEGV 139 |
| one-thread control | 1 → 1 | yes | completes |
| explicit falsification | 4 → 4 | no | completes |
| reconstructed exact worker | 4 → 4; system 4 → 1 | yes | completes; UNIQUE/rank 192/router 1 |

The solver-free failure rules out solver API execution, system OpenBLAS,
candidate code, public ABI, and mixed-symbol interposition as necessary causes.
The initial-four success falsifies the alternative that SciPy `gelsd`, the
input, four active threads, or the fixed affinity is intrinsically defective.

## Native evidence

Faulting thread: LWP 653211 (gdb thread 3).

Faulting DSO/function:
`libscipy_openblas-68440149.so` / `dgemm_itcopy_HASWELL`.

Calling thread stack:
`scipy_dgemm_ → scipy_dgebrd_ → scipy_dgelsd_ → f2py_rout.flapack_dgelsd`.

Full backtrace, registers, shared libraries, and mappings:
`evidence/cycle-01-gdb-exact.log`.

SciPy symbols are prefixed (`scipy_dgemm_`, `scipy_dgelsd_`,
`scipy_openblas_set_num_threads`); system OpenBLAS symbols are unprefixed.
Both use ELF64 x86-64 LP64 interfaces. The loaded MKL interface is explicitly
`libmkl_intel_lp64.so.2`. Public certified API headers are byte-identical across
L/M/A (SHA-256
`2172d6584e9f3c4518a0d7478ddc70fa8c02a5ea78bf9105d57f24265fa8595b`).

## Memory diagnostics

Eight native ASan/UBSan tests passed. The separate intentional ENOMEM fixture
cannot be validly combined with ASan because its `RLIMIT_AS` prevents ASan from
mapping its own fake stack/TLS; it was recorded as invalid, not passing. The
same ENOMEM fixture passed in the normal instrument-free build. This partition
matches the source comment requiring the ENOMEM fixture to remain separate.
