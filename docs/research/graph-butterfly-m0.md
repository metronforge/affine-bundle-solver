# Graph-interface / bundle-butterfly research — M0 contract

Status: research specification, not an implementation or performance claim.

## Source and terminology

The authoritative source is `paper.tex`, sections **Semantic merge**, **Canonical atomic insertion**, and **Why the bundle butterfly was not retained**. The paper already rejects a naive full-state balanced butterfly tree as an efficient solver route; this research investigates *interface-restricted* composition, which is a different algorithmic proposal. Do not rename row insertion itself as a general two-bundle merge.

For a consistent affine bundle `B=(R,ell)`, define
`Sol(B)={z: r^T z=ell(r) for every r in R}`.
Two bundles merge only if their functionals agree on `R1 intersect R2`; otherwise the result is the explicit inconsistent state `BOTTOM`.
For compatible bundles, `R=R1+R2` and
`ell(r1+r2)=ell1(r1)+ell2(r2)`.
The exact invariant is `Sol(B1 star B2)=Sol(B1) intersect Sol(B2)`.

The atomic insertion in the paper is `g=(I-P)a`, `rho=beta-a^T x`. If `g != 0`, `P+=P+gg^T/(g^Tg)`, `x+=x+rho*g/(g^Tg)`; if `g=0`, `rho=0` is redundant and `rho!=0` is contradictory. These are *exact arithmetic* statements. Do not infer floating-point status from them.

## Graph interface contract

Partition variables as `(u,s,v)` with left constraints `A1 u+C1 s=b1` and right constraints `A2 v+C2 s=b2`. This factorization is valid only when there is no omitted constraint coupling `u` directly to `v`. Define exact feasible interface sets
`P_i={s: exists internal variables satisfying block i}`.
Then the global system is feasible iff `P1 intersect P2 != empty`. The interface alone is not a full-solution representation: preserve reconstruction witnesses/affine maps and free parameters, or explicitly scope the result to feasibility only.

For arbitrary graph partitions, verify that every crossing constraint is represented in a separator/interface; otherwise reject the decomposition. Do not project independently and claim that projection commutes with intersection.

## Experimental variants and fair comparison

A: existing ABS, unchanged, pinned to exact baseline commit.
B: graph decomposition with exact interface semantics and a conventional reference merge.
C: *same* decomposition, elimination ordering, numerical tolerances, and reconstruction, with the paper-derived bundle merge restricted to the interface. Before implementing C, derive and independently review its exact correspondence to the paper's semantic merge. If B and C are algebraically identical, state this and isolate only an implementation-level difference; do not fabricate a novel algorithm.
D: established sparse direct baseline (e.g. sparse QR), with implementation and availability disclosed.

For all four, keep inputs, solution/status oracles, rank conventions, hardware, compiler settings, and timing protocols fixed. Report wall time separately from arithmetic counts. Instrument add/subtract/multiply/divide/sqrt and rank-revealing kernels consistently; disclose excluded operations and BLAS/LAPACK accounting. Track fill-in, peak state/interface size, factorization reuse, allocations, and reconstruction cost.

## Required adversarial tests

- Consistent full rank, underdetermined, overdetermined, rank-deficient, inconsistent.
- Minimal incompatible overlap: `x+y=1; 2x+2y=3`.
- Cycle inconsistency: `x1-x2=0; x2-x3=0; x3-x4=0; x4-x1=1`.
- Projection trap: `y=0` and `y=1`, projected to `x`.
- Reconstruction trap: `x=y; y=z` with later `y=1`.
- Conditioning: rows `(1,0),(1,eps),(0,1)` across eps scales and merge orders.
- Parametric paths, cycles, triangular meshes, overlapping 3-nonzero-coefficient equations, expanding separators, and dense controls.
- Use exact rational oracle for small systems and independent numerical residual/rank/status checks for larger ones.

## Gates

M0: this specification reviewed; no claims of empirical advantage.
M1: independent prototype B/C in research-only paths, without modifying the production solver.
M2: exact semantic proof obligations plus executable oracle-backed tests, including contradiction and reconstruction.
M3: comparable operation counters and documented exclusions.
M4: A/B/C/D benchmark on pinned fixtures, including negative results.
M5: upper bounds by local ranks, separator width, fill-in, merge schedule, and reconstruction; prove lower bounds only when justified.
M6: publish one of: advantage on a specified family; no advantage; conditional advantage. No release or main merge without independent review.

Use conventional commits, ordinary branches (no worktrees), rebase onto main, and no modifications to production ABS until gates pass.
