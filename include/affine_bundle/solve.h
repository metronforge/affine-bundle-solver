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

/* Controls how one numerical solve is routed.  Size is the accessible caller
   allocation, at least sizeof(V1); future trailing bytes are ignored. */
typedef struct {
    size_t struct_size;
    int sketch_width;
    int verification_passes;
    int acceptance_scale;
    unsigned long long seed;
} BSSolveOptionsV1;

enum {
    BS_SOLVE_OK = 0,
    BS_SOLVE_INVALID_ARGUMENT = 1,
    BS_SOLVE_ALLOCATION_FAILURE = 2,
    BS_SOLVE_OPERATIONAL_FAILURE = 3,
    BS_SOLVE_NUMERICAL_FAILURE = 4
};

void bs_init_solve_result(BSSolveResultV1 *out);
void bs_default_solve_options(BSSolveOptionsV1 *out);

/* A and b are finite row-major inputs.  x has n caller-owned doubles.  The
   operation computes a numerical least-squares/minimum-norm candidate and
   reports the router's operational classification; it performs no nearby
   certification and establishes no exact-source status. */
int bsolve(const double *A, const double *b, int m, int n,
           const BSOperationalPolicyV1 *policy,
           double *x, BSSolveResultV1 *out);

/* Advanced solve configuration.  options must be non-NULL, have a supported
   V1 prefix, and contain positive control values.  The historical router's
   `full` parameter is intentionally absent: it is ignored by normal routing
   and is retained only by the legacy router ABI.  Non-default operational
   policies select the existing deterministic source-QRCP policy route, where
   these randomized-router controls are validated but do not affect routing. */
int bsolve_ex(const double *A, const double *b, int m, int n,
              const BSSolveOptionsV1 *options,
              const BSOperationalPolicyV1 *policy,
              double *x, BSSolveResultV1 *out);

#ifdef __cplusplus
}
#endif
#endif
