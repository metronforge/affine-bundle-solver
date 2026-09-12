# Numerical-suite provenance contract design

## Scope

This change adds a fail-closed contract for a future numerical-suite evidence
package. It does not change solver kernels, numerical generators, manuscript
text, historical results, or figures, and this iteration does not generate a
candidate package.

The implementation preserves the existing ordered protocol:
`standard,rank,guard,scaling,structural,lapack`, mapped respectively to
`standard,rank_transition,guard_timing,scaling,structural,lapack_context`.
All dimensions, generators, distributions, tolerances, seeds, warmups,
repetitions, solver calls, timing sources, and the OpenMP `1,2,4` scaling
schedule remain unchanged.

## Components and data flow

`experiments/numerical_suite_contract.py` owns protocol identity, strict JSON
serialization, input/timing records, result and metadata validation, exact
router/manifest binding, runtime checks, package audit, and atomic publication.
It is numerical-kernel-free and fixture-testable.

`experiments/rerun_numerical_suite.py` remains the owner of the existing
generators and solver calls. It delegates contract mechanics to the new module,
records stable case/run identities and raw observations, checks the ABI layout
before each C call, and exits nonzero for numerical-contract failures. Every
timed router call retains its actual generator/routing seeds, requested and
observed OpenMP setting and runtime, duration in seconds, diagnostics, and
individual numerical verdict; a later successful repetition cannot hide an
earlier failure.

Candidate execution produces schema-v2 result and metadata documents, validates
both before publication, atomically replaces them, and writes relative-name
checksums last. Eligibility requires an exact six-section run, clean matching
source state, `--omp=4`, single-threaded BLAS pools whose runtime hashes include
the linked BLAS hash, complete machine/software/build identities, and valid
numerical contracts. Partial developer runs remain diagnostic and cannot emit a
candidate checksum.

The 82-case protocol is independently frozen in a literal test fixture. Its
signature is
`31e84400f2bb347bf3e076a8179b9a361c8e5cb7377eec0da7824e7e63a5ab04`.
It replaces
`ef22e2101de6a5b29a5e8319fcf04faf5af6ac6ca36f8430650070c6fa1ca7d8`
because generator parameters/distributions, warmup and timed routing seeds,
required run identities, `s` units, requested OpenMP threads, and required
ratio identities/directions are now part of the signed protocol document.

`tests/check_paper_claims.py --audit-numerical-suite ROOT` reports package
integrity, provenance, protocol eligibility, numerical validity, supported
claim mappings, and manuscript readiness separately. It does not promote any
claim. The PR #34 audit continues to validate its tracked immutable package.

## Provenance and privacy

The result records canonical input hashes, layout/dtype/strides, raw timing
arrays, recomputable median/MAD/ratios/aggregates, complete diagnostics, and
explicit expected/actual numerical contracts. Public output slot 10 is named
`router_berr`; unavailable transition residuals are JSON `null`.

The metadata records result hash/signature, source state before/after, relative
generator and dependency-lock hashes, command/time information, sanitized build
manifest and compiler evidence, exact loaded-router identity, linked/runtime
BLAS identities, thread controls, machine identity, and installed dependency
versions. Hostnames, usernames, device identifiers, credentials, checkout
paths, and virtual-environment paths are rejected.

The Digits case uses a disposable exactly pinned Python 3.12 environment. Pip
resolution and imports must establish a complete NumPy/SciPy/scikit-learn
closure before the hypothesis may be accepted; the filtered design matrix is
fingerprinted in the protocol.

## Failure behavior and testing

Fixture-only adversarial tests are written before implementation. They mock
CDLL/build/runtime inputs and never load the solver. Validators collect stable
machine-readable reasons for schema, hash, protocol, provenance, timing, input,
diagnostic, and numerical failures. Timing-range misses remain observations and
do not affect numerical or evidence eligibility.

OpenMP control is runtime-neutral: `threadpoolctl` limits `user_api=openmp`
inside each router-call context and observes that same context. Candidate mode
requires exactly one identified OpenMP runtime and exact requested/observed
thread equality. BLAS and OpenMP pools are partitioned by `user_api`, so a
four-thread OpenMP pool is never mistaken for a four-thread BLAS pool.

Publication serializes with `allow_nan=False`, validates before any final
replacement, uses temporary files in the destination directory, and replaces
the checksum last. A serialization failure preserves existing valid files; any
mid-publication failure leaves no matching final checksum pair.

The only registry edits correct `guard.rank1_cost` and
`transition.rank_gate`; both remain publication blockers. CI adds one
nonnumerical gcc/portable contract step. Local verification is limited to the
commands explicitly authorized in the task.
