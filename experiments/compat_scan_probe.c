/* Test/benchmark adapter only; no additions to the installed API.
 * Including the real router exposes its private scan, as existing internal
 * SVD tests do. Compile with the production router command and link the
 * separately compiled, unchanged formation guard. */
#include "bsolver.c"

void abs_compat_scan_probe(const double *a, const double *b, const double *x,
                           int m, int n, double tc, double *out) {
    double rr;
    int bad = compat_scan_fused(a, b, x, m, n, tc, &rr);
    out[0] = bad;
    out[1] = rr;
    out[2] = g_last_berr;
    out[3] = g_last_berr_valid;
    out[4] = g_last_berr > BS_QUALITY_THR;
}
