/*
 * router.h -- the fast classification router.
 *
 * Copyright 2026 Viktor Mikhalkin.  Licensed under the Apache License 2.0.
 *
 * These entry points were exported from libaffine_bundle_solver.so from the
 * first release but were declared in no header at all; the only written
 * record of their signatures was a ctypes block inside a test.  Calling them
 * from C was therefore impossible without reading the implementation.
 *
 * WHAT THE ROUTER IS, AND IS NOT
 *
 * The router is the fast, UNTRUSTED path.  It proposes a classification.
 * Nothing it computes is a proof of anything.  A claim about the data is
 * established only by the strict checker in <affine_bundle/certified_api.h>
 * and <affine_bundle/status_certificate.h>, which are compiled under a
 * different floating-point contract for that reason.  Feeding a router output
 * directly into a certificate changes the soundness argument of the library
 * and is not an optimisation.
 */
#ifndef AFFINE_BUNDLE_ROUTER_H
#define AFFINE_BUNDLE_ROUTER_H

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------------
 * Status codes, reported in out[0] of the meta API.
 *
 * out[0] carries the class itself, all five of them.  Earlier releases
 * mapped both FAIL and UNDECIDABLE onto 4, which erased the distinction the
 * classification rests on; out[9] carried the unmapped class and had to be
 * consulted to recover it.  The two fields now agree, and out[9] is kept
 * only so that callers written against the old behaviour keep working.
 * ---------------------------------------------------------------------- */
enum {
    ABS_STATUS_UNIQUE       = 1, /* the solution set is a single point       */
    ABS_STATUS_INFINITE     = 2, /* consistent, solution set has dimension>0 */
    ABS_STATUS_INCONSISTENT = 3, /* no solution exists                       */

    /* A refusal on resource grounds.  This asserts NOTHING about the data:
       there may well be a unique solution.  The rank fields carry no
       information in this case. */
    ABS_STATUS_FAIL         = 4,

    /* The data sits too close to a rank transition for a point answer.  This
       IS a statement about the data, and a much stronger one than FAIL: a
       rank INTERVAL [out[3], out[4]] is returned in place of a point rank.
       Which interval, and how wide, is decided against
       ABS_DEPENDENCE_THRESHOLD and ABS_GROWTH_THRESHOLD below. */
    ABS_STATUS_UNDECIDABLE  = 5
};

/* Raw internal class, reported in out[9].  Equal to out[0]; retained for
   callers written before out[0] carried the full class. */
enum {
    ABS_CLS_UNIQUE       = 1,
    ABS_CLS_INFINITE     = 2,
    ABS_CLS_INCONSISTENT = 3,
    ABS_CLS_FAIL         = 4,
    ABS_CLS_UNDECIDABLE  = 5
};

/* Certainty, reported in out[1]. */
enum {
    ABS_CERTAINTY_DETERMINISTIC = 1, /* reached without a randomised step    */
    ABS_CERTAINTY_RANDOMISED    = 2, /* a randomised acceptance was used;
                                        out[3..4] widen to [rank, min(m,n)] */
    ABS_CERTAINTY_NONE          = 3  /* FAIL or UNDECIDABLE                  */
};

/* ------------------------------------------------------------------------
 * Layout of the 11-element out vector of bsolve_router_meta_api.
 * ---------------------------------------------------------------------- */
enum {
    ABS_OUT_STATUS    = 0,  /* one of ABS_STATUS_*                          */
    ABS_OUT_CERTAINTY = 1,  /* one of ABS_CERTAINTY_*                       */
    ABS_OUT_RANK      = 2,  /* point rank; carries no information on FAIL,
                               and on UNDECIDABLE the interval below is the
                               answer rather than this field               */
    ABS_OUT_RANK_LO   = 3,  /* supported rank interval, lower end           */
    ABS_OUT_RANK_HI   = 4,  /* supported rank interval, upper end           */
    ABS_OUT_RELRES    = 5,  /* relative residual; NaN on FAIL/UNDECIDABLE.
                               For INCONSISTENT it is a diagnostic, not a
                               solution error: there is no solution.        */
    ABS_OUT_RELX      = 6,  /* error against the reference solution xt;
                               NaN for INCONSISTENT and FAIL/UNDECIDABLE,
                               where no solution witness is exported        */
    ABS_OUT_SECONDS   = 7,  /* wall clock.  Not reproducible.  Every
                               build-to-build comparison must exclude it.   */
    ABS_OUT_FALLBACK  = 8,  /* internal escalation indicator                */
    ABS_OUT_CLS       = 9,  /* raw class, ABS_CLS_*; equal to out[0]        */
    ABS_OUT_BERR      = 10, /* rowwise mixed-norm backward error, finite
                               only for a deterministic UNIQUE result       */
    ABS_OUT_LEN       = 11
};

/* ------------------------------------------------------------------------
 * The decision thresholds.
 *
 * These are part of the public contract, not implementation detail, because
 * they are what the classification means.  Every routine that decides
 * whether a direction is present in the row space compares an a-posteriori
 * distance interval against these two numbers:
 *
 *   distance interval entirely above ABS_GROWTH_THRESHOLD
 *       -> the direction is present; the rank grows
 *   distance interval entirely below ABS_DEPENDENCE_THRESHOLD
 *       -> the direction is absent; the row is dependent
 *   otherwise
 *       -> neither could be established.  This is where UNDECIDABLE comes
 *          from, and where the streaming API defers a row.
 *
 * The distances are measured on ROW-NORMALISED data, so the thresholds are
 * scale-free: multiplying a row by a constant does not move it across them.
 *
 * They set more than the refusal band of one routine.  The router's own rank
 * interval is counted with exactly these two numbers -- the lower end counts
 * diagonal magnitudes above the growth threshold, the upper end those at or
 * above the dependence threshold -- so out[ABS_OUT_RANK_LO] and
 * out[ABS_OUT_RANK_HI] are statements relative to them.  The four decades
 * between the two are the width of the library's declared ignorance.
 *
 * What does NOT follow from their being public: they are not tolerances a
 * caller passes in, and changing them is a change of what a classification
 * asserts, not a tuning knob.  A build that alters them is a different
 * library with the same name.
 *
 * Use abs_thresholds() to read the values the LIBRARY was built with.  If
 * they disagree with the macros below, the header and the shared object do
 * not come from the same build.
 * ---------------------------------------------------------------------- */
#define ABS_DEPENDENCE_THRESHOLD 1e-13
#define ABS_GROWTH_THRESHOLD     1e-9

void abs_thresholds(double *dependence, double *growth);

/* ------------------------------------------------------------------------
 * The solution-quality threshold.
 *
 * The two thresholds above decide the RANK.  This one decides whether a
 * UNIQUE classification is allowed to keep its solution witness, and it is
 * published for the same reason: it changes which status comes back.
 *
 * After a candidate solution x is found, the rowwise mixed-2-norm backward
 * error is measured,
 *
 *     berr = max over rows i of  |a_i . x - b_i|
 *                                ---------------------------
 *                                |b_i| + ||a_i||_2 * ||x||_2
 *
 * and compared against ABS_QUALITY_THRESHOLD.  Above it, the router does not
 * return UNIQUE.  It first retries through the trusted source QRCP backend,
 * and if that still cannot produce an acceptable witness the status becomes
 * UNDECIDABLE.  So a UNIQUE that fails on quality is reported as a refusal to
 * decide, not as a poor UNIQUE, and a caller never receives a unique-solution
 * claim backed by a witness the library itself would not accept.
 *
 * The contract this gives the caller:
 *
 *     out[ABS_OUT_STATUS] == ABS_STATUS_UNIQUE
 *       and out[ABS_OUT_CERTAINTY] == ABS_CERTAINTY_DETERMINISTIC
 *       and out[ABS_OUT_BERR] finite
 *     implies  out[ABS_OUT_BERR] <= ABS_QUALITY_THRESHOLD
 *
 * The denominator makes berr scale-free per row, so the threshold means the
 * same thing whatever units the system arrives in.
 *
 * Note that this is a statement about the WITNESS, not about the distance to
 * a nearby exact system.  Those distances are the eta profile of
 * <affine_bundle/certified_api.h> and are bounded independently.
 * ---------------------------------------------------------------------- */
#define ABS_QUALITY_THRESHOLD 1e-14

double abs_quality_threshold(void);

/* ------------------------------------------------------------------------
 * Entry points.
 *
 * A and b are read in row-major order, A as m*n doubles and b as m.
 * xt is an optional reference solution of length n used only to fill
 * out[ABS_OUT_RELX]; pass NULL when there is none.
 * out must have room for ABS_OUT_LEN doubles.
 *
 * sp, qv and alpha select the sketch width, the number of verification
 * passes and the acceptance threshold scale; (1, 2, 2) is what the
 * manuscript reports and what the batteries use.  seed drives the
 * randomised steps.  full requests the non-sketched path.
 *
 * Non-finite entries in A or b are rejected at this boundary and produce
 * FAIL, with the rank and residual fields carrying no information.  The check is a bit-pattern test on the exponent field, because the
 * router is compiled with -ffast-math, under which the compiler is entitled
 * to fold isfinite() to a constant, and does.
 *
 * NOT thread safe.  The diagnostic accessors below read state left by the
 * most recent call on any thread.
 * ---------------------------------------------------------------------- */

void bsolve_router_meta_api(const double *A, const double *b, const double *xt,
                            int m, int n, int sp, int qv, int alpha,
                            unsigned long long seed, int full, double *out);

/* Same inputs, but out follows the older 7-field layout of fill_out:
   {cls, rank, fallback, accepted_random, seconds, relres, relx}.
   Prefer bsolve_router_meta_api: this one exports no rank interval. */
void bsolve_router_api(const double *A, const double *b, const double *xt,
                       int m, int n, int sp, int qv, int alpha,
                       unsigned long long seed, int full, double *out);

/* Meta output plus the grey source rows.  Returns the number of distinct
   grey row indices retained by the diagnostic buffer; up to grey_cap of them
   are copied into grey_rows. */
int bsolve_router_diag_api(const double *A, const double *b, const double *xt,
                           int m, int n, int sp, int qv, int alpha,
                           unsigned long long seed, int full, double *out,
                           int *grey_rows, int grey_cap);

/* State from the most recent router call. */
int    bsolve_last_grey_total_api(void);        /* grey events, repeats included */
double bsolve_last_orth_eta_api(void);          /* largest orthogonality eta     */
void   bsolve_last_core_rank_interval_api(int *out2); /* out2[0]=lo, out2[1]=hi  */
int    bsolve_last_core_qr_rank_api(void);

/* Formation-guard counters: checks, escalations, source-QRCP calls. */
void bsolve_fg_counters_api(unsigned long long *out3);
void bsolve_fg_counters_reset_api(void);

/* ------------------------------------------------------------------------
 * The library also exports bsolve_fast_api, bsolve_auto_api,
 * bsolve_auto_qr_api, bsolve_block_api, bsolve_global_api,
 * bsolve_global_qr_api, bsolve_lapack_api, bsolve_seq_api and
 * bsolver_bench_embedded_main.  Those are individual routes and a benchmark
 * driver, called from the manuscript's Python scripts.  They run one strategy
 * and report what it produced; they do not classify.  They are deliberately
 * not declared here: being present in the dynamic symbol table is not the
 * same as being public API, and a caller who wants a classification wants
 * bsolve_router_meta_api.
 *
 * The same applies to the fg_* primitives of the formation guard, which are
 * visible in the fast library only because it is linked from strictly and
 * loosely compiled objects together.
 * ---------------------------------------------------------------------- */

#ifdef __cplusplus
}
#endif

#endif /* AFFINE_BUNDLE_ROUTER_H */
