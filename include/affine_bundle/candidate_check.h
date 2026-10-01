/* Candidate-quality evaluation for an arbitrary caller-supplied x. */
#ifndef AFFINE_BUNDLE_CANDIDATE_CHECK_H
#define AFFINE_BUNDLE_CANDIDATE_CHECK_H

#include <stddef.h>
#include "operational_policy.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BS_CANDIDATE_BOUND_UNAVAILABLE = 0,
    BS_CANDIDATE_WITHIN_QUALITY_BOUND = 1,
    BS_CANDIDATE_NOT_ESTABLISHED = 2
} BSCandidateVerdict;

enum {
    BS_CANDIDATE_CHECK_OK = 0,
    BS_CANDIDATE_CHECK_INVALID_ARGUMENT = 1,
    BS_CANDIDATE_CHECK_ALLOCATION_FAILURE = 2,
    BS_CANDIDATE_CHECK_NUMERICAL_FAILURE = 3
};

/* Versioned result.  The verdict describes evidence about this x; the return
   value from abs_check_candidate describes whether the operation executed.
   A valid-sized result is initialized to BOUND_UNAVAILABLE before any other
   validation.  Future trailing bytes are neither read nor written. */
typedef struct {
    size_t struct_size;
    BSOperationalPolicyV1 policy_used;
    BSCandidateVerdict verdict;
    double max_abs_residual_up;
    double mixed_backward_error_up;
} BSCandidateCheckResultV1;

void bs_init_candidate_check_result(BSCandidateCheckResultV1 *out);

/* Evaluate caller-owned finite x for finite row-major A and b.  This function
   is stateless, never invokes a solver/router, and makes no claim about the
   exact mathematical status of A,b.  Bounds are computed with directed
   rounding.  NOT_ESTABLISHED is not a rejection of x. */
int abs_check_candidate(const double *A, const double *b, const double *x,
                        int m, int n,
                        const BSOperationalPolicyV1 *policy,
                        BSCandidateCheckResultV1 *out);

#ifdef __cplusplus
}
#endif
#endif
