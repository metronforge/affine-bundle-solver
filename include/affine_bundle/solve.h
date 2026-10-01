/* Standalone numerical solve: A,b -> x plus operational evidence. */
#ifndef AFFINE_BUNDLE_SOLVE_H
#define AFFINE_BUNDLE_SOLVE_H

#include "operational_policy.h"
#include "router.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The solve result is exactly the existing operational result: introducing a
   second layout would duplicate semantics and create an unnecessary ABI. */
typedef BSOperationalResultV1 BSSolveResultV1;

enum {
    BS_SOLVE_OK = 0,
    BS_SOLVE_INVALID_ARGUMENT = 1,
    BS_SOLVE_ALLOCATION_FAILURE = 2,
    BS_SOLVE_OPERATIONAL_FAILURE = 3,
    BS_SOLVE_NUMERICAL_FAILURE = 4
};

void bs_init_solve_result(BSSolveResultV1 *out);

/* A and b are finite row-major inputs.  x has n caller-owned doubles.  The
   operation computes a numerical least-squares/minimum-norm candidate and
   reports the router's operational classification; it performs no nearby
   certification and establishes no exact-source status. */
int bsolve(const double *A, const double *b, int m, int n,
           int sp, int qv, int alpha, unsigned long long seed, int full,
           const BSOperationalPolicyV1 *policy,
           double *x, BSSolveResultV1 *out);

#ifdef __cplusplus
}
#endif
#endif
