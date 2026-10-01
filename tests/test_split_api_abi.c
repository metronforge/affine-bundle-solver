#include <affine_bundle/candidate_check.h>
#include <affine_bundle/certified_api.h>
#include <affine_bundle/operational_policy.h>
#include <affine_bundle/router.h>
#include <affine_bundle/solve.h>
#include <assert.h>
#include <stddef.h>
#include <stdio.h>

_Static_assert(sizeof(BSSolveResultV1) == sizeof(BSOperationalResultV1),
               "solve result must remain the operational-result ABI");
_Static_assert(offsetof(BSCandidateCheckResultV1, struct_size) == 0,
               "candidate result version field must be first");
_Static_assert(offsetof(BSCertificateResultV1, struct_size) == 0,
               "certificate result version field must be first");

int main(void)
{
    BSOperationalPolicyV1 policy;
    BSOperationalResultV1 operational;
    BSSolveResultV1 solve;
    BSCandidateCheckResultV1 candidate;
    BSCertificateResultV1 certificate;
    BSCombinedSemanticResultV1 combined;

    bs_default_operational_policy(&policy);
    assert(policy.struct_size == sizeof(policy));
    assert(policy.dependence_threshold == 1e-13);
    assert(policy.growth_threshold == 1e-9);
    assert(policy.compatibility_tolerance == 2e-10);
    assert(policy.quality_threshold == 1e-14);

    bs_init_operational_result(&operational);
    bs_init_solve_result(&solve);
    bs_init_candidate_check_result(&candidate);
    bs_init_certificate_result(&certificate);
    bs_init_combined_semantic_result(&combined);
    assert(operational.struct_size == sizeof(operational));
    assert(solve.struct_size == sizeof(solve));
    assert(candidate.struct_size == sizeof(candidate));
    assert(certificate.struct_size == sizeof(certificate));
    assert(combined.struct_size == sizeof(combined));

    /* Taking each address makes link-time symbol preservation/new-symbol
       availability part of this installed-header consumer test. */
    assert(&bs_default_operational_policy != NULL);
    assert(&bsolve_router_policy_api != NULL);
    assert(&bsolve_certified_policy_api != NULL);
    assert(&bsolve != NULL);
    assert(&abs_check_candidate != NULL);
    assert(&bs_certify_candidate != NULL);
    puts("split API ABI and symbols: PASS");
    return 0;
}
