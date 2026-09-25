# Task-5 v3 PDCA: build-identity blocker

Verdict: **BUILD_IDENTITY_BLOCKER**. This is a new campaign identity,
`task5-v3-canonical-20260925`, not a reconstruction or continuation of v2.
No historical Task-5 result was imported as a canonical v3 record, and
aggregate verdict counts are not comparable. No publication claim changed.

## PLAN

The package was isolated at `/projects/affine-bundle-solver-task5-v3` as a
local Git repository. The solver source, local `main`, `origin/main`, and the
remote `main` ref all matched
`29a0401d92e4ba7c9197b71be5304d816af87957` before building.
The manifest design uses 27 new IDs (`V3-001` onward): 24 small slots
(maximum dimension 5) and 3 deferred bounded-large slots (maximum dimension
256). Wide, square and tall profiles cross clear-full, exact-deficient,
near-low, near-high, and zero spectra; compatible/incompatible RHS and scale
pair controls are included where mathematically possible. Expected solver
verdicts are not stored as manifest facts.

## DO

The deterministic generator, canonical manifest, derived initial ledger,
analytic materializer, and corrected standard/contract oracles were committed.
Two independent manifest/ledger generations were byte-identical. The new
manifest SHA-256 is
`25d53a99ae185843a4697b15f1c1312cd55daa5c90ad4ad891ffb1f2714a79a8`;
the ledger SHA-256 is
`ae1685b7a30733e8d5438b14ab3285814948058af0cd1a2fbde6cbab49134e40`.
Neither uses the historical v2 manifest hash or slot namespace.

The frozen solver was configured with GCC 15.2.0, system OpenBLAS/LAPACK,
`CMAKE_BUILD_TYPE=Release`, and empty `ABS_ARCH_FLAGS`, then built into
`build/solver`. Compiler/link probes completed. A partial machine-readable
build identity is `campaign/build-provenance.partial.json`.

## CHECK

`tests/test_campaign.py`: 3/3 PASS. `tests/test_oracles.py`: 8/8 PASS.
The scaled `diag(1,1e-10)` reproducer classified both scale 1 and 1e8 as
UNIQUE, with rank 2 and a scale-independent relative least-squares cutoff.
Exact deficiency, zero RHS, incompatible RHS, FULL/QR branches, threshold
neighborhood and repetition controls passed.

The first actual null-`xt` differential could not load the required combined
entry point: `libcertified_solver.so` at the frozen main commit does not export
`bsolve_certified_diag_api` (`nm -D` and `ctypes` agree). Source inspection
confirms that this symbol exists in the recovered historical dirty source but
not in frozen main. Frozen main exports `bsolve_certified_api`, which invokes
the router once but does not expose all retained router meta fields (notably
the historical residual/backward-error fields) in the certified result.
Calling a separate router-meta API would run the router again and alter the
one-execution contract. Building the dirty library, modifying the frozen
solver, or silently dropping retained fields is outside this task.

The uncommitted experimental null-`xt` wrapper and failing differential test
were removed with `apply_patch`; no candidate harness or runner is claimed.
No small-case native validation or timing telemetry was run. The partial
identity deliberately has null runner/harness/timing hashes. No later
bounded-large command is proposed because no valid runner exists yet.

## ACT

Stop at the ABI boundary. A separate decision is needed to either authorize
a compatible one-call diagnostic API in the solver or revise the campaign's
retained-field contract with an explicit new identity. Neither is assumed
here. The local v3 package remains useful as a deterministic manifest/oracle
foundation, but is **not** ready for bounded-large validation.

No N138, 2048/4096, complete v3, historical 177-case, or publication
benchmark run occurred. Solver source, historical archives, and `stash@{0}`
were not modified. Nothing was pushed, submitted as a PR, or merged.
