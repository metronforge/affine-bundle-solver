
1. Can the pinned source build with the reproduction toolchain? Falsifier: A build/probe error or missing public symbol. → PASS, `./build.sh`, GCC 14.2.0 and SciPy OpenBLAS, `bsolve` exported by libcertified_solver.so. [Manifest](data/base-manifest.json), [probes](data/base-build.log). Proceed to A/A.

2. Do independent builds agree on rank/status and timings? Falsifier: Any semantic mismatch or repeatable drift outside 5%. → All three outputs (including x and backward error) match. Ratios 0.922/1.002/1.045; w1 exceeds 5%. Use more blocks and paired uncertainty. [A/A](data/aa.json).

3. Where does total solve time increase across shapes? Falsifier: Comparable costs at all shapes or failures to reproduce classifications. → Public solve ranges from 0.71 ms (48×192) to 156 ms (256×2048); extreme 42.5 ms, tall 8.48 ms. [Map](data/map.json). Retain wide as primary.

4. Can we freeze a meaningful multi-size wide family and acceptance rule? Falsifier: Mixed classifications in baseline or identical seeds for holdout. → All three are INFINITE with point interval [m,m]; held seeds are distinct. [Frozen protocol](protocol.md), [harness](bench.py). Profile w2.

5. Is classification a substantial part of w2 end-to-end solve? Falsifier: Router contributes less than 20% of elapsed bsolve. → Last warmed w2 call 17.65 ms: policy 11.77 ms (67%), reconstruction 5.88 ms; nested second rank proof 5.56 ms. [Five traces](data/profile-base-w2.txt). Compare smaller defect.

6. Does the small-wide control enter the same second proof? Falsifier: Same two QR factorizations in 48×192 and 128×768. → 48×192 enters try_secant_tail (n−r=144 ≤256), one QR and one guard; w2 enters empty sketch then second proof (n−r=640). [Small trace](data/profile-base-small.txt). Count operations.

7. Do the repeated checks add a direction or consume any tail row? Falsifier: Different QR ranks, an extra growth, or p<m in a primary call. → w3: 4 probe growths; after prefix rank 256, one zero insertion + two checks, zero further growth. Two (256×2048) QR states and guards, one all-row compat scan, one least-squares reconstruction. [Counts](data/profile-base-w3.txt). Seek independent falsification.

8. Can a single-factor intervention distinguish proof work from DGELSY cost? Falsifier: Independent review finds the proof necessary on this path or no isolated intervention. → Independent reviewer isolated two disjoint costs: second source-rank proof 5.56 ms, DGELSY reconstruction 5.88 ms. Replace only the former with the already certified prefix bound in a disposable build under full-row-rank/no-tail conditions. [Trace](data/profile-base-w2.txt).

9. Will disabling only the second identical proof remove its measured time? Falsifier: Less than half the predicted saving or any candidate/status difference. → 19.538→14.048 ms (−5.490 ms), predicted 5.558 ms, identical x/status. Small path fluctuated (0.885); do not assign that delta to removed QR. [Pairs](data/knockout.json), [one-line intervention](data/knockout.patch). Estimate ceilings across sizes.

10. Does the avoidable proof exceed 20% at all primary sizes? Falsifier: Median per-call proof/public fraction ≤0.20 at any size. → Second proof median share 30.6%, 32.4%, 31.6%. Estimated attainable ratio ~0.68–0.69. [w1](data/profile-base-w1.txt), [w2](data/profile-base-w2.txt), [w3](data/profile-base-w3.txt). Keep one-proof mechanism.

11. Can the second proof be replaced by a scalar bound without weakening the evidence? Falsifier: A non-source prefix, lower bound below the proposal, or missing source-row check. → Prefix contains every source row when pre_lo=m (p≤m); fg_qr_rank_certifies already proved m independent directions on this A with the same provenance errors. Full-row compatibility and validation still precede acceptance. Repeated QR/QR reconstruction/Gram costs Θ(nm²+m³) and extra workspace incl. n² capacity; bound lookup O(1). Counts in [w3 trace](data/profile-base-w3.txt). Implement only on first successful check.

12. Can the normal bsolve path execute exactly one guard on w2? Falsifier: Two guard calls or an altered operational/candidate result. → Baseline evidence test failed on 2 guards; A passes with [1,0,0], point interval [128,128]. Source edit leaves fallback and result ABI intact. Disable by reversing this single source commit. [A build](data/a-build.log).
