# Proposal: the incremental insertion API

Status: **implemented** in `include/affine_bundle/stream.h`, following
section 5 below with the field names changed (`ABS_INSERT_DEFER` rather
than `AMBIGUOUS`, since the row is set aside rather than lost). Section 7
remains open. The document is kept because it records why the certified
insertion routine was chosen over the threshold one, and that
reasoning is not visible from the resulting header. It exists because the
question "which `BState` invariants are internal" cannot be answered without
first noticing that there are **two** insertion routines, not one, and that
they disagree over a four-decade band of inputs.

## 1. There is no single `bs_insert`

| | `bs_insert` | `bs_insert_certified` |
|---|---|---|
| file | `src/bsolver_core.c` | `src/bsolver.c` |
| decides by | `gn > tolrank`, a caller-supplied threshold | interval `[mu_lo, mu_hi]` from the tracked orthogonality defect |
| grows when | `gn > tolrank` | `mu_lo > 1e-9` |
| absorbs when | `gn <= tolrank` | `mu_hi < 1e-13` |
| in between | there is no in between | returns `2`, ambiguous — it refuses |
| projection | two-pass MGS, scalar | `project_cgs2` via `dgemv_`, matrix form |
| defect bound | `bs_accumulate_new_q_defect` | switches to a theorem-derived bound at `r >= 96` |
| returns | 1 / 0 / -1 | 1 / 0 / -1 / **2** |

The plain routine has a single threshold and therefore always produces a
verdict. The certified routine carries an explicit region of refusal. That
region is where `UNDECIDABLE` comes from.

The handover document names `bs_insert` in `src/bsolver_core.c` as the
function to export. Exporting that one would ship, as the library's only
streaming interface, the routine whose verdict is backed by nothing — in a
library whose stated architecture is that the fast path may propose and only
the strict path may conclude.

## 2. The disagreement is measurable and wide

`A` is 1500 x 12 with the last column set to the first times `(1 + eps*sin i)`.
`bsolve_seq_api` is the loop over the plain `bs_insert`; the router reaches
the same data through the certified path.

```
       eps  seq (bs_insert)         router   rank seq/router
     0e+00         INFINITE       INFINITE       11/11
     1e-15         INFINITE       INFINITE       11/11
     1e-14         INFINITE       INFINITE       11/11
     1e-13         INFINITE       INFINITE       11/11
     1e-12         INFINITE    UNDECIDABLE       11/11    <--
     1e-11         INFINITE    UNDECIDABLE       11/11    <--
     1e-10         INFINITE    UNDECIDABLE       11/11    <--
     1e-09           UNIQUE    UNDECIDABLE       12/11    <--
     1e-08           UNIQUE         UNIQUE       12/12
     1e-06           UNIQUE         UNIQUE       12/12
```

Between `1e-12` and `1e-9` the threshold path returns a confident answer
exactly where the library's own machinery declines to. At `1e-9` the two do
not even agree on the rank. On the fifteen well-separated systems of
`tests/compare_builds.py` they agree everywhere, which is why this only shows
up if you go looking for it.

## 3. What is internal, and why

Field by field, with the reason it should not appear in a public contract.

**`orth_frob2`** — accumulated squared Gram defect, `long double`. It has no
single provenance. Below `r = 96` it is a measured quantity; above, a
theorem-derived bound; and `bs_set_backend_orth_bound` **overwrites** it with
a synthetic `64*eps*r` when the state was formed by a LAPACK backend instead
of by insertion. A public accessor would export a number whose meaning
depends on state history the caller cannot see. If a streaming caller needs
to know that orthogonality is degrading, that has to be a separate,
explicitly specified quantity, not this field.

**`Q`** — row-major internal basis storage.  The streaming implementation now
grows it geometrically with the rank; batch states may still reserve `n x n`.
Rows `0..r-1` are the basis and capacity beyond them is not state.  Exposing
the buffer would freeze both the layout and the growth policy.

**`r`** — the current rank of the accumulated row space. It is not a
classification. `r == n` means UNIQUE only along the sequential reading; the
router reaches `UNDECIDABLE` at full `r`, as the table above shows at
`eps = 1e-12`.

**`inconsistent`** — sticky and terminal. Once set, every further insert
returns `-1` and changes nothing. A streaming caller must be told that the
state is closed, not left to discover that its inserts stopped having effect.

**`x`** — a particular solution, meaningful only while `inconsistent == 0`.

## 4. Defects that only matter once this is public

Inside the library these are reachable only through the router, which
validates its inputs first. Exported, they become the caller's problem.

- The original `bs_insert` used two `alloca(n * sizeof(double))` buffers per
  row.  The implemented stream keeps this scratch on the heap and reuses it;
  large `n` no longer turns an insertion into an unchecked stack allocation.
- The original `bs_init` reserved `n x n` doubles for `Q` up front.  The
  implemented stream starts with O(n) state and grows `Q` geometrically.  A
  growth failure is reported separately and leaves the state unchanged.
- `tolrank` and `tolcon` are parameters of `bs_insert`, and the batch path
  passes `1e-10` and `2e-10` unconditionally. Exporting them makes the
  classification a function of caller-chosen constants. Exporting them
  *hidden* makes a documented threshold undocumented.
- The consistency threshold is `tolcon * (1 + |beta| + ||x||)`. It grows with
  the current solution, so the same row can be judged differently depending
  on what arrived before it. Order dependence is inherent, not a bug, but it
  is a contract term.

## 5. Proposed shape

Opaque handle, certified insertion, refusal preserved as a return value.

```c
typedef struct ABSStream ABSStream;

/* n columns.  Returns NULL if the O(n) initial state cannot be allocated. */
ABSStream *abs_stream_create(int n);
void       abs_stream_destroy(ABSStream *s);

enum {
    ABS_INSERT_GROW       =  1, /* the row enlarged the row space          */
    ABS_INSERT_ABSORB     =  0, /* dependent and compatible                */
    ABS_INSERT_CONTRA     = -1, /* contradiction; the stream is now closed */
    ABS_INSERT_DEFER      =  2, /* neither could be established; the state
                                   is unchanged and the stream stays open  */
    ABS_INSERT_EINVAL     = -2, /* invalid or non-finite input              */
    ABS_INSERT_ENOMEM     = -3  /* basis growth failed; retry is allowed    */
};

/* One row of length n and its right-hand side.  Rejects non-finite input at
   the boundary for the same reason the router does. */
int abs_stream_insert(ABSStream *s, const double *row, double rhs);

/* Classification of everything inserted so far, in the layout of
   <affine_bundle/router.h>.  ABS_OUT_SECONDS is not filled. */
void abs_stream_status(const ABSStream *s, double *out);
```

Five points the header would have to state, all of them consequences of the
above rather than choices:

1. `ABS_INSERT_DEFER` is a normal outcome, not an error. A caller that
   treats it as failure has re-created the threshold API.
2. After `ABS_INSERT_CONTRA` the stream is closed. Further inserts are
   rejected; the classification does not change.
3. Insertion order affects the result. Two permutations of the same rows may
   land on different sides of a threshold. This is a property of incremental
   classification, not of this implementation.
4. Not thread safe. One stream, one thread.
5. `ABS_INSERT_ENOMEM` is not a rank verdict. The row is not counted, the
   mathematical state is unchanged, and the caller may retry it.

Tolerances stay out of the signature. If they must be settable, that belongs
in a separate `abs_stream_create_ex`, so that the default path cannot make
the classification depend on a caller's constant by accident.

## 6. Acceptance, restated

The handover asks that "sequential insertion of m rows gives the same result
as the batch call on the same data". That has to name which batch call.

- Against `bsolve_seq_api`: exact agreement is expected and testable, because
  that function *is* the loop.
- Against `bsolve_router_meta_api`: agreement must not be promised. The
  router compresses to a core, escalates, and consults the source guard. The
  table in section 2 shows them disagreeing on both status and rank on
  ordinary inputs.

The useful test is therefore two-sided: exact equality against the
sequential path, and, against the router, agreement wherever the router does
not return `UNDECIDABLE` — with the disagreement band itself measured and
recorded rather than asserted away.

## 7. Resolved: the thresholds are public

`BS_GROW_THR` and `BS_DEP_THR` are now `ABS_GROWTH_THRESHOLD` and
`ABS_DEPENDENCE_THRESHOLD` in `include/affine_bundle/router.h`, with the
internal names defined from them so there is one source of truth. The reason
they belong there is broader than the streaming API: the router's own rank
interval is counted against exactly these two numbers, so
`out[ABS_OUT_RANK_LO]` and `out[ABS_OUT_RANK_HI]` are statements relative to
them and were previously statements relative to nothing a reader could see.

`abs_thresholds()` reports what the shared object was built with, so a
mismatch between a header and a library is detectable rather than silent.
`tests/test_threshold_contract.py` checks that the two agree, that the three
verdicts are separated where the contract says they are, and that the
thresholds are scale-free — the last being the property that makes them a
statement about the data rather than about its units.

## 8. Still open

`BS_SVD_DEP_THR` (1e-14) selects between branches inside the local dependency
SVD and does not by itself decide a status; it remains internal.

The stream's consistency tolerance, `2e-10`, differs in kind from the three
published thresholds: it is applied as `tolcon * (1 + |beta| + ||x||)`, so
unlike them it is *not* scale-free and depends on the solution accumulated so
far. Publishing it would promise something weaker, and the difference should
be stated rather than smoothed over.

## 9. Resolved: the quality threshold is public

`BS_QUALITY_THR` is now `ABS_QUALITY_THRESHOLD` in
`include/affine_bundle/router.h`, with the internal name defined from it.
Unlike the two rank thresholds it does not decide a rank: it decides whether a
UNIQUE classification keeps its solution witness. Above it the router retries
through the trusted source QRCP backend and, failing that, returns
UNDECIDABLE — a refusal to decide rather than a poor UNIQUE.

Publishing it required closing a hole first. `source_qrcp_trusted` can return
UNIQUE having computed a backward error without comparing it against the
threshold. One of its two call sites in `solve_router` applied the quality
gate to that result and the other returned it directly, so the same helper's
output was authoritative on one path and required demotion on the other. The
gate is now applied at both. Measured on 500 adversarial systems the open path
never actually returned UNIQUE — every entry resolved to UNDECIDABLE — so the
defect was latent rather than observed, and closing it changed no output on
any input that could be constructed.

`tests/test_threshold_contract.py` checks the resulting contract: a
deterministic UNIQUE with a finite backward error is at or below the
threshold. The system family matters. Well-scaled systems of modest width
solve two orders under the threshold and would satisfy the assertion whatever
the library did, so the test spreads column scales and runs up to n=384, where
removing the demotion produces UNIQUE results carrying errors of 1.7e-14 at
n=32 and 1.5e-13 at n=384.
