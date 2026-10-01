#include <affine_bundle/certified_api.h>
#include <affine_bundle/solve.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int same_bound(double a, double b)
{
    if (isinf(a) || isinf(b)) return isinf(a) && isinf(b);
    double scale = fmax(1.0, fmax(fabs(a), fabs(b)));
    return fabs(a - b) <= 64.0 * 2.2204460492503131e-16 * scale;
}

int main(void)
{
    const double A[] = {1.0, 0.0, 0.0, 1.0, 1.0, 1.0};
    const double b[] = {2.0, 3.0, 5.0};
    BSOperationalPolicyV1 policy;
    bs_default_operational_policy(&policy);
    BSSolveResultV1 solve_result;
    bs_init_solve_result(&solve_result);
    double x[2];
    assert(bsolve(A, b, 3, 2, 1, 2, 2, 17, 0, &policy, x,
                  &solve_result) == BS_SOLVE_OK);

    BSCertificateResultV1 result;
    bs_init_certificate_result(&result);
    assert(result.struct_size == sizeof(result));
    assert(result.nearby_status_mask == 0);
    assert(isinf(result.eta_unique));
    assert(isinf(result.eta_infinite));
    assert(isinf(result.eta_inconsistent));
    assert(result.exact_source_status == BS_EXACT_SOURCE_UNKNOWN);
    assert(result.exact_source_verification == BS_EXACT_VERIFY_NOT_VERIFIED);

    assert(bs_certify_candidate(A, b, x, 3, 2, &result) == BS_CERTIFY_OK);
    assert(result.nearby_status_mask != 0);
    assert(result.exact_source_status == BS_EXACT_SOURCE_UNKNOWN);
    assert(result.exact_source_verification == BS_EXACT_VERIFY_NOT_VERIFIED);

    BSCombinedSemanticResultV1 legacy;
    bs_init_combined_semantic_result(&legacy);
    assert(bsolve_certified_policy_api(A, b, NULL, 3, 2, 1, 2, 2, 17, 0,
                                       &policy, &legacy) == BS_POLICY_OK);
    assert(result.nearby_status_mask == legacy.nearby_status_mask);
    assert(same_bound(result.eta_unique, legacy.eta_unique));
    assert(same_bound(result.eta_infinite, legacy.eta_infinite));
    assert(same_bound(result.eta_inconsistent, legacy.eta_inconsistent));
    assert(result.unique_generator_code ==
           legacy.certificate_profile.unique_generator_code);
    assert(result.unique_verifier_code ==
           legacy.certificate_profile.unique_verifier_code);
    assert(result.infinite_generator_code ==
           legacy.certificate_profile.infinite_generator_code);
    assert(result.infinite_verifier_code ==
           legacy.certificate_profile.infinite_verifier_code);
    assert(result.inconsistent_generator_code ==
           legacy.certificate_profile.inconsistent_generator_code);
    assert(result.inconsistent_verifier_code ==
           legacy.certificate_profile.inconsistent_verifier_code);

    const double wrong[] = {200.0, -300.0};
    bs_init_certificate_result(&result);
    assert(bs_certify_candidate(A, b, wrong, 3, 2, &result) == BS_CERTIFY_OK);
    assert(result.exact_source_status == BS_EXACT_SOURCE_UNKNOWN);

    struct {
        BSCertificateResultV1 value;
        unsigned char tail[24];
    } future;
    memset(&future, 0x6d, sizeof(future));
    bs_init_certificate_result(&future.value);
    future.value.struct_size = sizeof(future);
    assert(bs_certify_candidate(A, b, x, 3, 2, &future.value) == BS_CERTIFY_OK);
    assert(future.value.struct_size == sizeof(future));
    for (size_t i = 0; i < sizeof(future.tail); ++i) assert(future.tail[i] == 0x6d);

    BSCertificateResultV1 undersized;
    memset(&undersized, 0xa5, sizeof(undersized));
    undersized.struct_size = sizeof(size_t);
    assert(bs_certify_candidate(A, b, x, 3, 2, &undersized) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(undersized.struct_size == sizeof(size_t));

    double nonfinite_x[] = {NAN, 0.0};
    double nonfinite_A[] = {NAN, 0.0, 0.0, 1.0, 1.0, 1.0};
    double nonfinite_b[] = {2.0, NAN, 5.0};
    bs_init_certificate_result(&result);
    assert(bs_certify_candidate(A, b, nonfinite_x, 3, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(result.nearby_status_mask == 0);
    assert(isinf(result.eta_unique));
    assert(result.exact_source_status == BS_EXACT_SOURCE_UNKNOWN);
    assert(bs_certify_candidate(NULL, b, x, 3, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(nonfinite_A, b, x, 3, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(A, nonfinite_b, x, 3, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(A, NULL, x, 3, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(A, b, NULL, 3, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(A, b, x, 0, 2, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(A, b, x, 3, 0, &result) ==
           BS_CERTIFY_INVALID_ARGUMENT);
    assert(bs_certify_candidate(A, b, x, 3, 2, NULL) ==
           BS_CERTIFY_INVALID_ARGUMENT);

    for (int i = 0; i < 20; ++i) {
        bs_init_certificate_result(&result);
        assert(bs_certify_candidate(A, b, x, 3, 2, &result) == BS_CERTIFY_OK);
        assert(result.nearby_status_mask == legacy.nearby_status_mask);
    }
    puts("candidate certification contract: PASS");
    return 0;
}
