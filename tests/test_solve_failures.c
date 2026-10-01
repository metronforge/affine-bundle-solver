#include <affine_bundle/solve.h>
#include <assert.h>
#include <stdio.h>

static int injected_failure;
static int captured_sketch_width;
static int captured_verification_passes;
static int captured_acceptance_scale;
static unsigned long long captured_seed;
static int captured_full = -1;

int abs_test_solve_lstsq_failure(void)
{
    return injected_failure;
}

void abs_test_solve_options(int sketch_width, int verification_passes,
                            int acceptance_scale, unsigned long long seed,
                            int full)
{
    captured_sketch_width = sketch_width;
    captured_verification_passes = verification_passes;
    captured_acceptance_scale = acceptance_scale;
    captured_seed = seed;
    captured_full = full;
}

static int run(int failure, double *x, BSSolveResultV1 *result)
{
    const double A[] = {1.0, 0.0, 0.0, 1.0};
    const double b[] = {1.0, 2.0};
    BSOperationalPolicyV1 policy;
    bs_default_operational_policy(&policy);
    injected_failure = failure;
    return bsolve(A, b, 2, 2, &policy, x, result);
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

    BSSolveOptionsV1 options;
    BSOperationalPolicyV1 policy;
    bs_default_solve_options(&options);
    bs_default_operational_policy(&policy);
    options.sketch_width = 3;
    options.verification_passes = 4;
    options.acceptance_scale = 5;
    options.seed = 19ULL;
    injected_failure = 0;
    bs_init_solve_result(&result);
    assert(bsolve_ex((const double[]){1.0, 0.0, 0.0, 1.0},
                     (const double[]){1.0, 2.0}, 2, 2, &options, &policy,
                     x, &result) == BS_SOLVE_OK);
    assert(captured_sketch_width == 3);
    assert(captured_verification_passes == 4);
    assert(captured_acceptance_scale == 5);
    assert(captured_seed == 19ULL);
    assert(captured_full == 0);

    puts("standalone solve injected failures: PASS");
    return 0;
}
