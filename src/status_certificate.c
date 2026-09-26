/*
 * status_certificate.c -- Independent checker for unique / infinite / inconsistent proof objects.
 *
 * Copyright 2026 Viktor Mikhalkin
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#pragma STDC FENV_ACCESS ON
#include "affine_bundle/status_certificate.h"
#include <fenv.h>
#include <limits.h>
#include <math.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

static int finite_vec(const double *x, size_t n) {
    if (!x) return 0;
    for (size_t i = 0; i < n; ++i) if (!isfinite(x[i])) return 0;
    return 1;
}

static void dot_interval(const double *a, const double *b, int n,
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

/* Directed LASSQ-style Euclidean norms.  Direct sum(v*v) loses
   availability when the data live near either end of the binary64 exponent
   range.  A power-of-two scale is exact, so all squaring is performed on
   O(1) numbers and only the final result is rescaled.  Under the strict build
   used by this checker, sqrt and the arithmetic below honor the active
   directed rounding mode. */
static int max_abs_exp_vec(const double *a, int n, double extra, int have_extra) {
    int emax = FP_ILOGB0;
    for (int i = 0; i < n; ++i) {
        double q = fabs(a[i]);
        if (q > 0.0) { int e = ilogb(q); if (emax == FP_ILOGB0 || e > emax) emax = e; }
    }
    if (have_extra) {
        double q = fabs(extra);
        if (q > 0.0) { int e = ilogb(q); if (emax == FP_ILOGB0 || e > emax) emax = e; }
    }
    return emax;
}

static double scaled_norm_dir(const double *a, int n, double extra, int have_extra, int mode) {
    int e = max_abs_exp_vec(a, n, extra, have_extra);
    if (e == FP_ILOGB0) return 0.0;
    volatile double ss = 0.0, r, p, root, out;
    fesetround(mode);
    for (int i = 0; i < n; ++i) {
        r = scalbn(a[i], -e); p = r * r; ss = ss + p;
    }
    if (have_extra) { r = scalbn(extra, -e); p = r * r; ss = ss + p; }
    root = sqrt(ss);
    out = scalbn(root, e);
    return out;
}

static double norm_up(const double *a, int n) {
    return scaled_norm_dir(a, n, 0.0, 0, FE_UPWARD);
}

static double norm_lower(const double *a, int n) {
    return scaled_norm_dir(a, n, 0.0, 0, FE_DOWNWARD);
}

static double norm_aug_lower(const double *a, double b, int n) {
    return scaled_norm_dir(a, n, b, 1, FE_DOWNWARD);
}

static double hypot_up(double a, double b) {
    double v[2] = {a, b};
    return norm_up(v, 2);
}


/* Exponent-framed interval products for the inconsistent proof.  A left-null
   witness and the source may occupy opposite ends of the binary64 exponent
   range, so forming y_i*a_ij directly can overflow even when the normalized
   dot product is perfectly benign.  frexp decomposes each input exactly;
   only O(1) mantissas are multiplied and all terms are accumulated in one
   common power-of-two frame. */
static int common_product_exp(const double *y, int m,
                              const double *A, const double *b, int n) {
    int E = INT_MIN;
    for (int i = 0; i < m; ++i) {
        if (y[i] == 0.0) continue;
        int ey = 0; (void)frexp(y[i], &ey);
        if (b[i] != 0.0) {
            int eb = 0; (void)frexp(b[i], &eb);
            if (ey + eb > E) E = ey + eb;
        }
        for (int j = 0; j < n; ++j) if (A[(size_t)i*n+j] != 0.0) {
            int ea = 0; (void)frexp(A[(size_t)i*n+j], &ea);
            if (ey + ea > E) E = ey + ea;
        }
    }
    return E;
}

static double product_in_frame_dir(double a, double b, int E, int mode) {
    if (a == 0.0 || b == 0.0) return 0.0;
    int ea = 0, eb = 0;
    double ma = frexp(a, &ea), mb = frexp(b, &eb);
    volatile double p, q;
    fesetround(mode);
    p = ma * mb;
    q = scalbn(p, ea + eb - E);
    return q;
}

static void dot_interval_frame(const double *a, const double *b, int n, int E,
                               double *lo, double *hi) {
    volatile double s, p;
    fesetround(FE_DOWNWARD); s = 0.0;
    for (int k = 0; k < n; ++k) { p = product_in_frame_dir(a[k], b[k], E, FE_DOWNWARD); s = s + p; }
    *lo = s;
    fesetround(FE_UPWARD); s = 0.0;
    for (int k = 0; k < n; ++k) { p = product_in_frame_dir(a[k], b[k], E, FE_UPWARD); s = s + p; }
    *hi = s;
}

/* Downward lower bound for |a|*b*2^{-E}, with b>=0. */
static double positive_product_lower_frame(double a, double b, int E) {
    if (!(a > 0.0) || !(b > 0.0)) return 0.0;
    int ea = 0, eb = 0;
    double ma = frexp(a, &ea), mb = frexp(b, &eb);
    volatile double p, q;
    fesetround(FE_DOWNWARD);
    p = ma * mb;
    q = scalbn(p, ea + eb - E);
    return q;
}

static double residual_abs_up(const double *a, double b,
                              const double *x, int n) {
    double lo, hi;
    volatile double rlo, rhi;
    dot_interval(a, x, n, &lo, &hi);
    fesetround(FE_DOWNWARD); rlo = lo - b;
    fesetround(FE_UPWARD);   rhi = hi - b;
    return fmax(fabs((double)rlo), fabs((double)rhi));
}

static int valid_perm(const int *p, int n) {
    int *seen = (int *)calloc((size_t)n, sizeof(int));
    if (!seen) return 0;
    for (int i = 0; i < n; ++i) {
        if (p[i] < 0 || p[i] >= n || seen[p[i]]) { free(seen); return 0; }
        seen[p[i]] = 1;
    }
    free(seen);
    return 1;
}

#if defined(__GNUC__) || defined(__clang__)
#define ABS_NOINLINE __attribute__((noinline))
#else
#define ABS_NOINLINE
#endif

/* One directed-rounding pass of the unique-object row reconstruction.  The
   caller sets the rounding mode; this function performs no mode change.

   For source row i selected as factor row lr = perm[ks] it forms, for every
   column j,
       acc[j] = sum_{k=0}^{min(lr,j)} L[lr,k] * U[k,j]      (L[lr,lr] = 1)
       e[j]   = scale * acc[j] - a[j]
   with every product and sum rounded in the caller's mode.  For each j the
   terms are added in increasing k, starting from 0.0, which is exactly the
   operation sequence of the former materialized dot product minus its
   structural zero terms (k > lr or k > j).  Adding an exact zero leaves a
   nonzero partial sum unchanged in every rounding mode, so the two
   formulations differ at most in the sign of an exactly-zero interval
   endpoint, which fabs() removes before any radius is formed.

   The loop is ordered over k and then over j, so each pass streams rows of
   the packed factor instead of striding down its columns, and the rounding
   mode is set twice per selected row rather than four times per entry.
   noinline keeps every floating-point operation of the pass inside a call
   made after the caller's fesetround, so none can be scheduled across a mode
   change.  The strict flags forbid contraction (see CMakeLists.txt), which
   the bit-identity above also requires. */
ABS_NOINLINE static void unique_row_pass(const double *restrict lu, int n,
                                         int lr, double scale,
                                         const double *restrict arow,
                                         double *restrict acc,
                                         double *restrict e) {
    for (int j = 0; j < n; ++j) acc[j] = 0.0;
    for (int k = 0; k <= lr; ++k) {
        double lk = (k < lr) ? lu[(size_t)lr*n+k] : 1.0;
        const double *urow = lu + (size_t)k*n;
        for (int j = k; j < n; ++j) { double p = lk * urow[j]; acc[j] = acc[j] + p; }
    }
    for (int j = 0; j < n; ++j) { double s = scale * acc[j]; e[j] = s - arow[j]; }
}

void bs_unique_witness_free(BSUniqueWitness *w) {
    if (!w) return;
    free(w->idx); free(w->scale); free(w->perm); free(w->packed_lu); free(w->x);
    memset(w, 0, sizeof(*w));
}
void bs_infinite_witness_free(BSInfiniteWitness *w) {
    if (!w) return; free(w->x); free(w->z); memset(w, 0, sizeof(*w));
}
void bs_inconsistent_witness_free(BSInconsistentWitness *w) {
    if (!w) return; free(w->y); memset(w, 0, sizeof(*w));
}

int bs_verify_unique(const double *A, const double *b, int m, int n,
                     const BSUniqueWitness *w, double *eta_up) {
    if (eta_up) *eta_up = INFINITY;
    if (!A || !b || !w || !eta_up || m < n || n <= 0 || w->m != m || w->n != n)
        return 1;
    if (!finite_vec(A, (size_t)m*n) || !finite_vec(b, (size_t)m) ||
        !finite_vec(w->x, (size_t)n) || !finite_vec(w->scale, (size_t)n) ||
        !finite_vec(w->packed_lu, (size_t)n*n)) return 2;
    if (!valid_perm(w->perm, n)) return 3;

    int *pos = (int *)malloc((size_t)m * sizeof(int));
    if (!pos) return 4;
    for (int i = 0; i < m; ++i) pos[i] = -1;
    for (int i = 0; i < n; ++i) {
        if (!w->idx || w->idx[i] < 0 || w->idx[i] >= m || pos[w->idx[i]] >= 0 ||
            !(w->scale[i] > 0.0) || w->packed_lu[(size_t)i*n+i] == 0.0) {
            free(pos); return 5;
        }
        pos[w->idx[i]] = i;
    }

    int old = fegetround();
    double xn_up = norm_up(w->x, n), best = 0.0;
    /* ehi and elo hold the upward and downward bounds of scale*(LU)[lr,:]-a_i;
       evec is the pass accumulator and then the entrywise |error| bound. */
    double *ehi = (double *)malloc((size_t)n*sizeof(double));
    double *elo = (double *)malloc((size_t)n*sizeof(double));
    double *evec = (double *)malloc((size_t)n*sizeof(double));
    if (!ehi || !elo || !evec) { free(pos); free(ehi); free(elo); free(evec); fesetround(old); return 6; }

    for (int i = 0; i < m; ++i) {
        double da_up = 0.0;
        int ks = pos[i];
        if (ks >= 0) {
            int lr = w->perm[ks];
            const double *arow = A + (size_t)i*n;
            fesetround(FE_DOWNWARD);
            unique_row_pass(w->packed_lu, n, lr, w->scale[ks], arow, evec, elo);
            fesetround(FE_UPWARD);
            unique_row_pass(w->packed_lu, n, lr, w->scale[ks], arow, evec, ehi);
            for (int j = 0; j < n; ++j) evec[j] = fmax(fabs(elo[j]), fabs(ehi[j]));
            da_up = norm_up(evec, n);
        }
        double res_up = residual_abs_up(A+(size_t)i*n, b[i], w->x, n);
        fesetround(FE_UPWARD);
        double db_up = res_up + da_up*xn_up;
        double pert = hypot_up(da_up, db_up);
        double src = norm_aug_lower(A+(size_t)i*n, b[i], n);
        double q;
        if (src == 0.0) q = (pert == 0.0 ? 0.0 : INFINITY);
        else { fesetround(FE_UPWARD); q = pert/src; }
        if (q > best) best = q;
    }
    free(pos); free(ehi); free(elo); free(evec); fesetround(old);
    *eta_up = best;
    return isfinite(best) ? 0 : 7;
}

int bs_verify_infinite(const double *A, const double *b, int m, int n,
                       const BSInfiniteWitness *w, double *eta_up) {
    if (eta_up) *eta_up = INFINITY;
    if (!A || !b || !w || !eta_up || m < 0 || n <= 0 || w->n != n) return 1;
    if (!finite_vec(A, (size_t)m*n) || !finite_vec(b, (size_t)m) ||
        !finite_vec(w->x, (size_t)n) || !finite_vec(w->z, (size_t)n)) return 2;
    int old = fegetround();
    double zn_lo = norm_lower(w->z, n);
    if (!(zn_lo > 0.0)) { fesetround(old); return 3; }
    double xn_up = norm_up(w->x, n), best = 0.0;
    for (int i = 0; i < m; ++i) {
        double lo, hi; dot_interval(A+(size_t)i*n, w->z, n, &lo, &hi);
        fesetround(FE_UPWARD);
        double az_up = fmax(fabs(lo), fabs(hi));
        double erow = az_up / zn_lo;
        double res_up = residual_abs_up(A+(size_t)i*n, b[i], w->x, n);
        double db_up = res_up + erow*xn_up;
        double pert = hypot_up(erow, db_up);
        double src = norm_aug_lower(A+(size_t)i*n, b[i], n);
        double q;
        if (src == 0.0) q = (pert == 0.0 ? 0.0 : INFINITY);
        else { fesetround(FE_UPWARD); q = pert/src; }
        if (q > best) best = q;
    }
    fesetround(old); *eta_up = best;
    return isfinite(best) ? 0 : 4;
}

int bs_verify_inconsistent(const double *A, const double *b, int m, int n,
                           const BSInconsistentWitness *w,
                           double *ytb_lo, double *ytb_hi, double *eta_up) {
    if (eta_up) *eta_up = INFINITY;
    if (!A || !b || !w || !ytb_lo || !ytb_hi || !eta_up ||
        m <= 0 || n < 0 || w->m != m || w->pivot_row < 0 || w->pivot_row >= m) return 1;
    if (!finite_vec(A, (size_t)m*n) || !finite_vec(b, (size_t)m) || !finite_vec(w->y, (size_t)m)) return 2;
    int k = w->pivot_row;
    if (w->y[k] == 0.0) return 3;
    int old = fegetround();

    int E = common_product_exp(w->y, m, A, b, n);
    if (E == INT_MIN) { fesetround(old); return 4; }

    /* Bounds are for 2^{-E} y^T b.  The positive power-of-two frame changes
       neither the sign proof nor the relative perturbation radius. */
    double lb, ub; dot_interval_frame(w->y, b, m, E, &lb, &ub);
    *ytb_lo = lb; *ytb_hi = ub;
    if (!(lb > 0.0 || ub < 0.0)) { fesetround(old); return 4; }

    double *col = (double *)malloc((size_t)m*sizeof(double));
    double *qvec = (double *)malloc((size_t)(n > 0 ? n : 1)*sizeof(double));
    if (!col || !qvec) { free(col); free(qvec); fesetround(old); return 5; }
    for (int j = 0; j < n; ++j) {
        for (int i = 0; i < m; ++i) col[i] = A[(size_t)i*n+j];
        double lo, hi; dot_interval_frame(col, w->y, m, E, &lo, &hi);
        qvec[j] = fmax(fabs(lo), fabs(hi));
    }
    double Hs = norm_up(qvec, n); /* upper bound for 2^{-E} ||A^T y|| */
    double src = norm_aug_lower(A+(size_t)k*n, b[k], n);
    double dens = positive_product_lower_frame(fabs(w->y[k]), src, E);
    double q;
    if (dens == 0.0) q = (Hs == 0.0 ? 0.0 : INFINITY);
    else { fesetround(FE_UPWARD); q = Hs/dens; }
    free(col); free(qvec); fesetround(old); *eta_up = q;
    return isfinite(q) ? 0 : 6;
}
