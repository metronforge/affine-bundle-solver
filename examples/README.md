# Examples

Two programs, built by CMake and run in CI. Both link only against the
installed interface in `include/affine_bundle/`; neither sees `src/`.

## `classify.c`

Builds three systems of the same shape — unique, rank deficient consistent,
inconsistent — and asks the router about each.

What to look at is the reading of the answer, not the call:

- `out[ABS_OUT_STATUS] == 4` is **not** "failed". It is either `FAIL`, a
  refusal on resource grounds that asserts nothing about the data, or
  `UNDECIDABLE`, which asserts that the data sits too close to a rank
  transition for a point answer and returns a rank interval instead. The
  two are separated only by `out[ABS_OUT_CLS]`. Branching on `out[0]` alone
  reads a refusal as a conclusion.
- The rank is an interval. `[r, r]` for a deterministic answer,
  `[r, min(m,n)]` when a randomised acceptance was used. The widening is
  information.

## `certify.c`

Runs the audit API on three systems, the third deliberately close to a rank
transition, and prints the η profile.

The profile is a set of upper bounds on the distance to a nearby exact
system of each type, independently verified. It is not a set of scores:

- Several η can be finite at once, and each is then a true statement about a
  different nearby system.
- At a consistent degenerate point all three go to zero together, so
  `argmin η` would be selecting noise. This is why the library returns a
  classification with a certificate rather than an argmin, and why
  `UNDECIDABLE` exists as an outcome instead of being resolved by taking the
  nearest type.

## `streaming.c`

Feeds rows in one at a time through `<affine_bundle/stream.h>`.

Three parts. The first watches the rank grow and then stop growing. The
second is the one worth reading: a row that lands between the dependence
threshold and the growth threshold is **deferred** — left out of the state,
with the rank becoming an interval and the status `UNDECIDABLE`. Nothing
failed. Then a row in the span with the wrong right-hand side closes the
stream, and further inserts are rejected.

The third measures why the API exists: keeping an up-to-date classification
by re-running the batch router on each growing prefix costs tens of times
more, and the gap widens with the number of rows.

Two things the example is built to make visible:

- A deferred row needs `r < n` to be possible at all. At full rank nothing
  can grow, so the interval collapses and the question cannot arise.
- The data is generated with splitmix64, not with a closed-form expression
  in `i` and `j`. `A[i][j] = sin(c0 + i*c1 + j*c2)` gives a rank-2 matrix
  whatever its shape, and an example built on it reports rank 2 for
  everything. See `example_data.h`.
