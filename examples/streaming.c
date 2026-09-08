/*
 * streaming.c -- classifying rows as they arrive.
 *
 * The batch entry points take the whole system and recompute from scratch,
 * so feeding them one new row at a time costs O(m) per row and the total
 * cost is quadratic in the number of rows.  A stream keeps the bundle as
 * state and pays O(n*r) per row regardless of how many rows came before.
 * Part three below measures that.
 *
 * The two parts before it are about the contract rather than the speed,
 * because the interesting thing about incremental classification is what
 * happens when a row cannot be classified at all.
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <affine_bundle/stream.h>
#include <affine_bundle/router.h>
#include "example_data.h"

static const char *name_of(const double *out)
{
    switch ((int)out[ABS_OUT_CLS]) {
    case ABS_CLS_UNIQUE:       return "UNIQUE";
    case ABS_CLS_INFINITE:     return "INFINITE";
    case ABS_CLS_INCONSISTENT: return "INCONSISTENT";
    case ABS_CLS_UNDECIDABLE:  return "UNDECIDABLE";
    default:                   return "FAIL";
    }
}

static void print_state(const ABSStream *st, const char *label)
{
    double out[ABS_OUT_LEN];
    long long seen = 0, deferred = 0;
    abs_stream_status(st, out);
    abs_stream_counts(st, &seen, &deferred);
    printf("    %-22s %-12s rank %d in [%d, %d]   seen %lld, deferred %lld\n",
           label, name_of(out), (int)out[ABS_OUT_RANK],
           (int)out[ABS_OUT_RANK_LO], (int)out[ABS_OUT_RANK_HI],
           seen, deferred);
}

static double now_seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

/* ---------------------------------------------------------------------- */
/* 1. The ordinary case: rank grows, then stops growing.                   */
/* ---------------------------------------------------------------------- */
static void part_one(void)
{
    enum { N = 6, ROWS = 40 };
    ABSStream *st = abs_stream_create(N);
    double row[N];
    int i, j, grow = 0, absorb = 0;

    printf("1. Rows arrive one at a time, %d columns\n", N);
    if (!st) { printf("    allocation failed\n"); return; }

    for (i = 0; i < ROWS; i++) {
        double rhs = 0.0;
        for (j = 0; j < N; j++) {
            row[j] = ex_entry(11, i, j);
            rhs += row[j] * (j + 1);   /* consistent by construction */
        }
        if (abs_stream_insert(st, row, rhs) == ABS_INSERT_GROW) grow++;
        else absorb++;

        if (i == 2 || i == 5 || i == ROWS - 1) {
            char label[32];
            snprintf(label, sizeof label, "after row %d", i + 1);
            print_state(st, label);
        }
    }
    printf("    %d rows enlarged the row space, %d were absorbed\n\n",
           grow, absorb);
    abs_stream_destroy(st);
}

/* ---------------------------------------------------------------------- */
/* 2. A row that cannot be classified, and a row that contradicts.         */
/* ---------------------------------------------------------------------- */
static void part_two(void)
{
    enum { N = 5 };
    ABSStream *st = abs_stream_create(N);
    double row[N];
    int i, j, rc;

    printf("2. A deferred row, then a contradiction\n");
    if (!st) { printf("    allocation failed\n"); return; }

    /* Only three rows into five columns: the span is a proper subspace, so
       there is room for a row to be genuinely undecided.  At full rank the
       question cannot arise -- nothing can grow -- and the interval
       collapses. */
    for (i = 0; i < 3; i++) {
        double rhs = 0.0;
        for (j = 0; j < N; j++) {
            row[j] = ex_entry(12, i, j);
            rhs += row[j] * (j + 1);
        }
        abs_stream_insert(st, row, rhs);
    }
    print_state(st, "3 ordinary rows");

    /* A row that is a copy of an earlier one perturbed into the band where
       the interval routine can establish neither independence nor
       dependence.  It is left out of the state and the rank becomes an
       interval; the status is UNDECIDABLE even though nothing failed. */
    {
        /* A row already inside the span, plus a component pointing out of it
           whose size lands between the dependence threshold (1e-13) and the
           growth threshold (1e-9).  Neither can be established. */
        double rhs = 0.0;
        for (j = 0; j < N; j++) {
            row[j] = ex_entry(12, 1, j) + 3e-11 * ex_entry(99, 0, j);
            rhs += row[j] * (j + 1);
        }
        rc = abs_stream_insert(st, row, rhs);
        printf("    insert returned %d (%s)\n", rc,
               rc == ABS_INSERT_DEFER  ? "DEFER"  :
               rc == ABS_INSERT_GROW   ? "GROW"   :
               rc == ABS_INSERT_ABSORB ? "ABSORB" : "other");
        print_state(st, "after the odd row");
    }

    /* Now a row in the span with the wrong right-hand side.  This closes
       the stream: the state is final and further inserts are rejected. */
    {
        double rhs = 0.0;
        for (j = 0; j < N; j++) {
            row[j] = ex_entry(12, 1, j);
            rhs += row[j] * (j + 1);
        }
        rhs += 1.0;
        rc = abs_stream_insert(st, row, rhs);
        printf("    insert returned %d (%s)\n", rc,
               rc == ABS_INSERT_CONTRA ? "CONTRA" : "other");
        print_state(st, "after the bad row");

        for (j = 0; j < N; j++) row[j] = 1.0;
        rc = abs_stream_insert(st, row, 1.0);
        printf("    a further insert returns %d; the stream stays closed\n\n", rc);
    }
    abs_stream_destroy(st);
}

/* ---------------------------------------------------------------------- */
/* 3. Why this exists: the batch path repeats itself, the stream does not. */
/* ---------------------------------------------------------------------- */
static void part_three(void)
{
    enum { N = 24, ROWS = 2000 };
    double *A = (double*)malloc((size_t)ROWS * N * sizeof(double));
    double *b = (double*)malloc((size_t)ROWS * sizeof(double));
    double out[ABS_OUT_LEN];
    ABSStream *st;
    double t0, t_stream, t_batch;
    int i, j;

    printf("3. Cost of following a growing system, %d columns\n", N);
    if (!A || !b) { free(A); free(b); printf("    allocation failed\n"); return; }

    for (i = 0; i < ROWS; i++) {
        double rhs = 0.0;
        for (j = 0; j < N; j++) {
            A[(size_t)i * N + j] = ex_entry(13, i, j);
            rhs += A[(size_t)i * N + j] * (j + 1);
        }
        b[i] = rhs;
    }

    /* Stream: one insert per arriving row. */
    st = abs_stream_create(N);
    if (!st) { free(A); free(b); printf("    allocation failed\n"); return; }
    t0 = now_seconds();
    for (i = 0; i < ROWS; i++)
        abs_stream_insert(st, A + (size_t)i * N, b[i]);
    t_stream = now_seconds() - t0;
    abs_stream_status(st, out);
    printf("    stream : %8.4f s   final %s, rank %d\n",
           t_stream, name_of(out), (int)out[ABS_OUT_RANK]);
    abs_stream_destroy(st);

    /* Batch: reclassify the whole prefix after each arrival, which is what a
       caller has to do today to keep an up-to-date answer. */
    t0 = now_seconds();
    for (i = 1; i <= ROWS; i++)
        bsolve_router_meta_api(A, b, NULL, i, N, 1, 2, 2, 7ULL, 0, out);
    t_batch = now_seconds() - t0;
    printf("    batch  : %8.4f s   final %s, rank %d\n",
           t_batch, name_of(out), (int)out[ABS_OUT_RANK]);

    if (t_stream > 0.0)
        printf("    ratio  : %.0fx   and it grows with the number of rows,\n"
               "             because the batch side repeats work the stream keeps.\n",
               t_batch / t_stream);

    free(A); free(b);
}

int main(void)
{
    printf("affine-bundle-solver: incremental classification\n\n");
    part_one();
    part_two();
    part_three();
    printf("\nA deferred row is a normal outcome.  It leaves the rank as an\n"
           "interval and the status UNDECIDABLE, which is the honest answer\n"
           "when neither independence nor dependence could be established.\n");
    return 0;
}
