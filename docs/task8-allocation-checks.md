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

The count on library paths is 55 -> 35. The remaining 35 are LAPACK
workspaces and local buffers inside functions that now all have a failure
channel, so they are the mechanical part: check after the group, free what
was allocated, return through the channel.

Router output stayed bit-identical on 64 systems across 8 shapes and 2
seeds, and the changed paths are clean under ASan and UBSan.

## Why it was not a sweep

Most of the remaining sites sit in functions that cannot report failure:

- `bs_init(BState*, int)` — `static void`. It allocates `n*n` doubles for `Q`
  and `n` for `x`, checks neither, and has no way to say so. Its callers
  proceed to write into `Q`. Closing this means changing the signature to
  return a status and updating every caller so the failure reaches
  `CLS_FAIL`.
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
