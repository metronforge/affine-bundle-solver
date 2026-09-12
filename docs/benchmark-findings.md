# What the benchmark package supports

The manuscript uses `results/synthetic-reference.*`, an immutable package
recorded on the reference laptop identified in its metadata. The package has
29 row-level records. Every numerical contract is valid. OpenMP and BLAS were
limited to one thread, with one case warmup and 11 timed repetitions.

Ratios are baseline/router. The five tall DGELSY comparisons are 16.318,
32.148, 48.120, 32.838, and 82.029. The grouped-row DGELSY comparisons are
12.677, 21.763, and 17.182. These are machine-scoped observations for the
recorded inputs, not a general speed range.

The package also records mixed results:

- square DGESV comparisons: 0.983, 0.993, and 1.083;
- underdetermined DGELSY comparisons: 0.411, 0.656, and 0.383;
- the 32 by 12800 extreme-wide DGELSY comparison: 1.206;
- grouped-row LSMR comparisons: 0.624, 1.603, and 0.636.

DGELSY computes a general minimum-norm least-squares result and LSMR is an
iterative solution method. Their internal work is not equivalent to equality
classification. The comparisons provide context, not a claim of universal
superiority.

`results/synthetic.csv` is older output with incomplete provenance. It remains
tracked for historical inspection but supplies no manuscript number.

## Checks

The claim registry contains only quantitative or status claims retained in
the manuscript. The checker verifies their text anchors and binds every
declared value to the corresponding immutable artifact row:

    python3 tests/check_paper_claims.py --check-performance-inventory
    python3 tests/check_paper_claims.py --audit-performance-artifacts . \\
      --require-publication-ready

The artifact audit checks the tracked hashes, source/build identity, canonical
case set, thread controls, raw timing summaries, and all row-level numerical
contracts. It does not rerun the benchmark.
