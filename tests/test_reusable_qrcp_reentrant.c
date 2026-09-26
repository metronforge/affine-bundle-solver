/* Invocation-local reusable QRCP state must remain reentrant. */
#include <affine_bundle/certified_api.h>
#include <omp.h>
#include <stdio.h>

int main(void)
{
    const double A[8*4] = {
        1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1,
        0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0
    };
    const double compatible[8] = {1,2,3,4,0,0,0,0};
    const double inconsistent[8] = {1,2,3,4,0,0,0,1};
    int failed = 0;
#pragma omp parallel for num_threads(4) reduction(|:failed)
    for (int iteration = 0; iteration < 64; ++iteration) {
        BSInconsistentWitness witness = {0};
        const double *b = (iteration & 1) ? inconsistent : compatible;
        int rc = bs_generate_inconsistent_witness(A,b,8,4,&witness);
        if ((iteration & 1) ? rc != 0 : rc != 6) failed = 1;
        bs_inconsistent_witness_free(&witness);
    }
    if (failed) { fputs("reentrant reusable QRCP failure\n",stderr); return 1; }
    puts("reentrant reusable QRCP: PASS threads=4 calls=64");
    return 0;
}
