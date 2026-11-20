/* Count real LAPACK factorizations on the streaming insertion path.
   Link the fast router object with --wrap=dgesvd_ and the system LAPACK. */
#include <assert.h>
#include <stdio.h>
#include "affine_bundle/stream.h"

static int queries, factorizations;
static int last_m, last_n;

void __real_dgesvd_(char *, char *, int *, int *, double *, int *, double *,
                    double *, int *, double *, int *, double *, int *, int *);

void __wrap_dgesvd_(char *jobu, char *jobvt, int *m, int *n, double *a,
                    int *lda, double *sigma, double *u, int *ldu, double *vt,
                    int *ldvt, double *work, int *lwork, int *info) {
    if (*lwork == -1) {
        queries++;
    } else {
        factorizations++;
        last_m = *m;
        last_n = *n;
    }
    __real_dgesvd_(jobu, jobvt, m, n, a, lda, sigma, u, ldu, vt, ldvt,
                   work, lwork, info);
}

int main(void) {
    enum { n = 64, r = 31 };
    double row[n] = {0};
    ABSStream *s = abs_stream_create(n);
    assert(s);
    for (int j = 0; j < r; ++j) {
        row[j] = 1;
        assert(abs_stream_insert(s, row, 0) == ABS_INSERT_GROW);
        row[j] = 0;
    }
    row[0] = 1;
    int compatible = abs_stream_insert(s, row, 0);
    printf("basis rank %d, compatible duplicate rc=%d, SVDs=%d\n",
           r, compatible, factorizations);
    assert(compatible == ABS_INSERT_ABSORB && queries == 0 && factorizations == 0);
    int contradictory = abs_stream_insert(s, row, 1);
    printf("contradictory duplicate rc=%d, workspace queries=%d, SVDs=%d, dimensions=%dx%d\n",
           contradictory, queries, factorizations, last_m, last_n);
    assert(contradictory == ABS_INSERT_CONTRA && queries == 1 && factorizations == 1);
    assert(last_m == r + 1 && last_n == n);
    abs_stream_destroy(s);
}
