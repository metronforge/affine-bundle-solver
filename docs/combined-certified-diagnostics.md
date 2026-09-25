# Combined certified diagnostics API

`bsolve_certified_diag_api()` is an additive public entry point in
`libcertified_solver`. Include `<affine_bundle/certified_api.h>` and link the
installed `affine-bundle-solver::certified_solver` target. The existing
`bsolve_certified_api()` entry point and `BSCertifiedResult` layout are unchanged.

The new call executes the fast router once, copies its complete
`ABS_OUT_LEN` meta vector and diagnostic snapshot, and then attempts the same
three independent certificate profiles as the existing certified API. The
`certified` member has the same semantics as a separate call to
`bsolve_certified_api()` on the same input. It is not a second router result.
`router_meta[ABS_OUT_SECONDS]` is elapsed time and is not deterministic.

`xt` is optional. Passing `NULL` requires no reference-solution calculation;
only `router_meta[ABS_OUT_RELX]` may differ when a reference vector is
supplied. All other router and certificate fields are independent of `xt`.
The usual NaN sentinels remain: for example, RELX is NaN without a reference
solution or when no solution witness is exported. No RELX field is added to
`BSCertifiedResult`.

`grey_distinct_count` is the number of distinct source-row indices retained,
at most `BS_CERTIFIED_DIAG_GREY_CAP` (64). `grey_total_events` includes
repeated events and may exceed that count. Unused `grey_rows` entries are
zero. `last_orth_eta`, `core_rank_interval`, and `core_qr_rank` use the
router's existing diagnostic conventions, including `-1` for an unavailable
core rank. `formation_guard_counters` contains per-invocation counts, in the
order checks, escalations, source-QRCP calls. Callers must not reset global
counters to interpret them.

The call returns `0` after router and profile execution. It returns `1` for
invalid arguments: `out == NULL`, missing mandatory `A`/`b`, nonpositive
dimensions or router controls (`sp`, `qv`, `alpha`), nonfinite `A`/`b`, or an
unrepresentable matrix/router workspace extent. On such failure, a non-NULL result is zeroed
and the router is not called. A router resource failure is represented by
`ABS_STATUS_FAIL` in `router_meta` and return code `2`; the diagnostic
snapshot and attempted profiles remain available. This does not change the
router's numerical policy or the existing certified API's return codes.

The snapshot is taken inside the router library immediately after that
invocation, from its existing thread-local diagnostics. The new API adds no
mutable global state and has no process-global reset prerequisite. It does
not broaden the library's general concurrency guarantees; callers must not
concurrently share mutable input or output buffers.
