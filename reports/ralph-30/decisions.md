
1. Can the pinned source build with the reproduction toolchain? Falsifier: A build/probe error or missing public symbol. → PASS, `./build.sh`, GCC 14.2.0 and SciPy OpenBLAS, `bsolve` exported by libcertified_solver.so. [Manifest](data/base-manifest.json), [probes](data/base-build.log). Proceed to A/A.

2. Do independent builds agree on rank/status and timings? Falsifier: Any semantic mismatch or repeatable drift outside 5%. → All three outputs (including x and backward error) match. Ratios 0.922/1.002/1.045; w1 exceeds 5%. Use more blocks and paired uncertainty. [A/A](data/aa.json).

3. Where does total solve time increase across shapes? Falsifier: Comparable costs at all shapes or failures to reproduce classifications. → Public solve ranges from 0.71 ms (48×192) to 156 ms (256×2048); extreme 42.5 ms, tall 8.48 ms. [Map](data/map.json). Retain wide as primary.

4. Can we freeze a meaningful multi-size wide family and acceptance rule? Falsifier: Mixed classifications in baseline or identical seeds for holdout. → All three are INFINITE with point interval [m,m]; held seeds are distinct. [Frozen protocol](protocol.md), [harness](bench.py). Profile w2.
