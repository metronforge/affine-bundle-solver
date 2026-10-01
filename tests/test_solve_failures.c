#include <affine_bundle/solve.h>
#include <assert.h>
#include <stdio.h>

static int injected_failure;

int abs_test_solve_lstsq_failure(void)
{
    return injected_failure;
}

static int run(int failure, double *x, BSSolveResultV1 *result)
{
    const double A[] = {1.0, 0.0, 0.0, 1.0};
    const double b[] = {1.0, 2.0};
    BSOperationalPolicyV1 policy;
    bs_default_operational_policy(&policy);
    injected_failure = failure;
    return bsolve(A, b, 2, 2, 1, 2, 2, 17, 0, &policy, x, result);
}

int main(void)
{
    double x[2] = {7.0, 8.0};
    BSSolveResultV1 result;
    bs_init_solve_result(&result);
    assert(run(2, x, &result) == BS_SOLVE_ALLOCATION_FAILURE);
    assert(x[0] == 0.0 && x[1] == 0.0);
    assert(result.operational_status == ABS_STATUS_UNIQUE);

    x[0] = 7.0; x[1] = 8.0;
    bs_init_solve_result(&result);
    assert(run(3, x, &result) == BS_SOLVE_NUMERICAL_FAILURE);
    assert(x[0] == 0.0 && x[1] == 0.0);
    assert(result.operational_status == ABS_STATUS_UNIQUE);

    puts("standalone solve injected failures: PASS");
    return 0;
}
