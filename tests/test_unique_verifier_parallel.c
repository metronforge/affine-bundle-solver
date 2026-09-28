/* Test-only instrumentation for the strict UNIQUE outer-row parallel path.
   The installed verifier never exports this hook. */
#include <affine_bundle/status_certificate.h>

#include <fenv.h>
#include <math.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { N = 32 };
static int worker_hits[N];

void abs_test_unique_thread_hook(void)
{
    int tid = omp_get_thread_num();
    if (tid >= 0 && tid < N) ++worker_hits[tid];
}

static int observed_workers(void)
{
    int count = 0;
    for (int i = 0; i < N; ++i) if (worker_hits[i]) ++count;
    return count;
}

static int run_case(const char *setting, int expected_workers,
                    const double *A, const double *b, BSUniqueWitness *w,
                    double *reference_eta, int *have_reference)
{
    double eta = INFINITY;
    int saved = fegetround();
    memset(worker_hits, 0, sizeof(worker_hits));
    if (setenv("ABS_CERT_UNIQUE_THREADS", setting, 1)) return 1;
    fesetround(FE_TOWARDZERO);
    int rc = bs_verify_unique(A, b, N, N, w, &eta);
    int after = fegetround();
    fesetround(saved);
    if (rc != 0 || after != FE_TOWARDZERO || observed_workers() != expected_workers) {
        fprintf(stderr, "setting=%s rc=%d restored=%d workers=%d expected=%d\n",
                setting, rc, after == FE_TOWARDZERO, observed_workers(), expected_workers);
        return 1;
    }
    if (!*have_reference) { *reference_eta = eta; *have_reference = 1; }
    else if (memcmp(reference_eta, &eta, sizeof eta)) {
        fprintf(stderr, "setting=%s changed eta %.17g -> %.17g\n", setting,
                *reference_eta, eta);
        return 1;
    }
    return 0;
}

int main(void)
{
    double A[N * N] = {0.0}, b[N] = {0.0}, scale[N], lu[N * N] = {0.0}, x[N] = {0.0};
    int idx[N], perm[N];
    BSUniqueWitness w = {N, N, idx, scale, perm, lu, x};
    double reference_eta = INFINITY;
    int have_reference = 0;
    for (int i = 0; i < N; ++i) {
        A[(size_t)i * N + i] = 1.0;
        lu[(size_t)i * N + i] = 1.0;
        idx[i] = perm[i] = i;
        scale[i] = 1.0;
    }
    if (run_case("1", 1, A, b, &w, &reference_eta, &have_reference) ||
        run_case("2", 2, A, b, &w, &reference_eta, &have_reference) ||
        run_case("4", 4, A, b, &w, &reference_eta, &have_reference) ||
        run_case("8", 8, A, b, &w, &reference_eta, &have_reference) ||
        run_case("16", 16, A, b, &w, &reference_eta, &have_reference) ||
        run_case("invalid", 1, A, b, &w, &reference_eta, &have_reference))
        return 1;
    puts("parallel strict UNIQUE: deterministic workers, eta, and fenv restoration: PASS");
    return 0;
}
