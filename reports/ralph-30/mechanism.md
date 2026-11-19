# Why the public solve gets faster

On the measured wide path, p=min(m,n)=m. The prefix contains every source row. core_qr_state factors the transpose of the row-normalized prefix and supplies Q, R and the pivot indices. The strict fg_qr_rank_certifies checks reconstruction, orthogonality and provenance. A success at rank m gives a lower bound of m on this source, and m is the dimensional upper bound. No row of the source can be added later.

BASE copies the prefix state, inserts one empty sketch row, checks two empty validation rows, and scans the original A,b for compatibility with the actual anchor. It then factors the retained proof rows and runs the strict QR witness check a second time on the same rank claim. A uses pre_lo at that last site only when pre_lo and the validated candidate rank both equal m. Validation and source compatibility still run on each call. The public certainty continues to describe the existing proposal path; the guard counter records the actual check count. When either equality fails, the old proof and source escalation run. No bound crosses calls and no pointer or factor is cached.

For rank r=m the duplicate QRCP, basis construction, Gram/reconstruction checks and triangular work cost Θ(nm²+m³). Removing one instance changes the constant for the public call, which still constructs a least-squares/minimum-norm candidate with DGELSY and has the same asymptotic order on this family. The strict kernels, rank tolerances, original-row residual test, and the arithmetic producing the public x are identical. A second proof over the normalized rows is a sufficient test, not a necessary additional premise once the first strict test has certified m. The argument does not require comparable row scales or a timing threshold.

| Inclusive profile on 128×768, ms | BASE | A |
|---|---:|---:|
| Public bsolve | 17.906 | 12.816 |
| Policy and routing | 12.093 | 6.745 |
| QR state construction, all calls | 7.596 | 4.252 |
| Strict rank witness, all calls | 3.893 | 1.915 |
| Second proof including its QR and witness | 5.674 | 0 |
| Original-row compatibility | 0.023 | 0.024 |
| State copy | 0.061 | 0.064 |
| DGELSY candidate including setup | 5.878 | 6.134 |

Medians over five warmed traces, with nested time inside parent spans. The BASE trace used CPU 1 and the exploratory A trace CPU 3 on the same VM. Matched CPU 1 comparisons are the uninstrumented timings. The second instrumented run on CPU 1 at 256×2048 attributes 3.275 and 3.017 ms to the two packs inside A's 63.874 ms candidate construction. Scope and I/O overhead limit precision for short spans. The study does not estimate DRAM bytes from elapsed time. [BASE](data/profile-base-w2.txt) · [A](data/profile-a-w2.txt) · [Packing spans](data/profile-a-pack-w3.txt)

At 256×2048 the trace records four successful probe insertions, two QR states at rank 256 on BASE, one subsequent empty-row insertion, two proposal checks and one original-row compatibility scan. The two original-source finiteness scans (policy and legacy meta entry), the prefix norm and normalization for Pcore, the norm and normalization for proof rows, the compatibility scan and the two DGELSY packing loops amount to **nine logical passes** over A for ordinary nonzero rows, plus the four-row probe. The removed factorization reads retained proof rows; these nine source passes persist on A. Logical passes are inferred from instrumented call counts and loop bounds, distinct from measured cache traffic. On the small control the first different branch is n−r≤256 in solve_blockprefix_qr: the secant-tail route can return after one proof. [Counts](data/profile-base-w3.txt) · [Small control](data/profile-base-small.txt)

A saves a proof-only BState whose Q allocation alone reserves 8n² bytes, plus Θ(nm+m²) factor/witness buffers. At n=2048 the avoided Q request is 32 MiB, at n=12800 it is 1250 MiB. Lazy allocation makes these requested bytes an upper estimate of the touched Q pages. Other Q states remain; neither peak RSS nor the overall storage order is claimed to drop by those amounts.

To reproduce the source profile, create a disposable detached worktree of the desired revision, then run `taskset -c 1 python3 reports/ralph-30/profile.py /path/to/worktree --instrument` from the campaign checkout, followed by the same command with `--case w2` in place of `--instrument`. Profiling uses GNU C cleanup scopes on this Linux host; production has no instrumentation.
