# Cycle 2 — Implement exactly one bounded optimization

## PLAN

Hypothesis: the selected unique-verifier target can be reduced without changing
observable behavior. The invariant is that packed `L` is unit lower triangular
and packed `U` is upper triangular, so `(L*U)[lr,j]` has possible nonzero terms
only for `k <= min(lr,j)`. Preserve the original nonzero term order under both
directed-rounding passes. Own no new state; retain `pos[m]` and `evec[n]`, remove
only `lrow[n]` and `ucol[n]`, and restore the caller's rounding mode on success
and failure. Accept on structural reduction plus baseline/candidate semantic
agreement.

## DO

The test was added before implementation. RED was observed at link time because
the required test-only multiplication-counter symbols did not exist. The
smallest implementation added a private `packed_lu_interval` helper, changed
only the unique verifier's LU reconstruction, removed two temporary allocations,
and added a compile-time-only counter to a separately compiled test target. No
installed library exports that counter and no public header changed.

The n=4 structural fixture requires exactly 60 direct products versus 128 in
the baseline. It also starts in `FE_UPWARD`, verifies an exact identity-system
certificate, and proves exact restoration of `FE_UPWARD`.

## CHECK

- Structural GREEN: 60 products, expected 60; baseline formula 128.
- Focused native tests: 5/5 passed.
- Process-isolated public witness/combined snapshots: 12/12 cases equal.
- V31-025/026/027 full meaningful records: 3/3 equal with NaN/Infinity-safe
  canonicalization; every candidate recorded one router execution.
- Public dynamic symbols: no additions or removals between baseline and
  candidate `libstatus_verifier.so`.
- Ownership: no global production cache; removed `2*n*sizeof(double)` live
  storage and two allocation-failure sites; all retained storage is freed.
- Rounding: each packed entry still performs an explicit downward pass followed
  by an upward pass, and all exits restore the saved mode.

The one-off elapsed values in the correctness differential are retained but are
not performance evidence. They were not used to rerun or select results.

## ACT

Accept the implementation for Cycle-3 qualification. No second optimization is
authorized. The solver commit is `perf: skip structural zeros in unique verifier`.
