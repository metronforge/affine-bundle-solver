#include "affine_bundle/status_certificate.h"

#include <fenv.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static int allocation_call;
static int fail_at;
static int outstanding;

void *review_malloc(size_t size)
{
    ++allocation_call;
    if (allocation_call == fail_at) return NULL;
    void *pointer = malloc(size);
    if (pointer) ++outstanding;
    return pointer;
}

void *review_calloc(size_t count, size_t size)
{
    ++allocation_call;
    if (allocation_call == fail_at) return NULL;
    void *pointer = calloc(count, size);
    if (pointer) ++outstanding;
    return pointer;
}

void review_free(void *pointer)
{
    if (pointer) --outstanding;
    free(pointer);
}

int main(void)
{
    const double A[] = {1.0, 0.0, 0.0, 1.0};
    const double b[] = {0.0, 0.0};
    double scale[] = {1.0, 1.0};
    double lu[] = {1.0, 0.0, 0.0, 1.0};
    double x[] = {0.0, 0.0};
    int idx[] = {0, 1};
    int perm[] = {0, 1};
    BSUniqueWitness witness = {2, 2, idx, scale, perm, lu, x};
    const int expected[] = {3, 4, 6, 6, 6};

    for (fail_at = 1; fail_at <= 5; ++fail_at) {
        allocation_call = 0;
        outstanding = 0;
        double eta = 0.0;
        if (fesetround(FE_TOWARDZERO) != 0) return 2;
        int rc = bs_verify_unique(A, b, 2, 2, &witness, &eta);
        if (rc != expected[fail_at - 1] || fegetround() != FE_TOWARDZERO ||
            outstanding != 0 || !isinf(eta) || signbit(eta)) {
            fprintf(stderr,
                    "fail_at=%d rc=%d expected=%d mode=%d outstanding=%d eta=%a\n",
                    fail_at, rc, expected[fail_at - 1], fegetround(),
                    outstanding, eta);
            return 1;
        }
    }
    puts("unique verifier ENOMEM positions 1..5 restore fenv and leak no allocation: PASS");
    return 0;
}
