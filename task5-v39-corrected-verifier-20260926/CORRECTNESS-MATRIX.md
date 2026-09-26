# Fresh correctness matrix

All results below use newly built artifacts for `40fe4d0`; no v3.7 binary or
timing hash is treated as qualifying evidence.

| Gate | Result |
|---|---|
| GCC native system-BLAS CTest | 31/31 pass |
| GCC portable system-BLAS CTest | 31/31 pass |
| GCC portable SciPy-OpenBLAS CTest | 31/31 pass |
| Clang portable | unavailable locally; not counted as passing; exact-head CI required |
| GCC native L control CTest | 25/25 pass |
| GCC native M control CTest | 30/30 pass |
| Valid native ASan/UBSan/LSan partition | 11/11 pass |
| Valid Python-loaded ASan/UBSan partition | 17/17 pass with leak detection disabled only for Python runtime compatibility |
| ENOMEM outside incompatible ASan resource limits | 2/2 pass |
| Installed C consumer | pass with `LD_LIBRARY_PATH` unset |
| Installed certified C consumer | pass with `LD_LIBRARY_PATH` unset |
| Installed certified C++ consumer | pass with `LD_LIBRARY_PATH` unset |
| Strict certificate PBT | 2,271 checks, zero failures |
| Strict equivalence-orbits PBT | 8,335 checks; exactly 154 frozen known-representation cases; zero new/hard failures |
| Original/corrected overflow regression | RED on `dd30ef9`, GREEN on `40fe4d0` |
| Ordinary row differential | 1,968 calls, 31,160 rows, 1,502,768 entries; 228 signed-zero-only endpoint differences; zero failures |
| Allocation-failure injection | allocation positions 1..5 return 3,4,6,6,6; rounding restored; no leaks |
| Correct-bootstrap L/M/A V31-026 comparison | complete and meaningful-field equal |
| Correct-bootstrap L stability | 10/10 complete, router count one |
| Public headers and exported symbols | unchanged and identical across L/M/A |
| Strict FP contraction | pass; candidate verifier contains no FMA instructions |
| `git diff --check` | pass |

The initial standalone v3.7 validation helper was also exercised as a
diagnostic. It constructs the intended environment but omits `env=` when
launching the subprocess, so that run inherited an uncontrolled thread state
and is invalid. It is retained under `evidence/invalid/`, is not a performance
observation, and is not counted in any gate. The v3.9 validator has a regression
test proving that the environment is propagated, and the actual protocol runner
already used the correct bootstrap implementation.
