#include <affine_bundle/candidate_check.h>
#include <assert.h>
#include <fenv.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static const double identity[] = {1.0, 0.0, 0.0, 1.0};
static const double rhs[] = {1.0, 2.0};

static int check(const double *A, const double *b, const double *x, int m, int n,
                 const BSOperationalPolicyV1 *policy,
                 BSCandidateCheckResultV1 *result)
{
    return abs_check_candidate(A, b, x, m, n, policy, result);
}

int main(void)
{
    BSOperationalPolicyV1 policy;
    bs_default_operational_policy(&policy);

    BSCandidateCheckResultV1 result;
    bs_init_candidate_check_result(&result);
    assert(result.struct_size == sizeof(result));
    assert(result.verdict == BS_CANDIDATE_BOUND_UNAVAILABLE);
    assert(isinf(result.max_abs_residual_up));
    assert(isinf(result.mixed_backward_error_up));

    const double exact[] = {1.0, 2.0};
    assert(fesetround(FE_DOWNWARD) == 0);
    assert(check(identity, rhs, exact, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_OK);
    assert(fegetround() == FE_DOWNWARD);
    assert(fesetround(FE_TONEAREST) == 0);
    assert(result.verdict == BS_CANDIDATE_WITHIN_QUALITY_BOUND);
    assert(result.max_abs_residual_up >= 0.0);
    assert(result.max_abs_residual_up <= 8.0e-15);
    assert(result.mixed_backward_error_up >= 0.0);
    assert(result.mixed_backward_error_up <= policy.quality_threshold);
    assert(result.policy_used.quality_threshold == policy.quality_threshold);

    const double perturbed[] = {1.0, 2.001};
    assert(check(identity, rhs, perturbed, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_OK);
    assert(result.verdict == BS_CANDIDATE_NOT_ESTABLISHED);
    assert(result.max_abs_residual_up >= 0.000999999999);
    assert(result.mixed_backward_error_up > policy.quality_threshold);

    const double zero[] = {0.0, 0.0};
    assert(check(identity, rhs, zero, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_OK);
    assert(result.verdict == BS_CANDIDATE_NOT_ESTABLISHED);
    assert(result.max_abs_residual_up >= 2.0);

    const double exact_rect[] = {3.0, -1.0};
    const double rectangular[] = {1.0, 0.0, 0.0, 1.0, 1.0, 1.0};
    const double rectangular_rhs[] = {3.0, -1.0, 2.0};
    assert(check(rectangular, rectangular_rhs, exact_rect, 3, 2,
                 &policy, &result) == BS_CANDIDATE_CHECK_OK);
    assert(result.verdict == BS_CANDIDATE_WITHIN_QUALITY_BOUND);

    struct {
        BSCandidateCheckResultV1 value;
        unsigned char tail[24];
    } future;
    memset(&future, 0x5a, sizeof(future));
    bs_init_candidate_check_result(&future.value);
    future.value.struct_size = sizeof(future);
    assert(check(identity, rhs, exact, 2, 2, &policy, &future.value) ==
           BS_CANDIDATE_CHECK_OK);
    assert(future.value.struct_size == sizeof(future));
    for (size_t i = 0; i < sizeof(future.tail); ++i) assert(future.tail[i] == 0x5a);

    BSCandidateCheckResultV1 undersized;
    memset(&undersized, 0xa5, sizeof(undersized));
    undersized.struct_size = sizeof(size_t);
    assert(check(identity, rhs, exact, 2, 2, &policy, &undersized) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(undersized.struct_size == sizeof(size_t));
    const unsigned char *undersized_bytes = (const unsigned char *)&undersized;
    for (size_t i = sizeof(size_t); i < sizeof(undersized); ++i)
        assert(undersized_bytes[i] == 0xa5);

    double nonfinite[] = {NAN, 2.0};
    double nonfinite_A[] = {NAN, 0.0, 0.0, 1.0};
    double nonfinite_b[] = {1.0, INFINITY};
    bs_init_candidate_check_result(&result);
    assert(check(identity, rhs, nonfinite, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(result.verdict == BS_CANDIDATE_BOUND_UNAVAILABLE);
    assert(isinf(result.max_abs_residual_up));
    assert(isinf(result.mixed_backward_error_up));

    assert(check(NULL, rhs, exact, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(nonfinite_A, rhs, exact, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, nonfinite_b, exact, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, NULL, exact, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, rhs, NULL, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, rhs, exact, 0, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, rhs, exact, 2, 0, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, rhs, exact, 2, 2, NULL, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(check(identity, rhs, exact, 2, 2, &policy, NULL) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);

    bs_default_operational_policy(&policy);
    policy.quality_threshold = 0.0;
    assert(check(identity, rhs, exact, 2, 2, &policy, &result) ==
           BS_CANDIDATE_CHECK_INVALID_ARGUMENT);
    assert(result.verdict == BS_CANDIDATE_BOUND_UNAVAILABLE);

    bs_default_operational_policy(&policy);
    for (int i = 0; i < 100; ++i) {
        bs_init_candidate_check_result(&result);
        assert(check(identity, rhs, exact, 2, 2, &policy, &result) ==
               BS_CANDIDATE_CHECK_OK);
        assert(result.verdict == BS_CANDIDATE_WITHIN_QUALITY_BOUND);
    }

    puts("candidate check contract: PASS");
    return 0;
}
