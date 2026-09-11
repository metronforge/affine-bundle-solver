# What the benchmarks say about the manuscript's claims

Two harnesses, one corpus each. `experiments/suitesparse_bench.py` runs real
matrices from the SuiteSparse Matrix Collection;
`experiments/synthetic_bench.py` generates the families the manuscript makes
claims about. It returns nonzero for portable numerical-contract failures;
hardware-dependent timing ranges are recorded as reference-machine
observations and require review rather than controlling portable CI.

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

## Grouped-row reference run pending

The harness now reproduces the exact repeated normalized Hadamard directions
used by the embedded C grouped generator and compares them separately with a
selected LAPACK driver and with LSMR. LSMR termination, iteration count,
finiteness, and residual quality are portable correctness checks. Timing
ratios are reference-machine observations and never determine portable pass
or failure.

The checked-in `results/synthetic.csv` predates that correction and remains a
historical, unconfirmed artifact. It is not publication-grade evidence. The
manuscript numbers and that CSV must remain unchanged until the documented
reference-machine command has produced both a new result and its metadata
sidecar for review.

From a clean checkout, replace `YOUR_STABLE_MACHINE_ID` with the persistent
name of the designated host and run exactly:

```bash
timeout 2700s env REFERENCE_MACHINE_ID=YOUR_STABLE_MACHINE_ID \
  CC=gcc ARCH_FLAGS=-march=native \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  sh -c './build.sh && python3 experiments/synthetic_bench.py \
    --driver gelsy --seed 20260909 --repeats 11 \
    --out results/synthetic-reference.csv \
    --metadata-out results/synthetic-reference.metadata.json \
    --reference-machine "$REFERENCE_MACHINE_ID"'
```

The result and sidecar require review before either can replace a historical
artifact or support a manuscript edit.

## Manuscript claim coverage

Performance-claim coverage is tracked separately from benchmark protocol
eligibility.  The bounded registry in
`experiments/manuscript_performance_claims.json` names every current
manuscript-facing performance claim, fixes its numerator/denominator and ratio
direction, and classifies its evidence.  Its `paper.tex` hash is deliberate:
changing manuscript text requires reviewing this explicit inventory, without
attempting to parse arbitrary LaTeX.

Ordinary CI may require the inventory to be complete even while known
publication blockers remain.  The lightweight commands are:

```bash
python3 tests/check_paper_claims.py --check-performance-inventory
python3 tests/check_paper_claims.py --audit-performance-artifacts CHECKOUT
python3 tests/check_paper_claims.py --audit-performance-artifacts CHECKOUT \
  --require-publication-ready
```

The first two fail on missing mappings, malformed directions, damaged
artifacts, or protocol-invalid results.  Only the explicit strict form fails
because a fully inventoried claim is not yet publication-ready.  This keeps
artifact integrity, benchmark-protocol eligibility, manuscript coverage, and
manuscript readiness distinct.

For the immutable laptop candidate, protocol eligibility does not resolve two
manuscript blockers.  The historical `32x12800` claim lacks source/build/machine
provenance and used a different exact RNG state; its ratio direction is
DGELSY/router.  The three current grouped LSMR observations do not support the
historical “2.6--5.9x faster” wording, and LSMR and the router do not solve
equivalent tasks.  Both facts must remain visible until a separate manuscript
correction is reviewed.

The benchmark emits row schema v2.  Each row has a stable `case_id`, a
portable `numerical_contract`, separately scoped historical claim fields, and
raw plus summary timings.  `build.sh` atomically writes the ignored
`.abs-build-manifest.json` next to the router library; publication eligibility
requires that record to match the exact loaded router, current clean source
commit/tree, build script, compiler argv, and linked OpenBLAS binary.

## Method notes

Both harnesses pin BLAS to one thread, which is the comparison the manuscript
makes. The synthetic harness records raw repeats, median and median absolute
deviation, thread-control variables, and the effective BLAS providers.

The baseline is explicit per case: square systems compare against DGESV,
dense rectangular systems use the selected DGELSY or DGELSD driver, and the
grouped sparse comparison uses LSMR. An early run compared square against
DGELSY and reported 2.5x where the manuscript claims 0.6-0.9x, entirely
because DGELSY is QR with column pivoting and costs far more than LU.

The first timed case needs a process-level warm-up. Without one it measured
0.43x on one machine and 15.79x on another for the same 8000 x 32 system --
a spread no algorithm produces. Whatever ran first was paying for the OpenMP
pool and the first LAPACK workspace query.
