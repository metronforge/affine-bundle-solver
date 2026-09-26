/* Allocation-failure cleanup for the private reusable QRCP state. */
#include <affine_bundle/certified_api.h>
#include <stdio.h>
#include <stdlib.h>

static int allocation_index, fail_at, failure_observed;

void *abs_test_qrcp_malloc(size_t size)
{
    ++allocation_index;
    if (allocation_index == fail_at) { failure_observed = 1; return NULL; }
    return malloc(size);
}

void *abs_test_qrcp_calloc(size_t count,size_t size)
{
    ++allocation_index;
    if (allocation_index == fail_at) { failure_observed = 1; return NULL; }
    return calloc(count,size);
}

int main(void)
{
    const double A[8*4] = {
        1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1,
        0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0
    };
    const double b[8] = {1,2,3,4,0,0,0,0};
    int failure;
    for (failure = 1; failure <= 6; ++failure) {
        BSInconsistentWitness witness = {0};
        int rc;
        allocation_index = 0; fail_at = failure; failure_observed = 0;
        rc = bs_generate_inconsistent_witness(A,b,8,4,&witness);
        if (rc == 0 || !failure_observed || allocation_index < failure || witness.m != 0 ||
            witness.y != NULL || witness.pivot_row != 0) {
            fprintf(stderr,"QRCP ENOMEM failure=%d rc=%d allocations=%d m=%d y=%p pivot=%d\n",
                    failure,rc,allocation_index,witness.m,(void*)witness.y,witness.pivot_row);
            bs_inconsistent_witness_free(&witness);
            return 1;
        }
    }
    puts("reusable QRCP ENOMEM: PASS failures=6");
    return 0;
}
