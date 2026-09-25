/* Exercise the private SVD state on actual wide, square, and tall cores.
 * bsolver_core.c is included by the production router, so this harness uses
 * the same implementation and build-time BLAS symbol mapping. */
#define BS_FAIL_RESULT(res,tzero) do{ (res).cls=CLS_FAIL; (res).rank=0; \
    (res).relres=NAN; (res).relx=NAN; (res).sec=now_sec()-(tzero); }while(0)
#define main bsolver_core_example_main
#include "bsolver_core.c"
#undef main
#include <sys/resource.h>

static int check_case(const char *name, int rows, int n, const double *singular,
                      int expected_rank, double ranktol) {
    size_t count = (size_t)rows * (size_t)n;
    double *core = calloc(count, sizeof(*core));
    double *y = calloc((size_t)rows, sizeof(*y));
    if (!core || !y) { free(core); free(y); return 1; }
    int minmn = rows < n ? rows : n;
    for (int i = 0; i < minmn; ++i) {
        core[(size_t)i * n + i] = singular[i];
        y[i] = singular[i] * (double)(i + 1);
    }

    BState state = {0};
    double relative_residual = -1.0;
    int failed = core_svd_state(core, y, rows, n, &state,
                                &relative_residual, ranktol) != 0;
    if (!failed && state.r != expected_rank) failed = 1;
    if (!failed && (!isfinite(relative_residual) || relative_residual > 1e-9))
        failed = 1;
    for (int j = 0; !failed && j < n; ++j) {
        double wanted_x = j < expected_rank ? (double)(j + 1) : 0.0;
        if (!isfinite(state.x[j]) || fabs(state.x[j] - wanted_x) > 1e-8)
            failed = 1;
        for (int k = 0; !failed && k < n; ++k) {
            double projector = 0.0;
            for (int l = 0; l < state.r; ++l)
                projector += state.Q[(size_t)l * n + j] *
                             state.Q[(size_t)l * n + k];
            double wanted = j == k && j < expected_rank ? 1.0 : 0.0;
            if (!isfinite(projector) || fabs(projector - wanted) > 1e-8)
                failed = 1;
        }
    }
    if (failed) fprintf(stderr, "%s: SVD x or row-space basis mismatch\n", name);
    else printf("PASS %s core=%dx%d rank=%d\n", name, rows, n, state.r);
    bs_free(&state);
    free(core); free(y);
    return failed;
}

static int measure_case(int rows, int n) {
    if (rows < 1 || n < 1 || rows > 2048 || n > 2048) return 2;
    double *core = calloc((size_t)rows * n, sizeof(*core));
    double *y = calloc((size_t)rows, sizeof(*y));
    if (!core || !y) { free(core); free(y); return 2; }
    /* A deterministic dense full-rank core, generated outside the timer. */
    for (int i = 0; i < rows; ++i)
        for (int j = 0; j < n; ++j) {
            double value = (double)((sm64((uint64_t)(i + 1) * 65537u +
                                     (uint64_t)(j + 1)) >> 11) & 0xffffu) / 65536.0;
            core[(size_t)i * n + j] = value + (i == j ? 2.0 : 0.0);
            y[i] += core[(size_t)i * n + j] / (double)(j + 1);
        }
    BState state = {0}; double rr = -1.0;
    double start = now_sec();
    int rc = core_svd_state(core, y, rows, n, &state, &rr, 1e-11);
    double elapsed = now_sec() - start;
    struct rusage use;
    getrusage(RUSAGE_SELF, &use);
    if (rc || !isfinite(rr) || !state.x || !state.Q) {
        fprintf(stderr, "measured core failed: %dx%d\n", rows, n);
        bs_free(&state); free(core); free(y); return 1;
    }
    printf("{\"rows\":%d,\"n\":%d,\"rank\":%d,\"seconds\":%.9g,"
           "\"peak_rss_kib\":%ld}\n", rows, n, state.r, elapsed, use.ru_maxrss);
    bs_free(&state); free(core); free(y); return 0;
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "--measure") == 0)
        return measure_case(atoi(argv[2]), atoi(argv[3]));
    if (argc != 1) return 2;
    const double wide[] = {1.0, 2.0, 3.0};
    const double square[] = {1.0, 2.0, 3.0, 4.0};
    const double tall[] = {1.0, 2.0, 3.0};
    const double rank_deficient[] = {1.0, 2.0, 0.0};
    const double zero[] = {0.0, 0.0, 0.0};
    const double near_threshold[] = {1.0, 0.5, 1e-12};
    int failures = 0;
    failures += check_case("wide", 3, 5, wide, 3, 1e-11);
    failures += check_case("square", 4, 4, square, 4, 1e-11);
    failures += check_case("tall", 5, 3, tall, 3, 1e-11);
    failures += check_case("wide-rank-deficient", 3, 5, rank_deficient, 2, 1e-11);
    failures += check_case("wide-rank-zero", 3, 5, zero, 0, 1e-11);
    failures += check_case("wide-near-threshold", 3, 5, near_threshold, 2, 1e-11);
    BState empty = {0}; double rr = -1.0;
    if (core_svd_state(NULL, NULL, 0, 5, &empty, &rr, 1e-11) != -1 ||
        core_svd_state(NULL, NULL, 3, 0, &empty, &rr, 1e-11) != -1) {
        fprintf(stderr, "zero dimension was not rejected\n");
        ++failures;
    }
    return failures ? 1 : 0;
}
