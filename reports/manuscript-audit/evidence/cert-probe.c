/* Public verifier diagnostics for the source revision named in certificates.md. */
#include "affine_bundle/certified_api.h"
#include <float.h>
#include <math.h>
#include <stdio.h>
#if defined(__SSE2__)
#include <xmmintrin.h>
#endif

static void infinite(const char *label, double *A, double *b, int m, int n,
                     double *x, double *z) {
    BSInfiniteWitness witness = {n, x, z};
    double eta;
    int rc = bs_verify_infinite(A, b, m, n, &witness, &eta);
    printf("%s rc=%d eta=%a\n", label, rc, eta);
}

static void inconsistent(const char *label, double *A, double *b, int m, int n,
                         double *y, int k) {
    BSInconsistentWitness witness = {m, y, k};
    double lo = NAN, hi = NAN, eta;
    int rc = bs_verify_inconsistent(A, b, m, n, &witness, &lo, &hi, &eta);
    printf("%s rc=%d eta=%a interval=[%a,%a]\n", label, rc, eta, lo, hi);
}

int main(void) {
    double two[] = {2}, one[] = {1}, zero[] = {0}, max[] = {DBL_MAX};
    infinite("scalar-large-z", two, zero, 1, 1, zero, max);
    infinite("scalar-unit-z", two, zero, 1, 1, zero, one);
    infinite("scalar-zero-z", two, zero, 1, 1, zero, zero);
    infinite("nonfinite-input", (double[]){NAN}, zero, 1, 1, zero, one);

    double A[] = {1, 0, 1, 0}, b[] = {0, 1}, x[] = {DBL_MAX, DBL_MAX};
    infinite("incompatible-two-rows", A, b, 2, 2, x, (double[]){0, 1});
    BSCertificateResultV1 result;
    bs_init_certificate_result(&result);
    int rc = bs_certify_candidate(A, b, x, 2, 2, &result);
    printf("candidate rc=%d mask=%d infinite_gen=%d infinite_ver=%d eta_inf=%a\n",
           rc, result.nearby_status_mask, result.infinite_generator_code,
           result.infinite_verifier_code, result.eta_infinite);

    /* The combined API reconstructs its own least-squares candidate. */
    double t = 0x1p-1022, source[] = {t, 0, 0, 0, t, 0, t, 0, 0};
    double rhs[] = {3.25, 3.25, 3.0}, reference[] = {0, 0, 0};
    BSCertifiedResult combined;
    rc = bsolve_certified_api(source, rhs, reference, 3, 3, 1, 2, 2,
                              12345, 0, &combined);
    printf("combined rc=%d mask=%d infinite_gen=%d infinite_ver=%d eta_inf=%a\n",
           rc, combined.accepted_status_mask, combined.infinite_generator_code,
           combined.infinite_verifier_code, combined.eta_infinite);

    int index[] = {0};
    BSUniqueWitness unique = {1, 1, index, one, index, one, zero};
    double eta;
    rc = bs_verify_unique(zero, zero, 1, 1, &unique, &eta);
    printf("unique-changes-zero-row rc=%d eta=%a\n", rc, eta);
    inconsistent("zero-pivot-needs-change", (double[]){0, 1}, (double[]){0, 1},
                 2, 1, (double[]){1, 1}, 0);
    inconsistent("zero-pivot-no-change", (double[]){0, 0}, (double[]){0, 1},
                 2, 1, (double[]){1, 1}, 0);
    inconsistent("exact-zero-contradiction", (double[]){1, 1}, (double[]){1, 1},
                 2, 1, (double[]){1, -1}, 1);
    inconsistent("signed-frame", (double[]){0x1p900, -0x1p-900},
                 (double[]){0, 0x1p-900}, 2, 1,
                 (double[]){0x1p-900, 0x1p900}, 1);

#if defined(__SSE2__)
    /* A separate calling environment, after the library-load probe. */
    unsigned previous = _mm_getcsr();
    unique.m = 2;
    for (int flush = 0; flush <= 1; ++flush) {
        _mm_setcsr(flush ? previous | 0x8040u : previous & ~0x8040u);
        rc = bs_verify_unique((double[]){1, 1}, (double[]){0, DBL_TRUE_MIN},
                              2, 1, &unique, &eta);
        printf("unique-ftz-daz-%d rc=%d eta=%a\n", flush, rc, eta);
        inconsistent(flush ? "inconsistent-ftz-daz-1" : "inconsistent-ftz-daz-0",
                     (double[]){DBL_TRUE_MIN}, one, 1, 1, one, 0);
    }
    _mm_setcsr(previous);
#endif
    return 0;
}
