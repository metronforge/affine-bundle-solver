/* Two public operations, exact dyadic inputs. No router instrumentation. */
#include <stdlib.h>
#include <stdio.h>
#include "affine_bundle/solve.h"
#include "affine_bundle/candidate_check.h"
#if defined(__SSE2__)
#include <xmmintrin.h>
#endif

static void require_ok(int status) {
    if (status != 0) {
        fprintf(stderr, "public API failure: %d\n", status);
        exit(EXIT_FAILURE);
    }
}

static void solve_scaled(double t) {
    const double a[] = {1, 0, 0, t}, b[] = {1, t};
    double x[2];
    BSOperationalPolicyV1 policy;
    BSSolveResultV1 result;
    BSCandidateCheckResultV1 check;
    bs_default_operational_policy(&policy);
    bs_init_solve_result(&result);
    require_ok(bsolve(a, b, 2, 2, &policy, x, &result));
    bs_init_candidate_check_result(&check);
    require_ok(abs_check_candidate(a, b, x, 2, 2, &policy, &check));
    printf("scale=%a status=%d rank=[%.0f,%.0f] fast BERR=%.17g "
           "x=(%.17g,%.17g) strict verdict=%d eta_up=%.17g\n",t,result.operational_status,
           result.router_meta[3],result.router_meta[4],result.router_meta[10],
           x[0],x[1],check.verdict,check.mixed_backward_error_up);
}

static void check_product(const char *mode) {
    const double a[] = {0x1p-530}, x[] = {0x1p-530}, b[] = {0};
    BSOperationalPolicyV1 p;
    BSCandidateCheckResultV1 ck;
    bs_default_operational_policy(&p);
    bs_init_candidate_check_result(&ck);
    require_ok(abs_check_candidate(a, b, x, 1, 1, &p, &ck));
    printf("%s verdict=%d residual_up=%a eta_up=%.17g, exact eta=1\n",
           mode,ck.verdict,ck.max_abs_residual_up,ck.mixed_backward_error_up);
}

int main(void) {
    solve_scaled(1);
    solve_scaled(0x1p-42);
    check_product("default");
#if defined(__SSE2__)
    unsigned saved = _mm_getcsr();
    _mm_setcsr(saved | 0x8040u);
    check_product("caller FTZ+DAZ");
    _mm_setcsr(saved);
#endif
}
