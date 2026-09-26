# Cycle-1 correctness, sanitizer, ABI, and portability matrix

Exact candidate: `dd30ef900ff7f48d4fe97e79aae94b7e64c48741`  
Tree: `a89ce2def1fc1b2ef4644cc4d17f13c533b099b7`  
Parent: authorized main `bb6c30d03191a92695b16d21581bfea6dce9942e`

| Gate | Result | Evidence |
|---|---:|---|
| Frozen row differential RED | EXPECTED FAIL | `candidate-red-ctest.log`: 1,968 calls saw no optimized rows |
| Frozen row differential GREEN | PASS | 1,968 calls; 31,160 rows; 1,502,768 entries; 228 signed-zero-only endpoints; 0 failures |
| GCC/system BLAS portable full CTest | 31/31 PASS | `system-portable.log` |
| GCC/system BLAS native full CTest | 31/31 PASS | `system-native.log` |
| GCC/SciPy OpenBLAS native full CTest | 31/31 PASS | `scipy-native.log` |
| Exact-library baseline/candidate harness | 57/57 PASS | `exact-library-harness.log` |
| ASan+UBSan native/leak partition | 11/11 PASS | `asan-native-leaks.log`; includes row differential |
| ASan+UBSan structural partition | 5/5 PASS | `asan-structural.log`; strict/fail-closed FP gates pass |
| ASan+UBSan stream ENOMEM | 1/1 PASS | `asan-stream-enomem.log` |
| ASan+UBSan Python semantics | 16/16 PASS | `asan-python-semantics.log` |
| Sanitized strict PBT | PASS/PASS | 8,335 and 2,271 checks in `asan-*-valid.log` |
| ENOMEM/failure injection | PASS | stream atomicity/retry and six reusable-QRCP allocation failures in full CTest |
| Reentrancy/concurrency | PASS | 64 calls across four threads in full CTest; verifier has no mutable static state |
| Installed C/C++ consumers | 3/3 PASS | clean `/tmp` execution with `LD_LIBRARY_PATH` unset in `install-consumer-valid.log` |
| Public headers | IDENTICAL | `abi-public-header.log` |
| Exported ABI | IDENTICAL | all three shared-library export sets in `abi-public-header.log` |
| GCC portable build.sh path | PASS | `build-sh-gcc-portable.log` |
| GCC native build | PASS | native CMake build and 31/31 CTest |
| Clang portable | SKIP locally | executable unavailable; mandatory exact-head CI gate retained |
| Strict FP-contraction gate | PASS | ordinary, native, SciPy, and sanitized structural CTests |
| Equivalence-orbits strict PBT | PASS with registered cases | 8,335 checks; exactly 154 known-representation cases; no hard/new failure |
| Certificate-equivariance strict PBT | PASS | 2,271 checks; zero failures |
| Eight manuscript claim reproductions | 8/8 PASS | `paper-claims.log` |
| Performance claim inventory | PASS | coverage complete in `performance-inventory.log` |
| Artifact hash audit | PASS | both immutable reference artifacts in `performance-artifact-hashes.log` |
| Publication-readiness audit | PASS | ready=true, no reasons in `publication-audit.log` |
| Manuscript build | PASS | 27-page PDF in `manuscript-build.log` |
| `git diff --check` | PASS | empty `git-diff-check-final.log` |
| Candidate worktree | CLEAN | `environment-summary.log` |

## Classifications

- Exact equality: every reconstructed `evec` entry is bit-identical to the frozen legacy kernel across all 1,502,768 comparisons.
- Contract-equivalent differences: 228 raw interval endpoints differ only in the sign of exact zero; production applies `fabs` before any observable use, and the resulting `evec` values are exact-equal.
- Registered pre-existing failures: exactly 154 `known-representation` affine-translation cases in the 8,335-check equivalence battery. There is no hard/new property failure.
- Skips: local Clang portable only, because no `clang` executable is installed. This remains an exact-head CI requirement, not a pass.
- Invalid environments retained but not counted: the first sanitized PBT command pointed a battery that hardcodes repository-root libraries at an absent build-tree path; the valid CI-equivalent `build_sanitized.sh` rerun passed. The first installed-consumer run inherited a trailing-empty `LD_LIBRARY_PATH`, loaded the repository-root ASan/SciPy artifact from CWD, and was invalid; the clean `/tmp` rerun loaded the installed system-OpenBLAS library and passed all three consumers.
- Compiler warnings: the strict scan contains only pre-existing compact-source indentation/unknown-pragma warnings; the candidate's new row-pass code adds no warning and all builds succeeded.
- New failures: none.

## Decision

Cycle 1 is accepted. The candidate preserves correctness, directed-rounding semantics, ABI, sanitizer validity, failure behavior, reentrancy, portability on available host compilers, and publication state. Performance work is authorized under the still-unexposed candidate timing constraint.

