#include <affine_bundle/certified_api.h>
#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

static int allocation_index, fail_at, failure_observed;
static int saw_qrcp_reject, saw_dgesdd_attempt, saw_dgesdd_verify;

static int fail_now(void)
{
    ++allocation_index;
    if (fail_at && allocation_index == fail_at) {
        failure_observed = 1;
        return 1;
    }
    return 0;
}

void *abs_test_certificate_malloc(size_t size)
{
    return fail_now() ? NULL : malloc(size);
}

void *abs_test_certificate_calloc(size_t count, size_t size)
{
    return fail_now() ? NULL : calloc(count, size);
}

void abs_test_infinite_fastpath_hook(int phase)
{
    if (phase == 2) saw_qrcp_reject = 1;
    if (phase == 3) saw_dgesdd_attempt = 1;
    if (phase == 4) saw_dgesdd_verify = 1;
}

int abs_test_infinite_force_qrcp_reject(void) { return 1; }

static int run(BSCertificateResultV1 *result)
{
    const double A[] = {1.0, 0.0};
    const double b[] = {1.0};
    const double x[] = {1.0, 0.0};
    bs_init_certificate_result(result);
    return bs_certify_candidate(A, b, x, 1, 2, result);
}

int main(void)
{
    BSCertificateResultV1 result;
    allocation_index = 0; fail_at = 0;
    assert(run(&result) == BS_CERTIFY_OK);
    assert(saw_qrcp_reject && saw_dgesdd_attempt && saw_dgesdd_verify);
    int total_allocations = allocation_index;
    assert(total_allocations > 6);

    for (int failure = 1; failure <= total_allocations; ++failure) {
        allocation_index = 0;
        fail_at = failure;
        failure_observed = 0;
        assert(run(&result) == BS_CERTIFY_ALLOCATION_FAILURE);
        assert(failure_observed);
        assert(result.nearby_status_mask == 0);
        assert(isinf(result.eta_unique));
        assert(isinf(result.eta_infinite));
        assert(isinf(result.eta_inconsistent));
        assert(result.exact_source_status == BS_EXACT_SOURCE_UNKNOWN);
        assert(result.exact_source_verification == BS_EXACT_VERIFY_NOT_VERIFIED);
    }
    printf("candidate certification allocation sweep: PASS allocations=%d\n",
           total_allocations);
    return 0;
}
