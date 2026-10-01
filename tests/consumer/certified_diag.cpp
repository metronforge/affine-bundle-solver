#include <affine_bundle/certified_api.h>
#include <affine_bundle/candidate_check.h>
#include <affine_bundle/solve.h>
#include <cstddef>

static_assert(ABS_OUT_LEN == 11, "unexpected router meta layout");
static_assert(sizeof(BSCertifiedResult) == 112, "legacy ABI changed");
static_assert(offsetof(BSCombinedCertifiedResult, router_meta) == sizeof(BSCertifiedResult),
              "combined prefix changed");
static_assert(offsetof(BSCombinedCertifiedResult, grey_rows) == 208, "grey offset changed");
static_assert(offsetof(BSCombinedCertifiedResult, formation_guard_counters) == 488,
              "guard offset changed");
static_assert(sizeof(BSCombinedCertifiedResult) == 512, "combined ABI size changed");

int main()
{
    const double A[]={1,0,0,1}, b[]={2,3};
    BSCombinedCertifiedResult result;
    if (bsolve_certified_diag_api(A,b,nullptr,2,2,1,2,2,7,0,&result) ||
        result.router_meta[ABS_OUT_STATUS] != ABS_STATUS_UNIQUE)
        return 1;

    BSOperationalPolicyV1 policy;
    BSSolveResultV1 solved;
    BSCandidateCheckResultV1 checked;
    BSCertificateResultV1 certified;
    double x[2];
    bs_default_operational_policy(&policy);
    bs_init_solve_result(&solved);
    bs_init_candidate_check_result(&checked);
    bs_init_certificate_result(&certified);
    return bsolve(A,b,2,2,1,2,2,7,0,&policy,x,&solved) != BS_SOLVE_OK ||
           abs_check_candidate(A,b,x,2,2,&policy,&checked) != BS_CANDIDATE_CHECK_OK ||
           checked.verdict != BS_CANDIDATE_WITHIN_QUALITY_BOUND ||
           bs_certify_candidate(A,b,x,2,2,&certified) != BS_CERTIFY_OK;
}
