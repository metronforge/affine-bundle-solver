#include <affine_bundle/solve.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static const double A[] = {1.0, 0.0, 0.0, 1.0};
static const double b[] = {1.0, 2.0};

static int solve(const double *matrix, const double *rhs, int m, int n,
                 const BSOperationalPolicyV1 *policy, double *x,
                 BSSolveResultV1 *result)
{
    return bsolve(matrix, rhs, m, n, 1, 2, 2, 17, 0, policy, x, result);
}

int main(void)
{
    BSOperationalPolicyV1 policy;
    bs_default_operational_policy(&policy);
    BSSolveResultV1 result;
    bs_init_solve_result(&result);
    assert(result.struct_size == sizeof(result));
    assert(result.operational_status == ABS_STATUS_FAIL);
    assert(result.exact_source_status == BS_EXACT_SOURCE_UNKNOWN);
    assert(result.exact_source_verification == BS_EXACT_VERIFY_NOT_VERIFIED);

    double x[2] = {NAN, NAN};
    assert(solve(A, b, 2, 2, &policy, x, &result) == BS_SOLVE_OK);
    assert(result.operational_status == ABS_STATUS_UNIQUE);
    assert(result.operational_certainty == ABS_CERTAINTY_DETERMINISTIC);
    assert(fabs(x[0] - 1.0) <= 1e-14);
    assert(fabs(x[1] - 2.0) <= 1e-14);

    /* Preserve the aliasing contract of bsolve_router_policy_api. */
    bs_init_solve_result(&result);
    result.policy_used = policy;
    assert(solve(A, b, 2, 2, &result.policy_used, x, &result) == BS_SOLVE_OK);
    assert(result.policy_used.quality_threshold == policy.quality_threshold);

    BSOperationalResultV1 legacy;
    bs_init_operational_result(&legacy);
    assert(bsolve_router_policy_api(A, b, NULL, 2, 2, 1, 2, 2, 17, 0,
                                    &policy, &legacy) == BS_POLICY_OK);
    assert(result.operational_status == legacy.operational_status);
    assert(result.operational_certainty == legacy.operational_certainty);
    for (int i = 0; i < ABS_OUT_LEN; ++i) {
        if (i == ABS_OUT_SECONDS) continue;
        assert(result.router_meta[i] == legacy.router_meta[i] ||
               (isnan(result.router_meta[i]) && isnan(legacy.router_meta[i])));
    }

    const double rank_deficient[] = {1.0, 0.0, 2.0, 0.0};
    const double rank_deficient_b[] = {3.0, 6.0};
    x[0] = x[1] = NAN;
    bs_init_solve_result(&result);
    assert(solve(rank_deficient, rank_deficient_b, 2, 2, &policy, x, &result) ==
           BS_SOLVE_OK);
    assert(result.operational_status == ABS_STATUS_INFINITE);
    assert(fabs(x[0] - 3.0) <= 1e-12);
    assert(fabs(x[1]) <= 1e-12);

    struct {
        BSSolveResultV1 value;
        unsigned char tail[24];
    } future;
    memset(&future, 0x3c, sizeof(future));
    bs_init_solve_result(&future.value);
    future.value.struct_size = sizeof(future);
    assert(solve(A, b, 2, 2, &policy, x, &future.value) == BS_SOLVE_OK);
    assert(future.value.struct_size == sizeof(future));
    for (size_t i = 0; i < sizeof(future.tail); ++i) assert(future.tail[i] == 0x3c);

    BSSolveResultV1 undersized;
    memset(&undersized, 0xa5, sizeof(undersized));
    undersized.struct_size = sizeof(size_t);
    assert(solve(A, b, 2, 2, &policy, x, &undersized) ==
           BS_SOLVE_INVALID_ARGUMENT);
    assert(undersized.struct_size == sizeof(size_t));
    const unsigned char *bytes = (const unsigned char *)&undersized;
    for (size_t i = sizeof(size_t); i < sizeof(undersized); ++i)
        assert(bytes[i] == 0xa5);

    bs_init_solve_result(&result);
    assert(solve(NULL, b, 2, 2, &policy, x, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(result.operational_status == ABS_STATUS_FAIL);
    assert(solve(A, NULL, 2, 2, &policy, x, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(solve(A, b, 2, 2, &policy, NULL, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(solve(A, b, 0, 2, &policy, x, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(solve(A, b, 2, 0, &policy, x, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(solve(A, b, 2, 2, NULL, x, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(solve(A, b, 2, 2, &policy, x, NULL) == BS_SOLVE_INVALID_ARGUMENT);

    double nonfinite_A[] = {NAN, 0.0, 0.0, 1.0};
    assert(solve(nonfinite_A, b, 2, 2, &policy, x, &result) ==
           BS_SOLVE_INVALID_ARGUMENT);
    assert(result.operational_status == ABS_STATUS_FAIL);

    bs_default_operational_policy(&policy);
    policy.dependence_threshold = policy.growth_threshold;
    assert(solve(A, b, 2, 2, &policy, x, &result) == BS_SOLVE_INVALID_ARGUMENT);
    assert(result.operational_status == ABS_STATUS_FAIL);

    puts("standalone solve contract: PASS");
    return 0;
}
