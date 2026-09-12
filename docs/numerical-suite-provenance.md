# Numerical-suite provenance contract

This document defines the admission boundary for a future main numerical-suite
reference package. It does not admit the historical
`results/numerical_final_suite.json`, and implementing this contract does not
make any manuscript claim current.

## Immutable protocol

Result schema version 2 uses protocol ID
`affine-bundle-numerical-suite-v2`. The canonical protocol signature is:

`31e84400f2bb347bf3e076a8179b9a361c8e5cb7377eec0da7824e7e63a5ab04`

The earlier signature
`ef22e2101de6a5b29a5e8319fcf04faf5af6ac6ca36f8430650070c6fa1ca7d8`
did not sign a complete execution-evidence shape. The signature changed
because the protocol now includes complete generator parameters and
distributions, exact warmup and timed routing-seed sequences, required timed
run identities, explicit `s` units, requested OpenMP threads, and exact ratio
identities and directions. The section order is:

1. `standard` -> `standard`
2. `rank` -> `rank_transition`
3. `guard` -> `guard_timing`
4. `scaling` -> `scaling`
5. `structural` -> `structural`
6. `lapack` -> `lapack_context`

Every case records stable case and run identities, native float64 ABI/layout
facts, dense row-major strides, and SHA-256 fingerprints of canonical C-order
bytes for A, b, and x. The filtered Digits design-matrix fingerprint is
`e0fd0d6813a2c9672452920a25da74d0b2b8a2cef476cfad80ad4b4f52bb5355`.
These checks establish the Python-to-C ABI boundary; they do not establish
cache efficiency or SIMD behavior inside solver kernels.

Each required timed router invocation records a stable run ID; case ID;
generator and routing seeds actually used; repetition index; requested and
observed OpenMP thread counts; OpenMP runtime identity; duration in `s`;
status, rank interval, residual, BERR, fallback, and solver timer diagnostics;
and an individual numerical-contract verdict. A case is valid only when every
required run is present exactly once, in order, and valid. Warmups have signed
seed sequences but are not mixed into timed aggregates.

Each timed operation records one timing source, exact warmup and repetition
counts, positive finite raw observations, median, and median absolute
deviation. Solver-reported timings and Python `perf_counter_ns` timings remain
separate. Required ratios have signed identities, numerator, denominator, and
direction and are recomputed from named medians. Historical timing ranges are
observations and never decide numerical validity or package eligibility.

## Package and candidate admission

A candidate package contains exactly:

- `numerical-suite-reference.json`
- `numerical-suite-reference.metadata.json`
- `numerical-suite-reference.sha256`

The result is written as strict stable JSON (`allow_nan=False`). The metadata
binds the result hash to clean, unchanged preflight/postflight source state;
the exact generator and dependency locks; invocation; run interval; adjacent
build manifest; compiler command; loaded router; linked and runtime BLAS;
thread controls; machine identity; and installed software versions. Hostnames,
usernames, device identifiers, credentials, checkout paths, and virtualenv
paths are forbidden.

The router is resolved from `ABS_LIB_DIR`. Only the adjacent manifest can
authorize that exact resolved library, and the verified path is the path
passed to `CDLL`. Router, sequential, LAPACK, and counter symbols are configured
on that same handle. The linked BLAS hash must occur in an observed runtime
BLAS pool, and every runtime BLAS pool must use one thread. Runtime pools are
split by `user_api`: BLAS pools remain single-threaded, while `threadpoolctl`
sets and observes the OpenMP runtime associated with each router call at the
suite's intentional 1/2/4 schedule. Missing, ambiguous, or mismatched OpenMP
observation makes candidate execution fail closed.

Candidate mode requires a reference-machine ID, `--omp=4`, and the exact
ordered six sections. Partial ordered runs remain useful diagnostics but are
ineligible and cannot emit a checksum. Immediately before publication the
source, router, manifest, and runtime-library evidence is verified again.
Result and metadata are serialized and validated in temporary files, then
atomically replaced; the relative-name checksum is published last.

## Dependency closure

`requirements-numerical-suite.txt` pins the shared CI versions plus the
scikit-learn runtime closure:

- NumPy 2.5.3
- SciPy 1.18.1
- mpmath 1.4.1
- threadpoolctl 3.6.0
- scikit-learn 1.9.1
- joblib 1.6.0
- cloudpickle 3.1.2
- narwhals 2.26.0

Resolution was verified with pip's binary-only Python 3.12 resolver, which
selected CPython 3.12 wheels for all eight exact pins. The same pins were
installed and imported in a disposable Python 3.13 virtual environment as a
second compatibility check. System Python was not modified.

## Audit and current status

Run the nonnumerical audit with:

```sh
python3 tests/check_paper_claims.py --audit-numerical-suite PACKAGE_ROOT
```

It reports artifact integrity, source/build/runtime provenance, protocol
eligibility, numerical-contract validity, supported claim mappings, and
manuscript readiness separately. The legacy unversioned historical JSON fails
with explicit schema, provenance, and raw-output reasons. Until a clean
candidate is separately reviewed and admitted, the registry remains at 20
claims, 18 publication blockers, and two nonblocked claims (`grouped.dgelsy`
and `scope.tall_directional`).
