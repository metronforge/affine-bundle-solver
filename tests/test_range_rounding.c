/* Pin actual stored binary64 inputs, not a real-number rescaling fantasy.
 * Removing verifier range normalization or rounding restoration must fail.
 * No floating diagnostic is used as a cross-platform equality key. */
#include <affine_bundle/status_certificate.h>
#include <affine_bundle/operational_policy.h>
#include <affine_bundle/router.h>
#include <affine_bundle/stream.h>
#include <fenv.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static int failures, checks;
#define CHECK(c) do { ++checks; if (!(c)) { \
    fprintf(stderr, "line %d: %s (round=%d)\n", __LINE__, #c, fegetround()); \
    ++failures; } } while (0)

static void verify_rejection(double s, int mode) {
    /* Nonzero products cancel: unlike all-zero input, this reaches the
       rejection AFTER the verifier has changed rounding for dot intervals. */
    double A[] = {0, 0}, b[] = {s, -s}, y[] = {1, 1}, lo, hi, eta;
    BSInconsistentWitness w = {2, y, 0};
    CHECK(bs_verify_inconsistent(A, b, 2, 1, &w, &lo, &hi, &eta) == 4);
    CHECK(lo == 0 && hi == 0);
    CHECK(fegetround() == mode);
}

static void verify_scale(double s, int mode) {
    double A[] = {s, 0, 0, 0}, b[] = {s, 0};
    double x[] = {1, 0}, z[] = {0, 1}, eta = -1;
    BSInfiniteWitness w = {2, x, z};
    CHECK(bs_verify_infinite(A, b, 2, 2, &w, &eta) == 0);
    CHECK(fegetround() == mode);
    CHECK(isfinite(eta) && eta == 0);
    /* Exact zero-row contradiction and early rejected zero RHS. */
    double zero[] = {0}, rhs[] = {s}, y[] = {1}, lo, hi;
    BSInconsistentWitness iw = {1, y, 0};
    CHECK(bs_verify_inconsistent(zero, rhs, 1, 1, &iw, &lo, &hi, &eta) == 0);
    CHECK(fegetround() == mode);
    CHECK((s > 0 && lo > 0) || (s < 0 && hi < 0));
    rhs[0] = 0;
    CHECK(bs_verify_inconsistent(zero, rhs, 1, 1, &iw, &lo, &hi, &eta) != 0);
    CHECK(fegetround() == mode);
    z[1] = 0;
    CHECK(bs_verify_infinite(A, b, 2, 2, &w, &eta) != 0);
    CHECK(fegetround() == mode);
    verify_rejection(s, mode);
}

static void threshold_neighborhoods(void) {
    BSOperationalPolicyV1 p;
    bs_default_operational_policy(&p);
    /* A zero row's compatibility predicate compares |b| directly to tc.
       nextafter inputs are built in nearest mode and survive storage exactly. */
    double rhs[] = {nextafter(p.compatibility_tolerance, 0),
                    p.compatibility_tolerance,
                    nextafter(p.compatibility_tolerance, INFINITY)};
    for (int sign = -1; sign <= 1; sign += 2) {
        for (int k = 0; k < 3; ++k) {
            ABSStream *st = abs_stream_create(2);
            double zero[] = {0, 0};
            CHECK(st != NULL);
            if (!st) continue;
            CHECK(abs_stream_insert(st, zero, sign * rhs[k]) == (k == 2 ? -1 : 0));
            abs_stream_destroy(st);
        }
    }
    /* Exact dyadic distances straddle each default rank threshold; no random
       QR basis construction or per-provider tolerance is involved. */
    const int exponents[] = {-44, -42, -31, -29};
    const int expected[] = {0, 2, 2, 1};
    for (int k = 0; k < 4; ++k) {
        ABSStream *st = abs_stream_create(2);
        double base[] = {1, 0}, row[] = {1, scalbn(1., exponents[k])};
        CHECK(st != NULL);
        if (!st) continue;
        CHECK(abs_stream_insert(st, base, 1) == 1);
        CHECK(abs_stream_insert(st, row, 1) == expected[k]);
        abs_stream_destroy(st);
    }
    /* Two repeated scalar equations. The router's source-row witness is x=1:
       its worst rowwise backward error is delta/(2+delta), which straddles
       the default 1e-14 quality gate between exponents -46 and -45.
       This is not the (different) optimal least-squares witness. */
    for (int e = -47; e <= -43; ++e) {
        double A[] = {1, 1}, b[] = {1, 1 + scalbn(1., e)};
        BSOperationalResultV1 r;
        bs_init_operational_result(&r);
        CHECK(!bsolve_router_policy_api(A, b, NULL, 2, 1, 1, 2, 2, 777, 0, &p, &r));
        printf("quality neighborhood exponent=%d status=%d backward_error=%a\n",
               e, r.operational_status, r.router_meta[10]);
        CHECK(r.operational_status == (e <= -46 ? ABS_STATUS_UNIQUE : ABS_STATUS_UNDECIDABLE));
        CHECK(fegetround() == FE_TONEAREST);
    }
}

int main(void) {
    int original = fegetround();
    CHECK(!fesetround(FE_TONEAREST));
#ifdef ABS_FENV_NEGATIVE_CONTROL
    verify_rejection(1, FE_TONEAREST);
    CHECK(!fesetround(original));
    return failures ? 1 : 0;
#endif
    /* Neighbors built before changing rounding mode, including true min,
       largest subnormal, smallest normal and largest finite numbers. */
    const double values[] = {0x1p-1074, 0x1p-1073, 0x1.8p-1073,
        nextafter(DBL_MIN, 0), DBL_MIN, nextafter(DBL_MIN, INFINITY),
        nextafter(DBL_MAX, 0), DBL_MAX};
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    for (int k = 0; k < 4; ++k) {
        CHECK(!fesetround(modes[k]));
        for (unsigned j = 0; j < sizeof values / sizeof values[0]; ++j)
            for (int sign = -1; sign <= 1; sign += 2) verify_scale(sign * values[j], modes[k]);
        for (int e = -1074; e <= 1023; ++e)
            for (int sign = -1; sign <= 1; sign += 2) verify_scale(sign * scalbn(1., e), modes[k]);
    }
    CHECK(!fesetround(FE_TONEAREST));
    threshold_neighborhoods();
    CHECK(!fesetround(original));
    printf("range/rounding: %d checks, %d failures; diagnostics are not equality keys\n", checks, failures);
    return failures ? 1 : 0;
}
