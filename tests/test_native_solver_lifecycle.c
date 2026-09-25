/* Leak-sensitive API lifecycle coverage without a CPython/NumPy host. */
#include <affine_bundle/certified_api.h>
#include <affine_bundle/router.h>
#include <affine_bundle/stream.h>
#include <math.h>
#include <stdio.h>

/* The individual strategy entry points are exported but intentionally not
   public-header APIs. Their signatures mirror the existing route test. */
extern void bsolve_global_qr_api(const double *, const double *, const double *,
                                  int, int, int, int, int, unsigned long long,
                                  int, double *);
extern void bsolve_block_api(const double *, const double *, const double *,
                              int, int, int, int, int, unsigned long long,
                              int, double *);
extern void bsolve_fast_api(const double *, const double *, const double *,
                             int, int, int, int, int, unsigned long long,
                             int, double *);
extern void bsolve_auto_qr_api(const double *, const double *, const double *,
                                int, int, int, int, int, int,
                                unsigned long long, int, double *);

static int check_case(const double *A, const double *b, int m, int n)
{
    double meta[ABS_OUT_LEN], legacy[7], eta = NAN, lo = NAN, hi = NAN;
    int grey[4], interval[2];
    unsigned long long counters[3];
    BSCertifiedResult result;
    BSUniqueWitness unique = {0};
    BSInfiniteWitness infinite = {0};
    BSInconsistentWitness inconsistent = {0};
    int rc;

    bsolve_router_meta_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, meta);
    if (meta[ABS_OUT_STATUS] < 1 || meta[ABS_OUT_STATUS] > 5) return 0;
    bsolve_router_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, legacy);
    bsolve_router_diag_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, meta, grey, 4);
    (void)bsolve_last_grey_total_api();
    (void)bsolve_last_orth_eta_api();
    bsolve_last_core_rank_interval_api(interval);
    (void)bsolve_last_core_qr_rank_api();
    bsolve_fg_counters_api(counters);
    bsolve_global_qr_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, legacy);
    bsolve_block_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, legacy);
    bsolve_fast_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, legacy);
    bsolve_auto_qr_api(A, b, NULL, m, n, 1, 2, 2, 1, 3, 0, legacy);

    rc = bsolve_certified_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, &result);
    if (rc != 0 || result.fast_status < 1 || result.fast_status > 5) return 0;
    if (bsolve_certified_api(A, b, NULL, m, n, 1, 2, 2, 3, 0, NULL) == 0)
        return 0;

    /* Exercise generator-owned witness buffers and their documented frees,
       even when a witness type cannot be accepted for this matrix. */
    rc = bs_generate_unique_witness(A, b, m, n, &unique);
    if (rc == 0) (void)bs_verify_unique(A, b, m, n, &unique, &eta);
    bs_unique_witness_free(&unique);
    rc = bs_generate_infinite_witness(A, b, m, n, &infinite);
    if (rc == 0) (void)bs_verify_infinite(A, b, m, n, &infinite, &eta);
    bs_infinite_witness_free(&infinite);
    rc = bs_generate_inconsistent_witness(A, b, m, n, &inconsistent);
    if (rc == 0)
        (void)bs_verify_inconsistent(A, b, m, n, &inconsistent, &lo, &hi, &eta);
    bs_inconsistent_witness_free(&inconsistent);
    return 1;
}

static int check_stream(void)
{
    const double first[] = {1.0, 0.0};
    const double second[] = {0.0, 1.0};
    const double contradiction[] = {1.0, 0.0};
    double status[ABS_OUT_LEN], x[2];
    long long seen, deferred;
    ABSStream *stream = abs_stream_create(2);
    int good = 0;
    if (!stream || abs_stream_create(0) != NULL) goto done;
    if (abs_stream_insert(stream, first, 1.0) != ABS_INSERT_GROW) goto done;
    if (abs_stream_insert(stream, second, 2.0) != ABS_INSERT_GROW) goto done;
    abs_stream_counts(stream, &seen, &deferred);
    abs_stream_status(stream, status);
    if (seen != 2 || deferred != 0 || status[ABS_OUT_RANK] != 2.0 ||
        !abs_stream_solution(stream, x)) goto done;
    if (abs_stream_insert(stream, contradiction, 2.0) != ABS_INSERT_CONTRA)
        goto done;
    abs_stream_status(stream, status);
    if (status[ABS_OUT_STATUS] != ABS_STATUS_INCONSISTENT) goto done;
    good = 1;
done:
    abs_stream_destroy(stream);
    return good;
}

static int check_rejected_witnesses(void)
{
    const double A[] = {1, 0, 0, 1}, b[] = {0, 0};
    const double Az[] = {0, 0}, bz[] = {1, 1};
    double x[] = {0, 0}, y[] = {1, -1}, scale[] = {1, 1};
    double lu[] = {1, 0, 0, 1}, z[] = {0, 0};
    int idx[] = {0, 1}, bad_perm[] = {0, 0};
    double eta = 0, lo = 0, hi = 0;
    BSUniqueWitness unique = {2, 2, idx, scale, bad_perm, lu, x};
    BSInfiniteWitness infinite = {2, x, z};
    BSInconsistentWitness inconsistent = {2, y, 0};
    return bs_verify_unique(A, b, 2, 2, &unique, &eta) != 0 &&
           bs_verify_infinite(A, b, 2, 2, &infinite, &eta) != 0 &&
           bs_verify_inconsistent(Az, bz, 2, 1, &inconsistent,
                                  &lo, &hi, &eta) != 0;
}

int main(void)
{
    const double unique_A[] = {1, 0, 0, 1, 1, 1};
    const double unique_b[] = {1, 2, 3};
    const double deficient_A[] = {1, 0, 2, 0, 3, 0};
    const double infinite_b[] = {1, 2, 3};
    const double inconsistent_b[] = {1, 2, 4};
    double dep, growth;
    abs_thresholds(&dep, &growth);
    if (!(dep > 0 && growth > dep && abs_quality_threshold() > 0) ||
        !check_stream() || !check_rejected_witnesses() ||
        !check_case(unique_A, unique_b, 3, 2) ||
        !check_case(deficient_A, infinite_b, 3, 2) ||
        !check_case(deficient_A, inconsistent_b, 3, 2)) {
        fputs("native solver lifecycle: FAIL\n", stderr);
        return 1;
    }
    puts("native stream/router/certified/witness lifecycle: PASS");
    return 0;
}
