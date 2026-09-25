# Native LSan boundary for CI

The failed CTest artifacts from [run 36176732134](https://github.com/metronforge/affine-bundle-solver/actions/runs/36176732134) were inspected before changing the sanitizer partition. All ten Python failures in the `remaining` partition, the Python DGESDD semantic failure, and the Python stream-storage failure occurred after their test bodies had completed without a Python traceback or assertion failure. Some printed an explicit `PASS`; absence of a traceback alone is not a replacement for the new passing CI run. Their retained leak stacks begin in CPython `_PyMem_RawMalloc`, with some NumPy `PyUFunc_FromFuncAndDataAndSignatureAndIdentity` and `NpyString_new_allocator` allocations. No retained leak stack contains a solver allocation frame. This is allocation provenance, not a claim that Python-hosted LSan proved solver leak-freedom.

The native `mxcsr_probe` also printed `PASS` and then had a separate 104-byte LSan report with allocation stacks through `dlopen` and the dynamic loader, not through a solver allocation frame. Run 36179216551 reproduced exactly this failure while the other seven native checks passed. The short-lived FP-mode probe now keeps both DSOs loaded until process exit, which is the load behavior it is designed to check; run 36179517856 then passed all eight native LSan checks. The probe itself is instrumented in sanitizer builds, avoiding a build-tool-only leak-check override; native solver lifecycle tests still independently run with LSan.

| Python CTest / entry point | Solver lifecycle/API exercised | Retained host allocation provenance | Native LSan coverage |
| --- | --- | --- | --- |
| `test_stream_storage.py` | stream create, growth failure, counts/status, retry, destroy | CPython raw allocator | `test_stream_storage_native` |
| `test_dgesdd_candidate_semantics.py` | certified API, router, compact DGESDD core | CPython and NumPy | `test_dgesdd_core_state`, `test_native_solver_lifecycle` |
| `test_certified_api.py` | certified API and generated witnesses | CPython and NumPy | `test_native_solver_lifecycle` |
| `test_status_profile_semantics.py` | certified API and inconsistent verifier | CPython and NumPy | `test_native_solver_lifecycle` |
| `test_verifier_adversarial.py` | three witness verifier failure paths | CPython and NumPy | `test_native_solver_lifecycle` (three corresponding rejected witnesses) |
| `test_meta_api_absent_solution_quality.py` | router meta API | CPython and NumPy | `test_native_solver_lifecycle` |
| `test_streaming_equivalence.py` | stream and router meta APIs | CPython and NumPy | `test_native_solver_lifecycle`, `test_stream_storage_native` |
| `test_threshold_contract.py` | thresholds, stream, router | CPython and NumPy | `test_native_solver_lifecycle` |
| `test_public_diagnostics.py` | router meta/diag/accessors and stream solution | CPython and NumPy | `test_native_solver_lifecycle` |
| `test_core_rank_boundary.py` | router rank interval and compact core | CPython and NumPy | `test_native_solver_lifecycle`, `test_dgesdd_core_state` |
| `test_blockprefix_guard.py` | router meta API | CPython and NumPy | `test_native_solver_lifecycle` |
| `test_route_agreement.py` | router and four individual routes | CPython and NumPy | `test_native_solver_lifecycle` |

The native lifecycle test uses small full-rank, rank-deficient compatible, and inconsistent systems; it exercises stream success/contradiction, router and individual routes, certified profile generation, witness generation/verification/free, three rejected verifier objects, and an invalid certified output argument. The native core test exercises the private compact-DGESDD allocation and release. The native ENOMEM test exercises first-growth failure, atomic state, identical-row retry, and destruction. The three native C examples also remain in the LSan partition. These are representative lifecycle paths, not exhaustive leak coverage of every solver input or allocation-failure branch. Python semantic batteries remain under ASan bounds/use-after-free/FakeStack and UBSan with `detect_leaks=0` only in their process steps; native processes retain `detect_leaks=1` and FakeStack. No LSan suppression is used.
