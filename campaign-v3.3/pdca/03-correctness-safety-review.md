# PDCA 3 — correctness, safety, and exact-head review

## PLAN

Hypothesis: the invocation-local reusable QRCP state preserves the public and numerical contract without ownership, leak, ABI, reentrancy, compiler, or BLAS regressions. Critical or Important independent-review findings, sanitizer findings, a changed public symbol/header, a meaningful-field differential, or a QRCP call-count regression were blocking falsifiers.

## DO

The exact solver head `87b239745f38514286a7a9d29f11b1a59f5b8245` (tree `86dd1f677664160e40de72c0121e72fa5e54a83b`) was exercised with GCC native and portable builds, system BLAS and SciPy OpenBLAS, ASan+UBSan, stream allocation failure, installed consumers, the Python differential harness, strict property tests, and a four-thread reentrancy regression. A fresh-context reviewer independently inspected the reuse invariant, owned state, all LAPACK arguments, pivot/rank semantics, cleanup paths, public ABI, and exact call-count evidence.

Two failed diagnostic probes were retained rather than hidden: the local machine has no `clang` executable, and an installed-consumer run launched from the sanitized build directory inherited a trailing-empty `LD_LIBRARY_PATH` that resolved local sanitizer libraries. The consumer suite passed when repeated from `/tmp` with `LD_LIBRARY_PATH` unset; the exact-head GitHub CI supplies the independent Clang gate.

## CHECK

- Native system-BLAS CTest: 28/28.
- Portable system-BLAS CTest: 28/28.
- SciPy OpenBLAS CTest: 28/28.
- ASan+UBSan native/leak subset: 14/14.
- Stream ENOMEM subset: 2/2.
- Sanitized Python semantic snapshots: 12/12.
- Harness suite: 31 passed.
- Strict property/differential checks: 10,606; no new failures (the 154 pre-existing representation cases remained classified as known failures).
- Portable/native comparison: 30 deterministic evaluations, semantic agreement; maximum residual difference `5.126e-14`.
- System/SciPy BLAS comparison: 30 deterministic evaluations, semantic agreement; maximum residual difference `2.598e-14`.
- Installed consumers: 3/3 with no missing dynamic dependencies.
- ABI: public header hashes and exported symbol sets are byte-for-byte unchanged.
- Reentrancy: 64 calls across four concurrent threads passed.
- Target-domain QRCP count: 2; complete supported call: 6; router executions: 1.

The independent exact-head review reported zero Critical, Important, or Minor findings and approved the change. It confirmed that DGEQP3 receives fixed `M=m`, `N=n`, `LDA=m`, a zero JPVT seed, and owned input; DORMQR receives `m x 1`, `K=min(m,n)`, `LDA=LDC=m`, adequate queried workspace, and never mutates the stored reflector state.

## ACT

Accept locally and enter the solver merge gate. Push the reviewed head, require all exact-head CI jobs to pass, fetch and revalidate the base immediately before a squash merge, and bind Cycle 4 only to the verified immutable squash commit. No official performance timing is authorized before that sequence completes.
