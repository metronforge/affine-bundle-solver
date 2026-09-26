# Correctness, portability, and sanitizer matrix

| Gate | M | Branch A (`69728e36`) | Branch B (`b8d22717`) |
|---|---:|---:|---:|
| GCC 15 portable build/workflow | PASS | PASS | PASS |
| GCC 15 `-march=native` build/workflow | baseline reference | PASS | PASS |
| Clang | SKIP: unavailable on host | SKIP: unavailable on host | SKIP: unavailable on host |
| System-BLAS native CTest | baseline reference | 31/31 PASS | 30/30 PASS |
| System-BLAS portable CTest | baseline reference | 31/31 PASS | 30/30 PASS |
| SciPy-OpenBLAS CTest | baseline reference | 31/31 PASS | 30/30 PASS |
| Exact-library harness | reference | 45/45 PASS | not applicable |
| Installed C/C/C++ consumers | reference | PASS | PASS |
| Public headers/exports vs M | — | byte/symbol identical | no public API change from flag/manuscript commits |
| Native ASan/UBSan partition | 10/10 PASS | 11/11 PASS | 10/10 PASS |
| Structural sanitizer partition | reference | 2/2 PASS | 2/2 PASS |
| Stream ENOMEM under valid ASan/LSan | PASS with test-only overlay | PASS | PASS |
| Python sanitizer semantics | 16/16 PASS | 16/16 PASS | 16/16 PASS |
| Sanitized strict PBT batteries | PASS/PASS | PASS/PASS | PASS/PASS |
| Reentrancy/failure injection | PASS | PASS | PASS |
| FP contraction structural gate | not present | PASS plus deliberate failures | PASS plus deliberate failures |

The first sanitizer attempt inherited an ASan preload into host Rust utilities and is retained as `INVALID`, not counted as a pass. Valid runs used clean build directories and valid runtime ordering. The stream-ENOMEM fixture fixes BLAS/OpenMP threads to one because worker-thread FakeStack reservations would otherwise occur after the intentional address-space limit; this is a test-fixture control, not a production semantic change.

The equivalence-orbits battery reported 8,335 checks, exactly 154 registered known-representation cases, and no hard or new failure. Those 154 cases predate v3.3 and are not treated as ordinary passes. Certificate-equivariance reported 2,271 checks and zero failures. M and A's retained GCC-portable stdout/result artifacts were byte-identical.

The direct frozen verifier comparison covered 1,968 calls, 31,160 reconstructed rows, and 1,502,768 entries. It found zero semantic failures and 228 signed-zero-only endpoint differences; absolute-value radius formation makes those endpoints contract-equivalent. Normal finite, subnormal, extreme finite, structural-zero, dense, pivoted, supported rounding, portable/native, and repeated-call cases were covered. Non-finite inputs are rejected by the existing checker contract rather than treated as finite witness data.
