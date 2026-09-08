/*
 * certify.c -- the eta profile, and why argmin(eta) is not a classifier.
 *
 * bsolve_certified_api runs the fast router and then, independently of what
 * the router chose, attempts a proof object of each of the three types.  A
 * finite eta means the corresponding proof object was independently
 * accepted, and the value is an upper bound on the distance to a nearby
 * exact system of that type.
 *
 * That is a weaker and more useful statement than it looks, and the example
 * is here to make the difference visible:
 *
 *   - Each eta bounds EXISTENCE of a nearby system of that type.  It is not
 *     a confidence, not a probability, not a score.
 *
 *   - Several etas can be finite at once.  A system that is nearly rank
 *     deficient is near a system with infinitely many solutions AND near one
 *     with exactly one, and both bounds are then true statements.
 *
 *   - At a consistent degenerate point all three distances go to zero
 *     together.  Picking the smallest eta would then be picking noise.  This
 *     is why the library returns a classification with a certificate and not
 *     an argmin over the profile, and why UNDECIDABLE exists as an outcome
 *     rather than being resolved by taking the nearest type.
 *
 * The third system below is built to sit close to a rank transition on
 * purpose, so the profile is worth looking at rather than obvious.
 */
#include <stdio.h>
#include <math.h>
#include <affine_bundle/certified_api.h>
#include <affine_bundle/router.h>
#include "example_data.h"

#define M 300
#define N 6

static void show_eta(const char *name, double eta, int accepted)
{
    if (accepted && isfinite(eta)) printf("    eta_%-13s %.6e\n", name, eta);
    else                           printf("    eta_%-13s  --  (no proof object accepted)\n", name);
}

static void audit(const char *label, const double *A, const double *b)
{
    BSCertifiedResult r;
    int rc = bsolve_certified_api(A, b, NULL, M, N, 1, 2, 2, 20260908ULL, 0, &r);

    printf("  %s\n", label);
    if (rc != 0) {
        printf("    audit returned %d; no profile\n\n", rc);
        return;
    }
    printf("    router proposed status %d, rank %d in [%d, %d]\n",
           r.fast_status, r.rank_estimate, r.rank_lo, r.rank_hi);

    show_eta("unique",       r.eta_unique,       r.accepted_status_mask & 1);
    show_eta("infinite",     r.eta_infinite,     r.accepted_status_mask & 2);
    show_eta("inconsistent", r.eta_inconsistent, r.accepted_status_mask & 4);

    {
        int k = 0;
        if (r.accepted_status_mask & 1) k++;
        if (r.accepted_status_mask & 2) k++;
        if (r.accepted_status_mask & 4) k++;
        if (k > 1) {
            printf("    %d proof objects accepted at once: each bound is a true\n"
                   "    statement about a DIFFERENT nearby exact system.  The\n"
                   "    smallest of them is not the answer.\n", k);
        }
    }
    printf("\n");
}

int main(void)
{
    static double A[M * N], b[M];
    int i, j;

    printf("affine-bundle-solver: nearby-status profile, %d x %d\n\n", M, N);

    for (i = 0; i < M; i++)
        for (j = 0; j < N; j++)
            A[i * N + j] = ex_entry(2, i, j);
    for (i = 0; i < M; i++) {
        double s = 0.0;
        for (j = 0; j < N; j++) s += A[i * N + j] * (j + 1);
        b[i] = s;
    }
    audit("well separated, consistent", A, b);

    /* Exactly rank deficient: the last column repeats the first. */
    for (i = 0; i < M; i++) A[i * N + (N - 1)] = A[i * N + 0];
    for (i = 0; i < M; i++) {
        double s = 0.0;
        for (j = 0; j < N; j++) s += A[i * N + j] * (j + 1);
        b[i] = s;
    }
    audit("exactly rank deficient", A, b);

    /* Near the transition: the repeated column is nudged by a quantity a few
       orders above the unit roundoff.  Whether this system "is" rank
       deficient is not a question the data answers. */
    for (i = 0; i < M; i++)
        A[i * N + (N - 1)] = A[i * N + 0] * (1.0 + 1e-12 * ex_value(9000 + i));
    for (i = 0; i < M; i++) {
        double s = 0.0;
        for (j = 0; j < N; j++) s += A[i * N + j] * (j + 1);
        b[i] = s;
    }
    audit("close to a rank transition", A, b);

    printf("A finite eta bounds the distance to a nearby exact system of that\n"
           "type.  It is not a score, and argmin over the profile is not a\n"
           "classification rule.\n");
    return 0;
}
