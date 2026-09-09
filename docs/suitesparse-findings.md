# SuiteSparse run: what it can and cannot answer

`experiments/suitesparse_bench.py`, dense subset, 16 matrices from 11
collection groups, density 0.25 to 1.00, all three shapes.

## The speed claim cannot be tested on this collection

The manuscript claims 20-80x for **dense overdetermined** systems. The dense
subset of SuiteSparse contains exactly one overdetermined matrix that fits:
`NYPA/Maragal_1`, 32 x 14. One matrix of that size is not a test.

This is a fact about the collection, not about the method. SuiteSparse is a
sparse collection; its dense entries are small and mostly square. The
objection that the timings rest on generated data therefore cannot be
answered here, and answering it needs a different corpus -- controlled
generators with prescribed condition number, with the origin of every row
labelled so a reader can tell which is which.

Sizes are the second reason not to read timings off this table: the largest
square matrix is 124 x 124 and the largest overall is 400 x 1200. At that
scale the measurement is dominated by call overhead rather than by the
algorithm, so the square median of 1.51x is not a performance statement.

## What it does support: classification across shapes

All 16 systems classified, and every status is coherent with the shape:

- square, full rank: UNIQUE with rank = n, on 9 of 9
- underdetermined: INFINITE with rank = m, on 6 of 6
- overdetermined and rank deficient: INFINITE with the rank interval [10, 14]

No FAIL, no UNDETERMINED, no status contradicting the shape. Four of the
sixteen carry a right-hand side supplied by the problem rather than one built
here; the other twelve are consistent by construction, so on those the status
reflects the construction and only the rank interval is about the matrix.

## A new weak point, worth stating in the manuscript

`LPnetlib/lp_fit2d`, 25 x 10524, is **0.02x** -- fifty times slower than
dgelsy. `LPnetlib/lp_fit1d`, 24 x 1049, is 0.09x.

The known underdetermined regression is 0.24-0.43x, measured at moderate
aspect ratios. These have n/m of 420 and 44, far outside anything previously
run, and the penalty grows sharply with that ratio. The manuscript should
carry this rather than leave it to be found: a stated 0.24x that turns out to
be 0.02x in a regime the paper did not explore is the kind of gap a reviewer
finds first.

## Selection notes, so this is not redone from scratch

Three attempts failed before this one, each measuring something other than
what was intended:

1. First matches from the index: 34 of 40 came from one family of simplicial
   boundary maps.
2. Cap per collection group: no help. JGD_Homology, JGD_Relat, JGD_GL7d and
   JGD_Taha are four groups holding that same family.
3. Filter by problem domain: a guess at where dense overdetermined systems
   arise, when density can be asked for directly.

The script now asks the collection for its own dense entries and falls back
to density measured from nnz, printing which path produced the sample.
