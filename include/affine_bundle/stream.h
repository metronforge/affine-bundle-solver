/*
 * stream.h -- incremental classification, one row at a time.
 *
 * Copyright 2026 Viktor Mikhalkin.  Licensed under the Apache License 2.0.
 *
 * The batch entry points recompute everything from scratch on every call, so
 * feeding rows in as they arrive costs O(m) per row.  A stream keeps the
 * affine bundle as persistent state and costs O(n*r) per row, independent of
 * how many rows have already been seen.
 *
 * WHICH INSERTION THIS IS
 *
 * The library has two row-insertion routines internally.  One decides by a
 * single threshold and therefore always returns a verdict.  The other builds
 * an a-posteriori interval for the distance from the row to the accumulated
 * row space, grows the rank only when that interval is entirely above the
 * growth threshold, absorbs the row only when it is entirely below the
 * dependence threshold, and DECLINES otherwise.
 *
 * This API is built on the second.  A row it cannot resolve is reported as
 * ABS_INSERT_DEFER and left out of the state, and the stream's rank estimate
 * becomes an interval rather than a point.  Measured on a family crossing a
 * rank transition, the two routines disagree over roughly four decades of
 * perturbation size, the threshold one answering confidently exactly where
 * the interval one refuses; see experiments/near_transition_band.py.
 *
 * WHAT THIS IS NOT
 *
 * "Certified" here means the decision carries an interval and a region of
 * refusal.  It does NOT mean the strict floating-point contract: this code
 * lives in the fast library, compiled with -ffast-math, and it proposes.
 * Proof objects and the eta profile come from
 * <affine_bundle/certified_api.h>, which needs the whole system at once and
 * has no incremental form.  A stream classification is a router-grade
 * answer, not a certificate.
 */
#ifndef AFFINE_BUNDLE_STREAM_H
#define AFFINE_BUNDLE_STREAM_H

#include <affine_bundle/router.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ABSStream ABSStream;

enum {
    ABS_INSERT_ABSORB =  0, /* dependent on what is already there, and
                               compatible with it; state unchanged apart
                               from bookkeeping                            */
    ABS_INSERT_GROW   =  1, /* the row enlarged the row space              */
    ABS_INSERT_DEFER  =  2, /* neither could be established.  The row is
                               NOT in the state and the stream stays open;
                               the rank becomes an interval and the status
                               becomes UNDECIDABLE.  This is a normal
                               outcome, not an error.                      */
    ABS_INSERT_CONTRA = -1, /* the row contradicts the accumulated system.
                               The stream is now CLOSED: further inserts
                               are rejected and the status stays
                               INCONSISTENT.                               */
    ABS_INSERT_EINVAL = -2  /* null argument, or a non-finite entry in the
                               row or the right-hand side.  Nothing about
                               the data is asserted and the state is
                               unchanged.                                  */
};

/*
 * Create a stream over n columns.
 *
 * Returns NULL if n is not positive or if the state could not be allocated.
 * The allocation is O(n^2) doubles and is made up front, so failure here is
 * a real outcome rather than a formality: a caller that ignores the return
 * value will crash on the first insert.
 */
ABSStream *abs_stream_create(int n);

/* Frees everything.  Safe on NULL. */
void abs_stream_destroy(ABSStream *s);

/*
 * Insert one row of n doubles and its right-hand side.  Returns one of the
 * ABS_INSERT_* codes above.
 *
 * ORDER MATTERS.  Two permutations of the same rows can land on different
 * sides of a threshold, and a row deferred early may have been resolvable
 * later.  This is a property of incremental classification and not of this
 * implementation; a caller that needs an order-independent answer wants the
 * batch router.
 *
 * NOT THREAD SAFE.  One stream, one thread.
 */
int abs_stream_insert(ABSStream *s, const double *row, double rhs);

/*
 * Classification of everything inserted so far, written into out in the
 * layout of <affine_bundle/router.h>.  out must have room for ABS_OUT_LEN
 * doubles.
 *
 * Filled: ABS_OUT_STATUS, ABS_OUT_CERTAINTY, ABS_OUT_RANK, ABS_OUT_RANK_LO,
 * ABS_OUT_RANK_HI, ABS_OUT_CLS.  Set to NaN: ABS_OUT_RELRES, ABS_OUT_RELX,
 * ABS_OUT_BERR -- a residual needs the whole system, which a stream does not
 * retain.  ABS_OUT_SECONDS is set to zero.
 *
 * The rank interval is [r, r + deferred], capped at n.  Both ends are sound:
 * the rows actually inserted are a subset of the rows seen, so their rank is
 * a lower bound; and d deferred rows can raise the rank by at most d.
 *
 * With any row deferred the status is UNDECIDABLE, including when r == n.
 * A deferred row is unresolved in both directions at once -- it may have
 * been independent, and it may have been contradictory -- so neither the
 * rank nor the consistency of the whole set has been established.
 */
void abs_stream_status(const ABSStream *s, double *out);

/*
 * Rows processed and rows deferred.  Either pointer may be NULL.
 *
 * A row offered after the stream closed on a contradiction is rejected
 * without being examined and does NOT count as processed, so after closure
 * the processed count stops advancing while the caller may keep offering
 * rows.  Compare it against your own count of rows offered if you need to
 * know where the stream stopped looking.
 */
void abs_stream_counts(const ABSStream *s, long long *seen, long long *deferred);

/* Current solution, n doubles, or 0 if the stream is closed or has any
   deferred row -- in those cases no solution has been established.
   Returns 1 when x was written. */
int abs_stream_solution(const ABSStream *s, double *x);

#ifdef __cplusplus
}
#endif

#endif /* AFFINE_BUNDLE_STREAM_H */
