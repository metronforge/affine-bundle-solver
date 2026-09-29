# Tail scan SIMD audit plan

Goal: establish actual SIMD, reachability, and optimization value without changing arithmetic.
Execution: autonomous inline, as requested. Base 984dece, branch perf/simd-stage2b-tail-scan.

- Add compile-time-only hooks to capture the real prefix and count serial/block rows in a diagnostic library. Default hooks preprocess away; verify production binary identity.
- Include the real router in a replay adapter. Replay the captured private BState through try_secant_tail; do not rewrite its loops. Document setup/final checks included in this isolation boundary.
- Freeze clean normal and no-autovec builds with source/tree, commands, object/library hashes. Retain production and diagnostic worker assembly and GCC diagnostics.
- Generate route-confirmed rank-deficient workloads, plus bypass controls; compare instrumented/uninstrumented decisions. Benchmark replay and production router with 3 warmups and 21 interleaved repeats, single-thread pinned. Separately collect phase telemetry and a two-thread block-path check.
- Run 35-test suites for both retained configurations, strict-object/flag and export checks, and diagnostic-equivalence probes. No arithmetic variants unless assembly and measurements justify one.
- Record limitations, results and recommendation; archive evidence without binaries; commit and confirm clean Git state.
