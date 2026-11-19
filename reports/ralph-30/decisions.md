# Ralph PDCA · 30 sequential decisions

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

13. Does A speed up all three cases and remove specifically the repeated phase? Falsifier: Family ratio above 0.8 or trace still contains the second proof. → Ratios 0.719/0.649/0.684, geometric mean 0.683, exploratory CI [0.647,0.802]. W2 trace has one QR/guard and no certified_proof_rank_lo. [Pairs](data/a.json), [instrumented run](data/profile-a-w2.txt). Reverse source change.

14. Does reversing A restore two guards only on the affected path? Falsifier: Reversal leaves one guard on w2 or changes count on small. → Reversed source equals BASE. W2 OFF→ON 18.906→12.931 ms, guards 2→1; small 0.724→0.739 ms, guards 1→1, CI includes 1. [Disable experiment](data/disable.json). Try boundary inputs.

15. Does A preserve numerical outcomes when the full row-rank premise fails? Falsifier: Changed x/status/evidence/quality or gate reuse on a rank-defective case. → All outputs agree, true defect [95,96], conflict [95,95], grey UNDECIDABLE [95,96]; counts unchanged except certified rank-96 ill case, 2→1. [Raw results](data/a-boundary.json). Profile remaining data movement.

16. Is building the DGELSY matrix twice a measurable residual cost? Falsifier: First pack below clock resolution or the query needs matrix values. → On w3 the first of two transposes costs 2.78–3.65 ms each call; last call 3.42 of 125.26 ms. B will pack only after the LAPACK workspace query. [Pack profile](data/profile-a-pack-w3.txt). Verify query contract.

17. Does DGELSY workspace size depend only on dimensions? Falsifier: Different optimal lengths or INFO on a finite, zero or NaN payload at fixed m,n. → INFO=0 and identical workspace for all payloads, sizes 17536/6752/1152. LWORK=−1 requests the optimal workspace only (LAPACK DGELSY); retain valid buffers and load all actual values and pivots before the computation. [Payload experiment](data/query.txt).

18. Does B improve public solve over both BASE and A? Falsifier: No reproducible extra improvement or changed numerical results. → B/BASE 0.964 [0.892,1.007]; (A+B)/A 0.986 [0.972,1.146]. All matched. Additional family benefit unresolved; keep B as experimental patch only. [B](data/b.json), [A+B versus A](data/ab-v-a.json), [patch](data/candidate-b.patch).

19. Where does A stop helping as dimensions and rank change? Falsifier: Full row rank alone predicts the saving even on the secant-tail route. → Ratios w1 0.670, extreme 0.736; small 0.956, defect 0.987, grey 0.994, last three intervals span 1. No supported loss region here. No new representation; avoids one short-lived n² allocation and factor work. [Shape/rank sweep](data/domain.json). Use computed rank, no tuned crossover.

20. Does deciding reuse require an additional data pass or expensive dispatch? Falsifier: Generated router calls another function to decide or allocates new storage. → Two integer compares/conditional branches, two stack loads at most in GCC native code. No matrix scan, tuning parameter or extra allocation. [Disassembly](data/selection.txt). Retain existing route and guard at its original acceptance site.

21. Does the selected public build reproduce the A effect without experiment-only patches? Falsifier: Production library has profiling hooks or paired family ratio >0.80. → Stock public build source equals 2e868b0, family ratio 0.689 [0.650,0.722], x/contract equal. [Integrated timings](data/integrated.json). Audit edge classifications and radii.

22. Do independent residuals or certificates reveal any near-boundary change? Falsifier: Different status, rank interval, candidate quality or accepted radius on the same input. → Six matched status/intervals, original-row upper bounds covered long-double oracle, all accepted masks and binary64 radii equal, including conflict and grey. Check/certify measured outside solve. [BASE](data/numeric-base.json), [FINAL](data/numeric-final.json). Run project oracles.

23. Do independent project oracles and source fallback still pass? Falsifier: Any rank/solution, outward-radius or fallback failure. → 36 solution and 180 quality oracle comparisons; qualification 180/180, 378 certificate-property checks; minimum finite strict/shadow radius ratio 1.0000000000000002. Conflict/grey exercised source QRCP (1/2 calls). [Split](data/split.json), [qualification](data/qualification.json), [radius oracle](data/oracle-radius.json). Measure controls.

24. Is any control slower by more than 5%? Falsifier: Any ratio >1.05; repeat that case before accepting. → Extreme 0.754; remaining ratios 1.031/1.016/1.035/1.021/1.032 (tall/grouped/square/grey/small). No >5% point loss. [Control data](data/controls.json). Retest largest apparent loss rather than narrowing prematurely.

25. Does the +3.5% square observation repeat above the investigation threshold? Falsifier: New independent blocks show a reproducible ratio >1.05. → Square 0.986 [0.921,1.105], tall 1.023 [0.956,1.118]. No confirmed regression; do not introduce a shape cutoff. [Retest](data/square-repeat.json). Send clean session the input and patch.

26. Can a fresh reviewer falsify the mechanism or reproduce it from clean builds? Falsifier: No guard-count drop or no speedup on w2 when rebuilt independently. → Independent clean builds w2 20.642→14.060 ms (0.681 [0.669,0.738]), guards 2→1. Small 0.960 [0.931,1.003], one guard on both. Reviewer confirmed pre_lo=m requires p=pr=m; removed allocations may avoid resource-pressure fallback. [Replication](data/independent.json), [commands](handoff.md). Unseal holdout.

27. Will the frozen, unseen wide inputs meet the goal with equivalent output? Falsifier: Held family ratio >0.80 or any numerical mismatch. → Holdout ratios 0.690 and 0.684, family 0.687 [0.671,0.704], identical numerical results. [First exposure](data/holdout.json). Inputs now used; no tuning. Rebuild both versions.

28. Will fresh uninstrumented builds on the same CPU meet the preregistered target? Falsifier: Family ratio >0.80, incompatible outputs, or uncertainty spanning the target. → Reproduction script passed with independently rebuilt BASE/FINAL on CPU 1. Family 0.708 [0.681,0.734], controls at worst +3.3% point (square). Holdout repeat 0.700 [0.663,0.740]. [Final pairs](data/final.json), [build manifests](data/final-manifest.json), [whole run](data/reproduction.txt). Verify manuscript and tests.

29. Do the project batteries and manuscript claims pass on the rebuilt solver? Falsifier: Any new failure or published performance number treated as portable. → All 8 manuscript claims reproduced, standalone C solve contract, blockprefix, compressed-core, threshold and graph-03 transition tests passed. Frozen checksums verified. [Claims](data/paper-claims.txt), [C API](data/solve-api.txt), [thresholds](data/test_threshold_contract.txt). Prepare review package.

30. Can a reviewer reconstruct the result from branch artifacts alone? Falsifier: Missing inputs/links, dirty solver diff, inconsistent metric, or failure to publish the requested ref. → 15 NPZ checksums, raw final/held input hashes, all 30 decisions and internal links verified; public family ratio recalculated 0.707976. Production diff is one router source file. Deliver [report](README.md), [reproduction](reproduce.sh) and [handoff](handoff.md) for branch-only review.
