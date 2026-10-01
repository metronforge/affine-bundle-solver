#include <affine_bundle/candidate_check.h>
#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <stdio.h>

static int allocation_calls;

void *abs_test_candidate_malloc(size_t size)
{
    (void)size;
    ++allocation_calls;
    return NULL;
}

int main(void)
{
    const double A[] = {1.0, 0.0, 0.0, 1.0};
    const double b[] = {1.0, 2.0};
    const double x[] = {1.0, 2.0};
    BSOperationalPolicyV1 policy;
    BSCandidateCheckResultV1 result;
    bs_default_operational_policy(&policy);
    bs_init_candidate_check_result(&result);
    assert(abs_check_candidate(A, b, x, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_ALLOCATION_FAILURE);
    assert(allocation_calls == 1);
    assert(result.verdict == BS_CANDIDATE_BOUND_UNAVAILABLE);
    assert(isinf(result.max_abs_residual_up));
    assert(isinf(result.mixed_backward_error_up));
    puts("candidate check allocation failure: PASS");
    return 0;
}
