/* Regression for reusable QRCP in the compatible-tall inconsistent witness. */
#include <affine_bundle/certified_api.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifdef ABS_SCIPY_BLAS
extern void __real_scipy_dgeqp3_(int*,int*,double*,int*,int*,double*,double*,int*,int*);
#define REAL_DGEQP3 __real_scipy_dgeqp3_
#define WRAP_DGEQP3 __wrap_scipy_dgeqp3_
#else
extern void __real_dgeqp3_(int*,int*,double*,int*,int*,double*,double*,int*,int*);
#define REAL_DGEQP3 __real_dgeqp3_
#define WRAP_DGEQP3 __wrap_dgeqp3_
#endif

static unsigned long tall_calls, tall_queries, tall_executes;
static uint64_t first_matrix_hash;
static int invariant = 1, pivot_seed_zero = 1;

static uint64_t hash_bytes(const void *data, size_t size)
{
    const unsigned char *p = (const unsigned char *)data;
    uint64_t h = UINT64_C(1469598103934665603);
    size_t i;
    for (i = 0; i < size; ++i) { h ^= p[i]; h *= UINT64_C(1099511628211); }
    return h;
}

void WRAP_DGEQP3(int *m, int *n, double *a, int *lda, int *jpvt,
                 double *tau, double *work, int *lwork, int *info)
{
    if (*m == 8 && *n == 4 && *lda == 8) {
        uint64_t h = hash_bytes(a, (size_t)(*lda) * (size_t)(*n) * sizeof(*a));
        int j;
        ++tall_calls;
        if (*lwork == -1) ++tall_queries; else ++tall_executes;
        if (first_matrix_hash == 0) first_matrix_hash = h;
        else if (h != first_matrix_hash) invariant = 0;
        for (j = 0; j < *n; ++j) if (jpvt[j] != 0) pivot_seed_zero = 0;
    }
    REAL_DGEQP3(m,n,a,lda,jpvt,tau,work,lwork,info);
}

static int run_once(void)
{
    /* Full-column-rank compatible system with four explicit zero rows.
       Every admissible left-null completion direction lives on a zero source
       row, forcing the historical fallback to scan the whole null space. */
    const double A[8*4] = {
        1,0,0,0,
        0,1,0,0,
        0,0,1,0,
        0,0,0,1,
        0,0,0,0,
        0,0,0,0,
        0,0,0,0,
        0,0,0,0
    };
    const double b[8] = {1,2,3,4,0,0,0,0};
    BSInconsistentWitness witness;
    int rc;
    tall_calls = tall_queries = tall_executes = 0;
    first_matrix_hash = 0; invariant = pivot_seed_zero = 1;
    rc = bs_generate_inconsistent_witness(A,b,8,4,&witness);
    if (rc == 0) bs_inconsistent_witness_free(&witness);
    if (rc != 6 || tall_calls != 2 || tall_queries != 1 || tall_executes != 1 ||
        !invariant || !pivot_seed_zero) {
        fprintf(stderr,
                "reusable QRCP rc=%d calls=%lu query=%lu execute=%lu invariant=%d jpvt_zero=%d hash=%016llx\n",
                rc,tall_calls,tall_queries,tall_executes,invariant,pivot_seed_zero,
                (unsigned long long)first_matrix_hash);
        return 0;
    }
    return 1;
}

int main(void)
{
    if (!run_once() || !run_once()) return 1;
    puts("reusable QRCP: PASS calls=2 query=1 execute=1 repeated=2");
    return 0;
}
