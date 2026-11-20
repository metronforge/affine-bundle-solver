# Evidence and decisions

One certificate-performance iteration. The benchmark, its acceptance rule and the holdout were committed before either optimization (f7d5365). Diagnostic observations and independent checks are outside the timing series.

| # | Question | Observation and decision |
|---:|---|---|
| 1 | Which baseline isolates the certificate change? | Branch from the published solve tip 361f068d. [Manifest](data/base-manifest.json). |
| 2 | Can both sides receive exactly the same candidate? | Store A,b,x in NPZ once. Compare byte hashes across processes. [Inputs](inputs/SHA256SUMS). |
| 3 | Which API measures issuance? | Time warmed bs_certify_candidate alone; record its return and every field. [Harness](experiment.py). |
| 4 | Does wide show an obvious repeated check? | On w2 only one inconsistent verification; LAPACK proposals account for much of total time. [Trace](data/base-w2.trace). |
| 5 | Do tall systems differ? | On t2, 11 inconsistent verification calls, including two accepted candidates. [Trace](data/base-t2.trace). |
| 6 | What family and target are fair? | Lock three tall shapes with equal weights and two new seeds/sizes for holdout. [Protocol](protocol.md). |
| 7 | How close are identical builds? | A/A geometric ratio 1.023. Use block intervals; interpret few-percent changes conservatively. [A/A](data/aa.json). |
| 8 | Is there enough time to remove? | T2 inconsistent verification consumes 7.67 ms of 18.14 ms in the median instrumented call. Proceed. [Trace](data/base-t2.trace). |
| 9 | Can E be obtained from one magnitude per row? | frexp exponent is monotone on positive finite magnitudes. Keep zero-row sentinel. [Proof](review/review.md). |
| 10 | Is the exponent optimization A sufficient? | A/BASE=0.918, short of target. Keep it and investigate the column sums. [Pairs](data/a.json). |
| 11 | Can moving a scale change a rounded product? | Subnormal or overflowing intermediates can invalidate equivalence. Limit direct multiplication to an explicitly bounded range. [Independent analysis](review/review.md). |
| 12 | Can the remaining column work be batched? | Each column has its own recurrence. Retain row order and perform separate downward/upward passes per tile. [Source](../../src/status_certificate.c). |
| 13 | Is there a path for out-of-range source or weight values? | Reuse the original framed dot product and its scratch buffer. [Source](../../src/status_certificate.c). |
| 14 | Does A+B help on the public API? | Exploratory family ratio 0.653 with identical public results. [Pairs](data/ab.json). |
| 15 | What about machines with extended intermediates? | Require binary64 and FLT_EVAL_METHOD==0 for B. x87 uses the scalar path. [Differential](review/verification-x87.json). |
| 16 | Can a tile boundary change a radius or the caller's mode? | Add a 3–4–5 case crossing column 64 at unit and extreme scales in four rounding modes. [Range suite](data/range.txt). |
| 17 | What does B alone buy? | Reverse A only; B/BASE=0.814, interval includes 0.80. [Pairs](data/b-only.json). |
| 18 | Is B beneficial on top of A? | (A+B)/A=0.707. Keep both in the public path. [Pairs](data/add-b.json). |
| 19 | Does this suppress candidate attempts? | T1/T2/T3 take 7/11/11 attempts on both sides with two successes each. [Witness capture](data/public-oracle-final.json). |
| 20 | Did the intended work actually fall? | T2 fesetround calls 344333→82065, frexp 1384452→143364. [BASE counters](data/counts-base.json), [FINAL counters](data/counts-final.json). |
| 21 | Did another certificate profile supply the saving? | On t2 the changed verifier falls from 7.67 to 1.64 ms; UNIQUE+INFINITE is 6.85→7.03 ms. [Final trace](data/final-t2.trace). |
| 22 | Is there a measurable control regression? | All nine exploratory control ratios below 1. No >5% point loss to investigate. [Controls](data/controls.json). |
| 23 | Is the chosen public radius outward? | Five captured selected witnesses satisfy the project's 100-decimal oracle; both sides give identical hex radii. [Public oracle](data/public-oracle-final.json). |
| 24 | Do unusual inputs change verifier results? | Independent differential runs in four modes match all fields and bit patterns under native and x87 evaluation. [Review](review/review.md). |
| 25 | Is caller-visible API and failure handling intact? | Public C tests pass, allocation sweep covers 24 sites. [API](data/cert-api.txt), [allocation](data/cert-alloc.txt). |
| 26 | Does an unseen family sample transfer? | Two new sizes, first use after freezing the patch, geometric ratio 0.674. No retuning. [Holdout](data/holdout.json). |
| 27 | Does a clean rebuild meet the frozen criterion? | Ratio 0.712, upper endpoint 0.720 (<0.800). [Final](data/final.json). |
| 28 | How does this affect the specific previous example? | Reload the old 128×768 matrix and RHS. Verify BASE x hash against previous campaign. Supplemental ratio 0.965. [Data](data/previous-w2.json). |
| 29 | Can an independent reversal undo the gain? | Rebuilding with both source changes reversed restores the baseline verifier hash. T2 final/off ratio 0.617. [Control](data/independent-off.json). |
| 30 | Do manuscript checks and packaging reproduce? | All eight manuscript claims pass. Bundle saved triples, scripts, raw blocks and review evidence with the branch. [Claims](data/paper-claims.txt), [reproduction](reproduce.sh). |
