# The API, without the manuscript

This document is written for someone who has not read `paper.tex` and wants to
call the library correctly. It covers what each entry point promises, what the
return values mean, and — the part that is easy to get wrong — what they do
*not* mean.

Three headers make up the public interface. Everything in `src/` is internal,
including `formation_guard.h`, whose symbols are visible in the fast library
only because that library is linked from strictly and loosely compiled objects
together.

| Header | Layer | Compiled with |
|---|---|---|
| `<affine_bundle/router.h>` | fast classification, untrusted | `-ffast-math` |
| `<affine_bundle/stream.h>` | incremental classification, untrusted | `-ffast-math` |
| `<affine_bundle/certified_api.h>`, `<affine_bundle/status_certificate.h>` | proof objects and verifier, trusted | `-frounding-math -fno-fast-math` |

---

## 1. The question the library answers

Given a dense real system `Ax = b` with no assumption of consistency, full
rank, or uniqueness, the library answers **which of those it can establish**,
and hands back an object that can be checked independently of how it was
found.

It is not primarily a solver. A solution comes back only in the cases where a
solution exists and the library was able to accept a witness for it.

---

## 2. Two layers, and why the separation is load-bearing

The **router** is fast and untrusted. It proposes a classification. Nothing it
computes is evidence of anything. It is compiled with `-ffast-math`, under
which the compiler may reassociate arithmetic and fold `isfinite()` to a
constant — which it does, which is why the router's non-finite input check is
a bit-pattern test on the exponent field rather than a call to `isfinite`.

The **checker** is slow and trusted. It recomputes every bound from the source
data under directed rounding and owns every radius it reports. It never reads
a number the router produced.

A change that lets a router output feed a certificate is a change to the
soundness argument of the library, not an optimisation. This is the one
invariant to preserve when modifying anything here.

---

## 3. The status model

Five statuses, reported in `out[ABS_OUT_STATUS]`.

| Status | Value | What it asserts |
|---|---|---|
| `ABS_STATUS_UNIQUE` | 1 | the solution set is a single point |
| `ABS_STATUS_INFINITE` | 2 | consistent, solution set of dimension > 0 |
| `ABS_STATUS_INCONSISTENT` | 3 | no solution exists |
| `ABS_STATUS_FAIL` | 4 | **nothing about the data** — a refusal on resource grounds |
| `ABS_STATUS_UNDECIDABLE` | 5 | the data sits too close to a rank transition for a point answer |

### `FAIL` and `UNDECIDABLE` are opposite kinds of statement

This is the distinction the whole design rests on, and the one most likely to
be collapsed by a caller writing `if (status >= 4) goto error;`.

`FAIL` means the library ran out of a resource. There may well be a unique
solution; the library is not saying otherwise. The rank fields carry no
information and must not be read.

`UNDECIDABLE` is a *result*. It says something specific and checked about the
data: the distance from some direction to the accumulated row space could not
be placed on either side of the decision band, so no point rank is defensible.
In exchange the library returns a **rank interval** `[out[ABS_OUT_RANK_LO],
out[ABS_OUT_RANK_HI]]`, which is more information than a point rank obtained
by rounding a borderline quantity to whichever side it fell on.

Treating the two alike discards the stronger of the two answers and keeps the
weaker.

Before `v0.4.0` both mapped onto the value 4 in `out[0]` and the raw class had
to be read from `out[9]`. The two fields now agree; `out[9]` is retained only
so that callers written against the old behaviour keep working.

### Certainty

`out[ABS_OUT_CERTAINTY]` reports how the status was reached:

- `ABS_CERTAINTY_DETERMINISTIC` (1) — no randomised step was used.
- `ABS_CERTAINTY_RANDOMISED` (2) — a randomised acceptance was used, and the
  rank interval widens to `[rank, min(m, n)]` to reflect it.
- `ABS_CERTAINTY_NONE` (3) — `FAIL` or `UNDECIDABLE`.

The widening is information, not a formality. A randomised `UNIQUE` at
`[r, min(m,n)]` is a weaker claim than a deterministic `UNIQUE` at `[r, r]`,
and the two are distinguishable without reading the source.

---

## 4. Reading the output vector

`bsolve_router_meta_api` writes `ABS_OUT_LEN` = 11 doubles. Fields carry
information only in the cases noted.

| Index | Name | Valid when |
|---|---|---|
| 0 | `ABS_OUT_STATUS` | always |
| 1 | `ABS_OUT_CERTAINTY` | always |
| 2 | `ABS_OUT_RANK` | point rank; meaningless on `FAIL`; on `UNDECIDABLE` the interval, not this field, is the answer |
| 3, 4 | `ABS_OUT_RANK_LO`, `ABS_OUT_RANK_HI` | the supported rank interval; meaningless on `FAIL` |
| 5 | `ABS_OUT_RELRES` | relative residual; `NaN` on `FAIL`/`UNDECIDABLE`. On `INCONSISTENT` it is a diagnostic, **not** a solution error — there is no solution |
| 6 | `ABS_OUT_RELX` | error against the reference `xt`; `NaN` for `INCONSISTENT`, `FAIL`, `UNDECIDABLE` |
| 7 | `ABS_OUT_SECONDS` | wall clock. Not reproducible. **Every build-to-build comparison must exclude this field** |
| 8 | `ABS_OUT_FALLBACK` | internal escalation indicator |
| 9 | `ABS_OUT_CLS` | raw class; equal to field 0; compatibility only |
| 10 | `ABS_OUT_BERR` | rowwise mixed-norm backward error; finite only for a deterministic `UNIQUE` |

`xt` is optional and feeds field 6 only. Pass `NULL` when there is no
reference solution.

`sp`, `qv` and `alpha` select sketch width, verification passes and
acceptance scale; `(1, 2, 2)` is what the manuscript reports and what the
test batteries use. `alpha` reaches only some of the routes, so changing it
does not always change the answer.

`full` is accepted and ignored. It once selected a deterministic pass over
the whole source system instead of the randomised closure check. Every route
the router selects now does source-derived rank arbitration by itself where
the evidence requires it, so the choice is no longer the caller's; only the
embedded benchmark route still reads the flag. The parameter stays in the
signature because the entry points are exported. Passing 1 does not buy a
stricter answer, and passing 0 does not lose one.

**Non-finite entries** in `A` or `b` are rejected at the API boundary and
produce `FAIL`, with rank and residual carrying nothing.

**Not thread safe.** The diagnostic accessors (`bsolve_last_*`,
`bsolve_fg_counters_api`) read state left by the most recent call on any
thread.

---

## 5. The three thresholds

These are published in `router.h` because they are what a classification
*means*, not because they are convenient to expose.

```
ABS_DEPENDENCE_THRESHOLD  1e-13
ABS_GROWTH_THRESHOLD      1e-9
ABS_QUALITY_THRESHOLD     1e-14
```

### Dependence and growth decide the rank

Every routine that asks whether a direction is present in the row space builds
an a-posteriori interval for the distance and compares it against both
numbers:

- interval entirely **above** the growth threshold → the direction is present,
  the rank grows;
- interval entirely **below** the dependence threshold → the direction is
  absent, the row is dependent;
- otherwise → neither was established. This is where `UNDECIDABLE` comes from
  and where the streaming API defers a row.

The distances are measured on **row-normalised** data, so the thresholds are
scale-free: multiplying a row by a constant does not move it across them. This
is tested rather than assumed (`tests/test_threshold_contract.py`), because it
is the difference between a threshold that means something about the data and
one that means something about the units the data arrived in.

The same two numbers count the router's own rank interval — the lower end
counts diagonal magnitudes above the growth threshold, the upper end those at
or above the dependence threshold. The four decades between them are the width
of the library's declared ignorance.

### Quality decides whether `UNIQUE` keeps its witness

After a candidate `x` is found, the rowwise mixed-2-norm backward error

```
berr = max over rows i of   |a_i . x - b_i| / ( |b_i| + ||a_i||_2 * ||x||_2 )
```

is compared against `ABS_QUALITY_THRESHOLD`. Above it, the router does not
return `UNIQUE`: it retries through the trusted source-QRCP backend, and if
that still cannot produce an acceptable witness the status becomes
`UNDECIDABLE`. So a `UNIQUE` that fails on quality is reported as a refusal to
decide, never as a poor `UNIQUE`.

The contract this gives a caller:

```
status == ABS_STATUS_UNIQUE
  && certainty == ABS_CERTAINTY_DETERMINISTIC
  && isfinite(out[ABS_OUT_BERR])
implies  out[ABS_OUT_BERR] <= ABS_QUALITY_THRESHOLD
```

This is a statement about the **witness**, not about the distance to a nearby
exact system. Those distances are the η profile of section 6 and are bounded
by a different mechanism.

### What does not follow from their being public

They are not tolerances a caller passes in. Changing them changes what a
classification asserts; a build that alters them is a different library with
the same name. Use `abs_thresholds()` and `abs_quality_threshold()` to read
what the loaded library was built with — if those disagree with the macros,
the header and the shared object are from different builds.

---

## 6. Certificates and the η profile

`bsolve_certified_api` runs the router and then, **independently of what the
router chose**, attempts all three proof-object types: unique, infinite,
inconsistent. Each is generated, then handed to a verifier that recomputes its
bound from `A` and `b` under directed rounding.

### What η is

`eta_unique`, `eta_infinite`, `eta_inconsistent` are **upper bounds on the
distance to a nearby exact system of that type**. A finite value means the
corresponding proof object was independently accepted; the initial value is
`+INFINITY` and stays there if it was not.

`accepted_status_mask` carries the same information as bits: 1 unique,
2 infinite, 4 inconsistent.

### What η is not

**Not a confidence score, and `argmin` is not a classification rule.** The
three exact status sets are not topologically separated. At a consistent
rank-deficient point all three distances vanish simultaneously, so an argmin
there is selecting noise. Several η can be finite at once, and when they are,
each is a true statement about a *different* nearby system — not competing
estimates of one truth.

This is precisely why the library returns a classification with a certificate
instead of returning the nearest type, and why `UNDECIDABLE` exists as an
outcome rather than being resolved by taking a minimum.

### The compatibility projection

`certified_status` and `eta_status` are a projection of the profile onto the
type the router happened to propose:

- `certified_status` is `0` when the router-selected proof object was **not**
  accepted — not an error code, just the absence of an acceptance;
- `eta_status` is `+INFINITY` in that case.

They are conveniences for callers written before the profile existed. The
router-independent fields are the primary semantics; prefer them.

### `eta_x` is not part of the η family

Despite the name, `eta_x` is copied straight from the router's
`ABS_OUT_BERR` — the backward error of the router's own witness. It comes from
the **untrusted** layer, is `NaN` outside a deterministic `UNIQUE`, and is not
a distance to a nearby exact system. Do not read it alongside the other three
as if it were the fourth coordinate of the same profile.

### Generator and verifier codes

`*_generator_code` and `*_verifier_code` are zero when the step succeeded and
nonzero otherwise. The nonzero values are diagnostics for reading the source,
not a stable enumeration; treat any nonzero as "this type was not accepted"
and do not branch on the specific value.

### Verifying a witness directly

`status_certificate.h` exposes the verifier without the driver:
`bs_verify_unique`, `bs_verify_infinite`, `bs_verify_inconsistent` return `0`
**only** when the object is accepted, and write the radius they own. For the
inconsistent case, `ytb_lo`/`ytb_hi` bound a positive power-of-two
normalisation of `yᵀb`; their **sign**, not their magnitude, is the certified
diagnostic. Witnesses are freed with the matching `bs_*_witness_free`.

---

## 7. Incremental classification

`stream.h` keeps the affine bundle as persistent state, costing `O(n·r)` per
row rather than the `O(m)` per row a caller pays by re-running the batch
router on each growing prefix.

```c
ABSStream *s = abs_stream_create(n);      /* NULL on bad n or allocation failure */
int rc = abs_stream_insert(s, row, rhs);
abs_stream_status(s, out);                /* out has the router.h layout */
abs_stream_destroy(s);
```

`abs_stream_create` allocates O(n) state and reusable insertion scratch.  The
row-major basis grows geometrically with independent rows and occupies O(n·r)
at rank r.  A constructor failure returns `NULL`; a later basis-growth failure
is distinct and leaves the row retryable.

| Insert code | Value | Meaning |
|---|---|---|
| `ABS_INSERT_ABSORB` | 0 | dependent and compatible; state unchanged apart from bookkeeping |
| `ABS_INSERT_GROW` | 1 | the row enlarged the row space |
| `ABS_INSERT_DEFER` | 2 | neither could be established; the row is **not** in the state and the stream stays open |
| `ABS_INSERT_CONTRA` | −1 | the row contradicts the accumulated system; the stream is now **closed** |
| `ABS_INSERT_EINVAL` | −2 | null argument or non-finite entry; nothing asserted, state unchanged |
| `ABS_INSERT_ENOMEM` | −3 | basis growth failed; row not counted, state unchanged, retry allowed |

Three properties worth knowing before designing around this:

**Deferral is normal, not an error.** A deferred row lands inside the band
between the two thresholds. The rank becomes the interval `[r, r + deferred]`
capped at `n`, and the status becomes `UNDECIDABLE`. Both ends are sound: the
inserted rows are a subset of the rows seen, so their rank is a lower bound,
and `d` deferred rows can raise the rank by at most `d`.

With any row deferred the status is `UNDECIDABLE` **even when `r == n`**. A
deferred row is unresolved in both directions at once — it may have been
independent, and it may have been contradictory — so neither the rank nor the
consistency of the whole set has been established.

**Order matters.** Two permutations of the same rows can land on opposite
sides of a threshold, and a row deferred early may have been resolvable later.
This is a property of incremental classification, not of this implementation.
A caller needing an order-independent answer wants the batch router.

**After closure the counts stop.** A row offered to a closed stream is
rejected without being examined and does not count as processed, so
`abs_stream_counts` stops advancing while the caller may keep offering rows.
Compare against your own count if you need to know where the stream stopped
looking.

`abs_stream_status` fills status, certainty, rank, both interval ends and the
raw class; sets `ABS_OUT_RELRES`, `ABS_OUT_RELX` and `ABS_OUT_BERR` to `NaN`,
because a residual needs the whole system, which a stream does not retain; and
sets `ABS_OUT_SECONDS` to zero. `abs_stream_solution` writes `x` and returns 1
only when the stream is open with no deferred row.

**A stream answer is router-grade.** "Certified" in this context means the
decision carries an interval and a region of refusal. It does not mean the
strict floating-point contract: this code lives in the fast library. Proof
objects need the whole system at once and have no incremental form.

**One stream, one thread.**

---

## 8. Guarantees, and where they stop

What is guaranteed:

- The classification returned is the one the documented thresholds imply for
  the data as given, with `UNDECIDABLE` returned in preference to a point
  answer the thresholds do not support.
- A finite η means a verifier that reads only `A`, `b` and the witness
  accepted that witness under directed rounding.
- A deterministic `UNIQUE` with finite `berr` satisfies the quality bound.
- `FAIL` asserts nothing about the data, and no resource failure is ever
  converted into a status verdict.

What is not:

- **η magnitudes are platform-dependent** at machine scale — the same system
  yields values differing in the last digits across machines and BLAS builds.
  Structural claims (counts, statuses, acceptance masks) are exact and
  reproducible; measured radii are not. `tests/check_paper_claims.py` keeps
  the two apart on purpose.
- **The rounding contract rests on `-frounding-math`.** GCC silently ignores
  `#pragma STDC FENV_ACCESS`. Compiler-independent closure would need
  validated interval arithmetic or a formally verified checker. The strict
  layer is a research prototype in this specific sense.
- **Property-based testing falsifies; it does not prove.** The batteries
  (8 335 and 2 271 checks) rule out large classes of implementation error and
  are not a substitute for the manuscript's argument.
- **Resource failure is not numerical uncertainty.** Checked batch allocation
  failures return `FAIL`; stream basis-growth failure returns
  `ABS_INSERT_ENOMEM` without changing the rank or row count.  The allocation
  audit reports zero unchecked sites on library paths; see
  [`task8-allocation-checks.md`](task8-allocation-checks.md).
- **This is a dense solver.** Sparse problems need a different implementation.

Performance is not a guarantee of this API and is deliberately not summarised
here. Where the method is fast, where it is at parity and where it is far
slower is a measured question, kept in
[`benchmark-findings.md`](benchmark-findings.md) and
[`suitesparse-findings.md`](suitesparse-findings.md) with the harness that
produces each number.

---

## 9. A minimal correct call

```c
#include <affine_bundle/router.h>

double out[ABS_OUT_LEN];
bsolve_router_meta_api(A, b, NULL, m, n, 1, 2, 2, 0ULL, 0, out);

switch ((int)out[ABS_OUT_STATUS]) {
case ABS_STATUS_UNIQUE:
    /* a solution exists and is unique.  out[ABS_OUT_BERR] is bounded by
       ABS_QUALITY_THRESHOLD when certainty is DETERMINISTIC. */
    break;
case ABS_STATUS_INFINITE:
case ABS_STATUS_INCONSISTENT:
    /* rank and rank interval are meaningful */
    break;
case ABS_STATUS_UNDECIDABLE:
    /* a result: read [out[ABS_OUT_RANK_LO], out[ABS_OUT_RANK_HI]].
       Do not read out[ABS_OUT_RANK]. */
    break;
case ABS_STATUS_FAIL:
    /* not a statement about the data.  Read nothing else. */
    break;
}
```

Working programs are in `examples/`: `classify.c` for the status model,
`certify.c` for the η profile, `streaming.c` for incremental use. They link
only against the installed interface and never see `src/`.

---

## 10. Exported but not public

The library also exports `bsolve_fast_api`, `bsolve_auto_api`,
`bsolve_auto_qr_api`, `bsolve_block_api`, `bsolve_global_api`,
`bsolve_global_qr_api`, `bsolve_lapack_api`, `bsolve_seq_api` and
`bsolver_bench_embedded_main`.  The first two of the `global` pair are the
same route: `bsolve_global_api` forwards to `bsolve_global_qr_api`. These are individual routes and a benchmark
driver called from the manuscript's Python scripts. They run one strategy and
report what it produced; they do not classify, and they are deliberately
declared in no header. Presence in the dynamic symbol table is not the same as
being public API.

The same applies to the `fg_*` primitives of the formation guard.
