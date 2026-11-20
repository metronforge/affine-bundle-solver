/* Linux oracle fixture: copy the accepted witness with the smallest radius.
   The real verifier computes every verdict and output. Single-threaded probe. */
#define _GNU_SOURCE
#include <affine_bundle/status_certificate.h>
#include <dlfcn.h>
#include <math.h>
#include <string.h>

typedef int (*verify_fn)(const double *, const double *, int, int,
                         const BSInconsistentWitness *, double *, double *, double *);
static verify_fn verifier;
static double *record;
static int rows, pivot, attempts, successes;
static double best;

void capture_begin(double *y, int m, verify_fn real_verifier) {
    record = y;
    rows = m;
    verifier = real_verifier;
    pivot = -1;
    attempts = successes = 0;
    best = INFINITY;
}

int capture_end(int *counts, double *eta) {
    record = NULL;
    counts[0] = attempts;
    counts[1] = successes;
    *eta = best;
    return pivot;
}

int bs_verify_inconsistent(const double *A, const double *b, int m, int n,
                           const BSInconsistentWitness *w, double *lo,
                           double *hi, double *eta) {
    if (!verifier) verifier = (verify_fn)dlsym(RTLD_NEXT, "bs_verify_inconsistent");
    int rc = verifier(A, b, m, n, w, lo, hi, eta);
    if (record && m == rows) {
        ++attempts;
        if (rc == 0) {
            ++successes;
            if (*eta < best) {
                best = *eta;
                pivot = w->pivot_row;
                memcpy(record, w->y, (size_t)m*sizeof(double));
            }
        }
    }
    return rc;
}
