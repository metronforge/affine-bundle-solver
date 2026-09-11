# Task 8, restated: allocation checks are a refactor, not a sweep

The handover recorded this as "~15 LAPACK workspace sites (`work`, `tau`,
`jpvt`, `iwork`) without a NULL check", to be closed by "a check after each
group, free what was allocated, return through `BS_FAIL_RESULT`". Two things
turned out differently. `experiments/allocation_audit.py` reproduces the
count.

## The count

```
src/bsolver.c          34 on library paths
src/bsolver_core.c     21 on library paths, 21 in the embedded benchmark
src/certified_api.c     0
src/formation_guard.c   0
src/status_certificate.c 0
```

55 on library paths, not 15.

**The strict layer is already clean.** `certified_api.c`,
`status_certificate.c` and `formation_guard.c` check every allocation,
including the combined guards of the form `if (An && bn && ybar0 && ...)`.
That is worth stating plainly: the part of the library whose output is a
certificate does not have this defect. A narrower scan reports these files as
unchecked and is wrong; the audit script documents the window it uses.

## Status

The refactor part is done. `bs_init` and `bs_copy` return a status,
`reset_source_guarded` and `try_secant_tail` carry a resource code distinct
from every value that is a statement about the data, `core_qr_state` and
`core_svd_state` free and return -1, and every caller maps the resource code
to `CLS_FAIL`. `sketch_remainder` needed no channel after all: its
per-thread scratch is an optimisation, so on allocation failure it falls
through to the serial loop, which computes the same sketch.
`abs_stream_create` no longer duplicates `bs_init`'s body to get a checkable
allocation.

The count on library paths is **55 -> 0**. The mechanical part followed the
refactor: check after each group, free what was allocated, return through the
channel the function now has. Two route helpers gained a resource code while
this was done. `try_square_lu_unique` and `try_sampled_source_fullrank` both
returned 0 on a failed allocation, and 0 there means "declined, try another
route" -- a smaller route that then succeeded would have turned the shortage
into a verdict about the data. Both now return -1, and `solve_router_raw`
maps it to `CLS_FAIL`.

The 30 remaining sites are in the embedded benchmark driver, which is not on
any library path and is reached only from `experiments/`.

Router output stayed bit-identical on 64 systems across 8 shapes and 2
seeds, and the changed paths are clean under ASan and UBSan.

## Why it was not a sweep

Most of the remaining sites sit in functions that cannot report failure:

- The original `bs_init(BState*, int)` was `static void`, allocated `n*n`
  doubles for `Q` and `n` for `x`, and checked neither.  It now returns a
  status.  Batch states retain full basis capacity; the public stream uses
  checked O(n) initial state and grows basis rows separately.
- `sketch_remainder(...)` — `static void`. Allocates four per-thread buffers
  (`LC`, `Ld`, `LE`, `Lf`) before an OpenMP region.
- Several routes allocate a group and then enter a parallel region or a
  LAPACK call directly, so an early return needs a cleanup path that does not
  exist yet.

So the work is: give these functions a failure channel, thread it to the
callers, and only then add the checks. That is a small refactor of failure
propagation, and it should be scheduled as one rather than attempted as a
mechanical pass — a wrong free list turns a missing check into a double free,
which is worse than what it replaces.

## Risk, unchanged

The handover's assessment still holds: the large allocations upstream are
checked and return `CLS_FAIL` before these are reached, so this is hygiene
rather than a live defect. Nothing here is a reason to delay the deposit.

## When it is done

Use `CLS_FAIL`, never `CLS_UNDECIDABLE`: a refusal on resource grounds
asserts nothing about the data, and `UNDECIDABLE` asserts that the data sits
near a rank transition. Since `v0.4.0` those two are distinct values in
`out[0]`, so conflating them is now visible to callers.

Acceptance is unchanged and easy to check: the router output stays
bit-identical on clean input, and `experiments/allocation_audit.py` reports
zero on library paths.

## Runtime workspace follow-up

The absence of unchecked allocations does not answer a separate performance
question: should repeated solves receive an opaque reusable workspace instead
of allocating LAPACK scratch internally?  A warmed, one-thread allocation
trace was run on the fast router before changing its API.  The interposer was
process-wide, so its time includes any allocation performed by BLAS and is an
upper bound on time the router could remove.

| shape | allocation calls | requested bytes | median router time | time inside allocation |
|---:|---:|---:|---:|---:|
| 256 x 256 | 9 | 1,067,008 | 0.868 ms | 0.011 ms (1.25%) |
| 512 x 512 | 9 | 4,231,168 | 4.576 ms | 0.077 ms (1.68%) |
| 1024 x 1024 | 9 | 16,850,944 | 24.145 ms | 0.302 ms (1.25%) |
| 8000 x 128 | 9 | 271,360 | 0.572 ms | 0.007 ms (1.22%) |
| 128 x 512 | 51 | 13,479,740 | 9.770 ms | 0.397 ms (4.07%) |
| 256 x 2048 | 51 | 166,738,748 | 127.315 ms | 1.868 ms (1.47%) |

The byte count is not avoidable work.  Buffers returned by `calloc` still
have to be cleared when reused, and every matrix consumed by LAPACK still has
to be filled.  The percentages therefore overstate the benefit of a reusable
workspace.  Even the 51-allocation wide route falls to 1.47% at its larger
representative size.

The three workspace queries in `core_qr_state` were measured separately by a
direct C harness against the same SciPy OpenBLAS symbols.  Their combined
median cost was 0.08--0.09 microseconds for QR cores from 512 x 128 through
2048 x 256.  Caching those query results cannot affect end-to-end time at the
reported precision.

**Decision:** retain internal checked allocations and do not add a public
workspace or an internal arena.  Revisit only with a batch/repeated-solve API
and evidence that allocator time, excluding mandatory buffer clearing, is a
material fraction of the call.  Requested bytes alone are not such evidence.
