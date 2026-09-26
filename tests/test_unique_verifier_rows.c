/*
 * test_unique_verifier_rows.c -- row-level differential for bs_verify_unique.
 *
 * The unique checker reconstructs scale*(LU)[perm[ks],:] - a_i for every
 * selected source row in two directed-rounding passes.  This test compares
 * every reconstructed row against a frozen copy of the kernel it replaced
 * (main @ 1621d104, status_certificate.c lines 220-231), which materialised
 * the L row and each U column and called a volatile dot product.
 *
 * Expected, from the operation-sequence argument in status_certificate.c:
 *   - the entrywise error bound evec[j] is bit-identical;
 *   - elo[j] and ehi[j] are bit-identical except that an exactly-zero
 *     endpoint may differ in sign (the old kernel added structural zero
 *     products); such cases are counted and reported, never ignored;
 *   - every call returns 0 and restores the caller's rounding mode.
 *
 * Witness classes cover dense random factors, near-consistent certificates
 * (radius at ulp scale), wide exponent ranges with signed zeros and
 * subnormals, and diagonal factors like the frozen Task-5 benchmark slots.
 * Each class runs under all four starting rounding modes.
 *
 * Built with the strict flags and -DABS_TEST_UNIQUE_ROW_HOOK; the hook is
 * never compiled into an installed library.
 */
#include "affine_bundle/status_certificate.h"

#include <fenv.h>
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma STDC FENV_ACCESS ON

/* ---- frozen reference: main @ 1621d104 ---------------------------------- */

static void ref_dot_interval(const double *a, const double *b, int n,
                             double *lo, double *hi) {
    volatile double s, p;
    fesetround(FE_DOWNWARD);
    s = 0.0;
    for (int k = 0; k < n; ++k) { p = a[k] * b[k]; s = s + p; }
    *lo = s;
    fesetround(FE_UPWARD);
    s = 0.0;
    for (int k = 0; k < n; ++k) { p = a[k] * b[k]; s = s + p; }
    *hi = s;
}

static void ref_row(const BSUniqueWitness *w, const double *arow, int ks,
                    double *lo_out, double *hi_out, double *err_out,
                    double *lrow, double *ucol) {
    int n = w->n, lr = w->perm[ks];
    for (int k = 0; k < n; ++k)
        lrow[k] = (k < lr ? w->packed_lu[(size_t)lr*n+k] : (k == lr ? 1.0 : 0.0));
    for (int j = 0; j < n; ++j) {
        for (int k = 0; k < n; ++k)
            ucol[k] = (k <= j ? w->packed_lu[(size_t)k*n+j] : 0.0);
        double lo, hi; ref_dot_interval(lrow, ucol, n, &lo, &hi);
        volatile double slo, shi, elo, ehi;
        fesetround(FE_DOWNWARD); slo = w->scale[ks] * lo; elo = slo - arow[j];
        fesetround(FE_UPWARD);   shi = w->scale[ks] * hi; ehi = shi - arow[j];
        lo_out[j] = elo; hi_out[j] = ehi;
        err_out[j] = fmax(fabs((double)elo), fabs((double)ehi));
    }
}

/* ---- hook capture --------------------------------------------------------- */

static int hook_rows;
static int hook_n;
static int *hook_row_index;
static double *hook_lo, *hook_hi, *hook_err;

void abs_test_unique_row_hook(int row, int n, const double *lo,
                              const double *hi, const double *err) {
    if (n != hook_n) { fprintf(stderr, "hook: n=%d, expected %d\n", n, hook_n); exit(2); }
    if (hook_rows >= n) { fprintf(stderr, "hook: more than n selected rows\n"); exit(2); }
    hook_row_index[hook_rows] = row;
    memcpy(hook_lo + (size_t)hook_rows*n, lo, sizeof(double)*(size_t)n);
    memcpy(hook_hi + (size_t)hook_rows*n, hi, sizeof(double)*(size_t)n);
    memcpy(hook_err + (size_t)hook_rows*n, err, sizeof(double)*(size_t)n);
    ++hook_rows;
}

/* ---- deterministic inputs ------------------------------------------------- */

static uint64_t rng_state = 0x9E3779B97F4A7C15ULL;
static uint64_t next_u64(void) {
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 7; rng_state ^= rng_state << 17;
    return rng_state;
}
static double uniform_pm1(void) { return (double)(next_u64() >> 11) / 9007199254740992.0 * 2.0 - 1.0; }

enum { CLS_RANDOM, CLS_NEAR_CONSISTENT, CLS_WIDE_EXPONENT, CLS_DIAGONAL, CLS_COUNT };
static const char *cls_name[CLS_COUNT] = {"random", "near-consistent", "wide-exponent", "diagonal"};

static double draw(int cls) {
    double r = uniform_pm1();
    if (cls != CLS_WIDE_EXPONENT) return r;
    switch (next_u64() % 10) {
        case 0: return 0.0;
        case 1: return -0.0;
        case 2: return ldexp(r, -1070);                           /* subnormal */
        case 3: return ldexp(r, (int)(next_u64() % 1800) - 900);
        case 4: return ldexp(1.0, (int)(next_u64() % 200) - 100); /* exact powers of two */
        default: return r;
    }
}

static long n_calls, n_rows, n_entries, n_zero_sign_only, n_failures;

static int same_bits(double a, double b) { return memcmp(&a, &b, sizeof a) == 0; }

static void expect_nonfinite_bound_rejected(const char *name,
                                            const double *A, const double *b,
                                            int m, int n,
                                            const BSUniqueWitness *w) {
    int row_index[2];
    double lo[4], hi[4], err[4];
    hook_rows = 0;
    hook_n = n;
    hook_row_index = row_index;
    hook_lo = lo;
    hook_hi = hi;
    hook_err = err;

    int saved = fegetround();
    double eta = 0.0;
    fesetround(FE_TOWARDZERO);
    int rc = bs_verify_unique(A, b, m, n, w, &eta);
    int after = fegetround();
    fesetround(saved);

    if (rc != 7 || !isinf(eta) || eta < 0.0) {
        ++n_failures;
        fprintf(stderr, "[%s] non-finite derived bound accepted: rc=%d eta=%.17g\n",
                name, rc, eta);
    }
    if (after != FE_TOWARDZERO) {
        ++n_failures;
        fprintf(stderr, "[%s] rounding mode not restored\n", name);
    }
}

static void test_nonfinite_derived_bounds_fail_closed(void) {
    {
        const double A[] = {1.0}, b[] = {0.0};
        int idx[] = {0}, perm[] = {0};
        double scale[] = {DBL_MAX}, packed_lu[] = {2.0}, x[] = {0.0};
        BSUniqueWitness w = {1, 1, idx, scale, perm, packed_lu, x};
        expect_nonfinite_bound_rejected("reconstruction-overflow", A, b, 1, 1, &w);
    }
    {
        const double A[] = {1.0, 0.0, 0.0, 1.0};
        const double b[] = {DBL_MAX, DBL_MAX};
        int idx[] = {0, 1}, perm[] = {0, 1};
        double scale[] = {1.0, 1.0};
        double packed_lu[] = {1.0, 0.0, 0.0, 1.0};
        double x[] = {DBL_MAX, DBL_MAX};
        BSUniqueWitness w = {2, 2, idx, scale, perm, packed_lu, x};
        expect_nonfinite_bound_rejected("solution-norm-overflow", A, b, 2, 2, &w);
    }
}

static void run_case(int cls, int m, int n) {
    double *A = malloc(sizeof(double)*(size_t)m*n), *b = malloc(sizeof(double)*(size_t)m);
    BSUniqueWitness w; memset(&w, 0, sizeof w);
    w.m = m; w.n = n;
    w.idx = malloc(sizeof(int)*(size_t)n); w.scale = malloc(sizeof(double)*(size_t)n);
    w.perm = malloc(sizeof(int)*(size_t)n); w.packed_lu = malloc(sizeof(double)*(size_t)n*n);
    w.x = malloc(sizeof(double)*(size_t)n);
    int *rows = malloc(sizeof(int)*(size_t)m);
    double *rlo = malloc(sizeof(double)*(size_t)n), *rhi = malloc(sizeof(double)*(size_t)n);
    double *rerr = malloc(sizeof(double)*(size_t)n), *t1 = malloc(sizeof(double)*(size_t)n);
    double *t2 = malloc(sizeof(double)*(size_t)n);
    hook_row_index = malloc(sizeof(int)*(size_t)n);
    hook_lo = malloc(sizeof(double)*(size_t)n*n); hook_hi = malloc(sizeof(double)*(size_t)n*n);
    hook_err = malloc(sizeof(double)*(size_t)n*n);
    if (!A || !b || !w.idx || !w.scale || !w.perm || !w.packed_lu || !w.x || !rows || !rlo ||
        !rhi || !rerr || !t1 || !t2 || !hook_row_index || !hook_lo || !hook_hi || !hook_err) {
        fprintf(stderr, "allocation failed\n"); exit(2);
    }

    for (size_t q = 0; q < (size_t)m*n; ++q) A[q] = (cls == CLS_DIAGONAL) ? 0.0 : draw(cls);
    for (int i = 0; i < m; ++i) b[i] = draw(cls);
    for (size_t q = 0; q < (size_t)n*n; ++q) w.packed_lu[q] = (cls == CLS_DIAGONAL) ? 0.0 : draw(cls);
    for (int i = 0; i < n; ++i) {
        double *d = &w.packed_lu[(size_t)i*n+i];
        if (cls == CLS_DIAGONAL) *d = (next_u64() & 1) ? 0.6 + 0.4*fabs(uniform_pm1()) : -(0.6 + 0.4*fabs(uniform_pm1()));
        else if (*d == 0.0) *d = 1.0;
        if (cls == CLS_NEAR_CONSISTENT) *d += 2.0;
        w.scale[i] = fabs(uniform_pm1()) + 0.5;
        w.x[i] = draw(cls == CLS_DIAGONAL ? CLS_RANDOM : cls);
        w.perm[i] = i;
    }
    if (cls != CLS_DIAGONAL)
        for (int i = n - 1; i > 0; --i) { int j = (int)(next_u64() % (uint64_t)(i + 1)); int t = w.perm[i]; w.perm[i] = w.perm[j]; w.perm[j] = t; }
    for (int i = 0; i < m; ++i) rows[i] = i;
    for (int i = m - 1; i > 0; --i) { int j = (int)(next_u64() % (uint64_t)(i + 1)); int t = rows[i]; rows[i] = rows[j]; rows[j] = t; }
    for (int i = 0; i < n; ++i) w.idx[i] = (cls == CLS_DIAGONAL) ? i : rows[i];
    if (cls == CLS_DIAGONAL)                      /* A = D * diag(U): the slot geometry */
        for (int i = 0; i < n; ++i) A[(size_t)i*n+i] = w.scale[i] * w.packed_lu[(size_t)i*n+i];
    if (cls == CLS_NEAR_CONSISTENT) {             /* A rows = scale * fl(LU row) */
        fesetround(FE_TONEAREST);
        for (int ks = 0; ks < n; ++ks) {
            int lr = w.perm[ks];
            for (int j = 0; j < n; ++j) {
                double s = 0.0;
                for (int k = 0; k <= (lr < j ? lr : j); ++k)
                    s += (k < lr ? w.packed_lu[(size_t)lr*n+k] : 1.0) * w.packed_lu[(size_t)k*n+j];
                A[(size_t)w.idx[ks]*n+j] = w.scale[ks] * s;
            }
        }
    }

    const int modes[4] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    for (int md = 0; md < 4; ++md) {
        hook_rows = 0; hook_n = n;
        double eta = 0.0;
        fesetround(modes[md]);
        int rc = bs_verify_unique(A, b, m, n, &w, &eta);
        int after = fegetround();
        fesetround(FE_TONEAREST);
        ++n_calls;
        if (after != modes[md]) { ++n_failures; fprintf(stderr, "[%s %dx%d] rounding mode not restored\n", cls_name[cls], m, n); }
        if (rc != 0 && rc != 7) { ++n_failures; fprintf(stderr, "[%s %dx%d] rc=%d\n", cls_name[cls], m, n, rc); continue; }
        if (hook_rows != n) { ++n_failures; fprintf(stderr, "[%s %dx%d] %d rows observed, expected %d\n", cls_name[cls], m, n, hook_rows, n); continue; }
        for (int r = 0; r < hook_rows; ++r) {
            int i = hook_row_index[r], ks = -1;
            for (int t = 0; t < n; ++t) if (w.idx[t] == i) ks = t;
            if (ks < 0) { ++n_failures; fprintf(stderr, "hook reported unselected row %d\n", i); continue; }
            ref_row(&w, A + (size_t)i*n, ks, rlo, rhi, rerr, t1, t2);
            fesetround(FE_TONEAREST);
            ++n_rows;
            for (int j = 0; j < n; ++j) {
                size_t q = (size_t)r*n + j;
                ++n_entries;
                if (!same_bits(hook_err[q], rerr[j])) {
                    ++n_failures;
                    if (n_failures < 10) fprintf(stderr, "[%s %dx%d mode %d] row %d col %d: err %.17g != ref %.17g\n",
                                                 cls_name[cls], m, n, md, i, j, hook_err[q], rerr[j]);
                }
                for (int h = 0; h < 2; ++h) {
                    double got = h ? hook_hi[q] : hook_lo[q], ref = h ? rhi[j] : rlo[j];
                    if (same_bits(got, ref)) continue;
                    if (got == 0.0 && ref == 0.0) { ++n_zero_sign_only; continue; }
                    ++n_failures;
                    if (n_failures < 10) fprintf(stderr, "[%s %dx%d mode %d] row %d col %d: %s %.17g != ref %.17g\n",
                                                 cls_name[cls], m, n, md, i, j, h ? "hi" : "lo", got, ref);
                }
            }
        }
    }
    free(A); free(b); free(w.idx); free(w.scale); free(w.perm); free(w.packed_lu); free(w.x);
    free(rows); free(rlo); free(rhi); free(rerr); free(t1); free(t2);
    free(hook_row_index); free(hook_lo); free(hook_hi); free(hook_err);
}

int main(void) {
    test_nonfinite_derived_bounds_fail_closed();
    for (int t = 0; t < 480; ++t) {
        int n = 1 + (int)(next_u64() % 24), m = n + (int)(next_u64() % 8);
        run_case(t % CLS_COUNT, m, n);
    }
    static const int shapes[][2] = {{192, 192}, {256, 128}, {130, 129}};
    for (size_t s = 0; s < sizeof shapes / sizeof shapes[0]; ++s)
        for (int cls = 0; cls < CLS_COUNT; ++cls) run_case(cls, shapes[s][0], shapes[s][1]);

    printf("unique verifier rows: %ld calls, %ld rows, %ld entries compared; "
           "%ld signed-zero-only endpoint differences; %ld failures\n",
           n_calls, n_rows, n_entries, n_zero_sign_only, n_failures);
    if (n_entries == 0) { fprintf(stderr, "vacuous: no entries compared\n"); return 1; }
    return n_failures ? 1 : 0;
}
