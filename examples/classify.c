/*
 * classify.c -- what the router answers, and how to read the answer.
 *
 * Three systems of the same shape are built by hand: one with a unique
 * solution, one rank deficient and consistent, one with no solution at all.
 * The router is asked about each.
 *
 * The point of the example is the reading, not the call.  Two things in
 * particular:
 *
 *   1. FAIL and UNDECIDABLE are opposite kinds of statement and must not be
 *      collapsed into "did not work".  FAIL is a refusal on resource
 *      grounds and asserts nothing whatsoever about the data; UNDECIDABLE
 *      asserts that the data is too close to a rank transition for a point
 *      answer, and returns a rank interval instead.  A caller that treats
 *      both as failure discards the stronger of the two results.
 *
 *   2. The rank is an interval.  For a deterministic answer the interval is
 *      a point, [r, r].  When a randomised acceptance was used it widens to
 *      [r, min(m,n)], and that widening is information, not noise.
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <affine_bundle/router.h>
#include "example_data.h"

#define M 200
#define N 8

static const char *status_name(const double *out)
{
    switch ((int)out[ABS_OUT_STATUS]) {
    case ABS_STATUS_UNIQUE:       return "UNIQUE";
    case ABS_STATUS_INFINITE:     return "INFINITE";
    case ABS_STATUS_INCONSISTENT: return "INCONSISTENT";
    case ABS_STATUS_FAIL:        return "FAIL";
    case ABS_STATUS_UNDECIDABLE: return "UNDECIDABLE";
    default:                      return "?";
    }
}

static const char *certainty_name(const double *out)
{
    switch ((int)out[ABS_OUT_CERTAINTY]) {
    case ABS_CERTAINTY_DETERMINISTIC: return "deterministic";
    case ABS_CERTAINTY_RANDOMISED:    return "randomised";
    default:                          return "none";
    }
}

static void report(const char *label, const double *A, const double *b)
{
    double out[ABS_OUT_LEN];

    /* sp=1, qv=2, alpha=2 are the settings the manuscript reports.
       xt is NULL: there is no reference solution to compare against, so
       out[ABS_OUT_RELX] will not be meaningful. */
    bsolve_router_meta_api(A, b, NULL, M, N, 1, 2, 2, 20260908ULL, 0, out);

    printf("  %-26s %-13s rank %d in [%d, %d]   %s\n",
           label,
           status_name(out),
           (int)out[ABS_OUT_RANK],
           (int)out[ABS_OUT_RANK_LO],
           (int)out[ABS_OUT_RANK_HI],
           certainty_name(out));

    if ((int)out[ABS_OUT_STATUS] == ABS_STATUS_FAIL) {
        printf("    (a refusal on resource grounds: this says nothing about "
               "the system)\n");
    }
}

int main(void)
{
    static double A[M * N], b[M];
    int i, j;

    printf("affine-bundle-solver: %d x %d systems\n\n", M, N);

    /* Deterministic pseudo-random entries.  See example_data.h for why this
       is not a closed-form expression in i and j. */
    for (i = 0; i < M; i++)
        for (j = 0; j < N; j++)
            A[i * N + j] = ex_entry(1, i, j);
    /* b in the column space, so the system is consistent. */
    for (i = 0; i < M; i++) {
        double s = 0.0;
        for (j = 0; j < N; j++) s += A[i * N + j] * (j + 1);
        b[i] = s;
    }
    report("full rank, consistent", A, b);

    /* Make the last two columns copies of the first two: rank drops to N-2
       and the solution set gains two dimensions. */
    for (i = 0; i < M; i++) {
        A[i * N + (N - 2)] = A[i * N + 0];
        A[i * N + (N - 1)] = A[i * N + 1];
    }
    for (i = 0; i < M; i++) {
        double s = 0.0;
        for (j = 0; j < N; j++) s += A[i * N + j] * (j + 1);
        b[i] = s;
    }
    report("rank deficient, consistent", A, b);

    /* Push one entry of b off the column space.  With m >> n one perturbed
       row cannot be absorbed, and no solution exists. */
    b[M / 3] += 1.0;
    report("inconsistent", A, b);

    printf("\nFAIL and UNDECIDABLE are different answers, not degrees of the\n"
           "same one: the first asserts nothing about the system, the second\n"
           "asserts that a point rank is not available and returns an\n"
           "interval instead.\n");
    return 0;
}
