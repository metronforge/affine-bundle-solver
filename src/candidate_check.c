#pragma STDC FENV_ACCESS ON
#include "affine_bundle/candidate_check.h"

#include <fenv.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef ABS_TEST_CANDIDATE_ALLOC
extern void *abs_test_candidate_malloc(size_t);
#define candidate_malloc abs_test_candidate_malloc
#else
#define candidate_malloc malloc
#endif

static int finite_vector(const double *values, size_t count)
{
    if (!values) return 0;
    for (size_t i = 0; i < count; ++i)
        if (!isfinite(values[i])) return 0;
    return 1;
}

static int maximum_exponent(const double *values, int count)
{
    int largest = FP_ILOGB0;
    for (int i = 0; i < count; ++i) {
        double value = fabs(values[i]);
        if (value > 0.0) {
            int exponent = ilogb(value);
            if (largest == FP_ILOGB0 || exponent > largest) largest = exponent;
        }
    }
    return largest;
}

static double norm_directed(const double *values, int count, int mode)
{
    int exponent = maximum_exponent(values, count);
    if (exponent == FP_ILOGB0) return 0.0;
    volatile double sum = 0.0, scaled, product, root, result;
    fesetround(mode);
    for (int i = 0; i < count; ++i) {
        scaled = scalbn(values[i], -exponent);
        product = scaled * scaled;
        sum = sum + product;
    }
    root = sqrt(sum);
    result = scalbn(root, exponent);
    return result;
}

static double residual_abs_upper(const double *row, double rhs,
                                 const double *x, int n)
{
    volatile double sum = 0.0, product, low, high;
    fesetround(FE_DOWNWARD);
    for (int j = 0; j < n; ++j) {
        product = row[j] * x[j];
        sum = sum + product;
    }
    low = sum - rhs;
    fesetround(FE_UPWARD);
    sum = 0.0;
    for (int j = 0; j < n; ++j) {
        product = row[j] * x[j];
        sum = sum + product;
    }
    high = sum - rhs;
    return fmax(fabs((double)low), fabs((double)high));
}

void bs_init_candidate_check_result(BSCandidateCheckResultV1 *out)
{
    if (!out) return;
    memset(out, 0, sizeof(*out));
    out->struct_size = sizeof(*out);
    out->verdict = BS_CANDIDATE_BOUND_UNAVAILABLE;
    out->max_abs_residual_up = INFINITY;
    out->mixed_backward_error_up = INFINITY;
}

int abs_check_candidate(const double *A, const double *b, const double *x,
                        int m, int n,
                        const BSOperationalPolicyV1 *policy,
                        BSCandidateCheckResultV1 *out)
{
    if (!out || out->struct_size < sizeof(*out))
        return BS_CANDIDATE_CHECK_INVALID_ARGUMENT;

    size_t caller_size = out->struct_size;
    BSOperationalPolicyV1 policy_copy;
    int policy_status = bs_validate_operational_policy(policy);
    if (!policy_status) {
        policy_copy = *policy;
        policy_copy.struct_size = sizeof(policy_copy);
    }
    bs_init_candidate_check_result(out);
    out->struct_size = caller_size;
    if (policy_status) return BS_CANDIDATE_CHECK_INVALID_ARGUMENT;
    out->policy_used = policy_copy;

    if (!A || !b || !x || m <= 0 || n <= 0 ||
        (size_t)m > SIZE_MAX / (size_t)n ||
        (size_t)m * (size_t)n > SIZE_MAX / sizeof(double) ||
        !finite_vector(A, (size_t)m * (size_t)n) ||
        !finite_vector(b, (size_t)m) ||
        !finite_vector(x, (size_t)n))
        return BS_CANDIDATE_CHECK_INVALID_ARGUMENT;

    double *row_backward = candidate_malloc((size_t)m * sizeof(*row_backward));
    if (!row_backward) return BS_CANDIDATE_CHECK_ALLOCATION_FAILURE;

    fenv_t caller_environment;
    if (fegetenv(&caller_environment)) {
        free(row_backward);
        return BS_CANDIDATE_CHECK_NUMERICAL_FAILURE;
    }

    double x_norm_lower = norm_directed(x, n, FE_DOWNWARD);
    double maximum_residual = 0.0;
    int available = isfinite(x_norm_lower);
    for (int i = 0; i < m; ++i) {
        const double *row = A + (size_t)i * n;
        double residual = residual_abs_upper(row, b[i], x, n);
        double row_norm_lower = norm_directed(row, n, FE_DOWNWARD);
        volatile double product, denominator, quotient;
        fesetround(FE_DOWNWARD);
        product = row_norm_lower * x_norm_lower;
        denominator = fabs(b[i]) + product;
        if (!isfinite(residual) || !isfinite(row_norm_lower) ||
            !isfinite((double)denominator)) {
            available = 0;
            row_backward[i] = INFINITY;
        } else if (denominator == 0.0) {
            row_backward[i] = residual == 0.0 ? 0.0 : INFINITY;
            if (residual != 0.0) available = 0;
        } else {
            fesetround(FE_UPWARD);
            quotient = residual / denominator;
            row_backward[i] = quotient;
            if (!isfinite(row_backward[i])) available = 0;
        }
        if (residual > maximum_residual) maximum_residual = residual;
    }

    double maximum_backward = 0.0;
    for (int i = 0; i < m; ++i)
        if (row_backward[i] > maximum_backward) maximum_backward = row_backward[i];
    free(row_backward);
    if (fesetenv(&caller_environment))
        return BS_CANDIDATE_CHECK_NUMERICAL_FAILURE;

    if (isfinite(maximum_residual)) out->max_abs_residual_up = maximum_residual;
    if (isfinite(maximum_backward)) out->mixed_backward_error_up = maximum_backward;
    if (!available || !isfinite(maximum_residual) || !isfinite(maximum_backward))
        return BS_CANDIDATE_CHECK_OK;

    out->verdict = maximum_backward <= policy_copy.quality_threshold
        ? BS_CANDIDATE_WITHIN_QUALITY_BOUND
        : BS_CANDIDATE_NOT_ESTABLISHED;
    return BS_CANDIDATE_CHECK_OK;
}
