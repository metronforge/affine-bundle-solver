# PDCA 2 — native hotspot attribution

## PLAN

- Hypothesis: the dominant high-level phase is explained by a small set of native functions or kernels rather than allocation syscalls or diffuse overhead.
- Method: prefer `perf` statistical profiling; if prohibited, use low-overhead native-function/kernel interposition and a separate `strace -c` memory-syscall probe.
- Acceptance: one or a small set of functions explains most of V31-027 and has measured call counts consistent with repeated work.
- Falsifier: no stable native concentration, or allocation/copy system calls consume a comparable share.
- Safety: no solver source changes; wrappers preserve ABI and avoid nested double-counting.

## DO

`perf 7.0.14` was attempted and failed with `perf_event_paranoid=4`; the exact failure is retained. The fallback measured five instrumented records already collected per slot and ran `strace 6.19` on V31-027. Symbols were resolved at the C/BLAS/LAPACK boundary.

## CHECK

V31-027 issued 262 `dgeqp3_` calls whose median inclusive total was 255.786 ms, 73.6% of its 347.574 ms instrumented end-to-end time. `dormqr_` was also called 262 times but consumed only 4.936 ms. Other V31-027 kernels were `dgelsy_` 11.569 ms and `dgesvd_` 6.534 ms. V31-025 and V31-026 each issued only four `dgeqp3_` calls.

The `strace` memory probe observed 835 selected syscalls totaling 5.151 ms (580 `mmap`, 153 `munmap`, 75 `brk`, 18 `madvise`, 9 `clone3`), far below the QRCP total. This excludes syscall-level allocation as dominant but cannot exclude allocator-internal or copy cost. Instruction-level self time is unavailable because `perf` is prohibited; the kernel wrappers provide inclusive time, and high-level exclusive generator time is available from cycle 1.

Measured call counts, coupled with the retained source mapping, locate the repetition in `bs_generate_inconsistent_witness`: the compatible-tall fallback scans null directions and calls `left_null_vector_qrcp`, which recopies and refactorizes the same matrix for each direction.

## ACT

Accept. Repeated QRCP in the compatible-tall inconsistent-witness availability fallback is the leading target. Cycle 3 tests whether size and thread sensitivity support computational repetition rather than fixed, memory-syscall, or serialization overhead.
