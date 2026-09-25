# Task-5 v3 canonical campaign design

## Purpose and boundary

`task5-v3-canonical-20260925` is a new experiment, not a continuation of the
unrecoverable v2 manifest or Task-4 ledger. The package lives in its own local
Git repository. The solver is an external, hash-pinned dependency at
`29a0401d92e4ba7c9197b71be5304d816af87957`; no solver source is edited.
Old checkpoints inform test ideas only and are never imported as records.

## Components

- `task5v3/campaign.py` defines a small coverage matrix, validates it, and
  atomically writes canonical UTF-8 manifest JSON and JSONL ledger. Stable v3
  IDs and order indices are generated solely from that matrix. The ledger
  contains one initial `READY_SMALL` or `DEFERRED_BOUNDED_LARGE` row per slot.
- `task5v3/materialize.py` constructs finite, deterministic diagonal-profile
  matrices from each slot and an analytically compatible or incompatible RHS.
  No historical source data is needed. Scale pairs exercise oracle invariance.
- `task5v3/oracles.py` retains independent SVD and pivoted-QR rank measures,
  uses absolute `tau_abs` only for those measures, and sends relative
  `cond_rel` to SciPy `lstsq` (`gelsd` FULL, `gelsy` non-FULL). The published
  contract-oracle thresholds and classification rules remain unchanged.
- `task5v3/solver.py` imports the historical combined C ABI and retained field
  schema, but passes a genuine null `xt`. Test-only code calls the same ABI
  with a reference `xt` for differential controls. No RELX is retained.
- `task5v3/runner.py` runs only an explicit slot list and refuses a missing
  or mismatched manifest/ledger/library identity. It records disjoint phase
  durations and checks the sum against total case time before writing JSONL.

## Coverage and safety

The small set crosses wide/square/tall shapes with full, exactly deficient,
near-threshold-low/high, and zero spectra; compatible and incompatible RHS
where mathematically possible; and two scaled full-rank controls. A deferred
three-shape medium set is present only to define a later bounded validation.
No anticipated solver verdict is baked into the manifest except analytic
construction metadata. Small validation uses only dimensions at most 5.

Generation rejects duplicate IDs/orders, invalid shapes, impossible
incompatibility policies, and malformed slot parameters. Canonical writes
use sorted keys and a trailing newline; independent runs must be byte equal.
The ledger is derived from the manifest hash, never from historical records.
The runner requires explicit IDs, a dimension cap, and refuses deferred slots
unless a future command explicitly opts into bounded-large validation.

## Verification

Test-first controls cover manifest determinism and ledger bijection,
standard-oracle rank/scale/zero boundaries, null-`xt` semantic equality on
all retained fields across four outcomes and three shapes, timing non-overlap,
and explicit small-run selection. Build the pinned solver with portable GCC,
system BLAS/LAPACK, recorded compiler/linker flags, and one BLAS/OpenMP thread.
The initial campaign run is a predeclared subset of small slots only.

The identity record hashes generator, manifest, ledger, runner, imported
solver wrapper, three shared libraries, and build configuration; it records
versions, provider, thresholds, policies, thread settings, and timestamp.
Aggregate v2-v3 verdict comparisons and publication claims are out of scope.
