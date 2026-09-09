# What the benchmarks say about the manuscript's claims

Two harnesses, one corpus each. `experiments/suitesparse_bench.py` runs real
matrices from the SuiteSparse Matrix Collection;
`experiments/synthetic_bench.py` generates the families the manuscript makes
claims about and reports, per family, whether the measurement lands inside
the claimed range. The second returns a nonzero exit code when a claim is not
reproduced, so it can be run as a scheduled job rather than read by hand.

Results below are from two machines. Where they disagreed, that is noted.

## Confirmed, and extended

**20-80x on overdetermined m >> n.** Reproduced at every width tried:

```
    8000 x 32      26.2x
    7680 x 64      27.9x
    7680 x 128     64.4x
    8000 x 2000    29.6x
   20000 x 2000    72.5x
```

The last two matter because nothing in the manuscript was measured above
n = 128. The claim was stated for narrow systems and turns out to carry to
n = 2000, at the top of the range.

**Classification across shapes and conditioning.** Eleven of eleven, on both
small and large systems: INFINITE on exactly rank-deficient input,
INCONSISTENT, UNDECIDABLE with a rank interval on perturbations inside the
refusal band, and the quality invariant at condition numbers 1e2, 1e8 and
1e14. At 1e14 the router declines rather than returning UNIQUE, which is the
status model working. The same holds at 6000 x 2000, where the backward error
could plausibly have grown past the threshold and does not: 6.6e-16.

Sixteen real matrices from the SuiteSparse dense subset classify coherently
too, across all three shapes, with no FAIL. See docs/suitesparse-findings.md.

## Not reproduced

**Square systems: 0.6-0.9x claimed, parity measured.** 1.03x, 1.04x and 1.06x
at 256, 512 and 2000, against dgesv rather than a least-squares driver. Two
machines agree. The manuscript understates the method here, which is a claim
worth correcting in its own right: a paper that says it loses where it does
not invites the reader to distrust the places it says it wins.

**Underdetermined: pessimistic at small sizes, correct at scale.** 0.44x at
128 x 512 and 0.62x at 256 x 2048, against a claimed 0.24-0.43x; but 0.35x at
2000 x 8000, inside it. The claim appears to describe the large-system
behaviour and to be conservative below that.

**Extreme underdetermined is far worse than the range says.** 0.03x at
32 x 12800, and the SuiteSparse run found 0.02x on LPnetlib/lp_fit2d at
25 x 10524. The stated 0.24-0.43x was measured at moderate aspect; at n/m in
the hundreds the penalty is an order beyond it. This belongs in the
manuscript's limitations rather than being left to be found.

## Open: the grouped-row regression

The performance table reports 0.56x on "overdetermined with grouped rows"
without describing how the grouping was built. The generator here draws rows
from a few directions with small spread, and comes out at 26x and 38x --
faster, not slower. Either that construction is not the one measured, or the
regression has a narrower cause than the label suggests.

This is recorded, not asserted. Turning it into a passing check against a
generator that may not be the right one would make the harness agree with the
paper for the wrong reason.

## Method notes

Both harnesses pin BLAS to one thread, which is the comparison the manuscript
makes.

The baseline differs by shape and must: square systems compare against dgesv,
everything else against dgelsy. An early run compared square against gelsy
and reported 2.5x where the manuscript claims 0.6-0.9x, entirely because
gelsy is QR with column pivoting and costs far more than LU.

The first timed case needs a process-level warm-up. Without one it measured
0.43x on one machine and 15.79x on another for the same 8000 x 32 system --
a spread no algorithm produces. Whatever ran first was paying for the OpenMP
pool and the first LAPACK workspace query.
