#include "affine_bundle/status_certificate.h"

#include <dlfcn.h>
#include <fenv.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

typedef int (*verify_unique_fn)(const double *, const double *, int, int,
                                const BSUniqueWitness *, double *);

static int same_bits(double left, double right)
{
    return memcmp(&left, &right, sizeof left) == 0;
}

static int expect_rejected(verify_unique_fn verify, const char *name,
                           const double *A, const double *b, int m, int n,
                           BSUniqueWitness *w)
{
    static const int modes[] = {
        FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO
    };
    for (size_t i = 0; i < sizeof modes / sizeof modes[0]; ++i) {
        double eta = 0.0;
        if (fesetround(modes[i]) != 0) return 90;
        int rc = verify(A, b, m, n, w, &eta);
        if (rc != 7 || !isinf(eta) || signbit(eta) || fegetround() != modes[i]) {
            fprintf(stderr, "%s mode=%d rc=%d eta=%a after=%d\n",
                    name, modes[i], rc, eta, fegetround());
            return 1;
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        fprintf(stderr, "dlopen: %s\n", dlerror());
        return 2;
    }
    verify_unique_fn verify = NULL;
    *(void **)(&verify) = dlsym(handle, "bs_verify_unique");
    if (!verify) return 2;

    const double one[] = {1.0};
    const double zero[] = {0.0};
    const double huge[] = {DBL_MAX};
    const double plus_two[] = {2.0};
    const double minus_two[] = {-2.0};
    double x_zero[] = {-0.0};
    int index[] = {0};
    int perm[] = {0};
    BSUniqueWitness w = {1, 1, index, (double *)huge, perm,
                         (double *)plus_two, x_zero};

    int failures = 0;
    failures += expect_rejected(verify, "positive-reconstruction-overflow",
                                one, zero, 1, 1, &w);
    w.packed_lu = (double *)minus_two;
    failures += expect_rejected(verify, "negative-reconstruction-overflow",
                                one, zero, 1, 1, &w);

    const double identity[] = {1.0, 0.0, 0.0, 1.0};
    const double rhs[] = {DBL_MAX, DBL_MAX};
    double scales[] = {1.0, 1.0};
    double solution[] = {DBL_MAX, DBL_MAX};
    int indices[] = {0, 1};
    int perms[] = {0, 1};
    BSUniqueWitness norm_w = {2, 2, indices, scales, perms,
                              (double *)identity, solution};
    failures += expect_rejected(verify, "solution-norm-overflow",
                                identity, rhs, 2, 2, &norm_w);

    double scale_one[] = {1.0};
    double lu_one[] = {1.0};
    BSUniqueWitness ordinary = {1, 1, index, scale_one, perm, lu_one, x_zero};
    double eta = -1.0;
    if (fesetround(FE_DOWNWARD) != 0) return 90;
    int rc = verify(one, zero, 1, 1, &ordinary, &eta);
    double positive_zero = 0.0;
    if (rc != 0 || !same_bits(eta, positive_zero) || fegetround() != FE_DOWNWARD) {
        fprintf(stderr, "ordinary rc=%d eta=%a after=%d\n", rc, eta, fegetround());
        ++failures;
    }

    dlclose(handle);
    if (failures) return 1;
    puts("non-finite derived bounds fail closed and ordinary signed-zero case is stable: PASS");
    return 0;
}
