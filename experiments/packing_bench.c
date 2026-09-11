#define _POSIX_C_SOURCE 200809L

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/*
 * Isolate the two layouts used by the fast router before a LAPACK call.
 * This is a diagnostic benchmark, not a CI performance gate: timings depend
 * on the host, while the memcmp checks are required on every run.
 *
 *   cc -O3 -march=native -std=c11 experiments/packing_bench.c -lm \
 *      -o /tmp/abs-packing-bench
 *   /tmp/abs-packing-bench
 */

typedef void (*pack_fn)(double *, const double *, int, int);
typedef void (*scaled_pack_fn)(double *, const double *, const double *, int);

#ifndef PACK_TILE
#define PACK_TILE 8
#endif

static void pack_naive(double *dst, const double *src, int rows, int cols) {
    for (int j = 0; j < cols; ++j)
        for (int i = 0; i < rows; ++i)
            dst[i + (size_t)j * rows] = src[(size_t)i * cols + j];
}

static void pack_tiled(double *dst, const double *src, int rows, int cols) {
    enum { TILE = PACK_TILE };
    for (int ib = 0; ib < rows; ib += TILE) {
        int iend = ib + TILE < rows ? ib + TILE : rows;
        for (int jb = 0; jb < cols; jb += TILE) {
            int jend = jb + TILE < cols ? jb + TILE : cols;
            for (int i = ib; i < iend; ++i) {
                const double *row = src + (size_t)i * cols;
                for (int j = jb; j < jend; ++j)
                    dst[i + (size_t)j * rows] = row[j];
            }
        }
    }
}

static void rows_as_columns_loop(double *dst, const double *src,
                                 int rows, int cols) {
    for (int j = 0; j < rows; ++j)
        for (int i = 0; i < cols; ++i)
            dst[i + (size_t)j * cols] = src[(size_t)j * cols + i];
}

static void rows_as_columns_memcpy(double *dst, const double *src,
                                   int rows, int cols) {
    for (int j = 0; j < rows; ++j)
        memcpy(dst + (size_t)j * cols, src + (size_t)j * cols,
               (size_t)cols * sizeof(double));
}

static void pack_scaled_naive(double *dst, const double *src,
                              const double *scale, int n) {
    for (int j = 0; j < n; ++j)
        for (int i = 0; i < n; ++i)
            dst[i + (size_t)j * n] = src[(size_t)i * n + j] / scale[i];
}

static void pack_scaled_tiled(double *dst, const double *src,
                              const double *scale, int n) {
    enum { TILE = PACK_TILE };
    for (int jb = 0; jb < n; jb += TILE) {
        int jend = jb + TILE < n ? jb + TILE : n;
        for (int i = 0; i < n; ++i) {
            const double *row = src + (size_t)i * n;
            double si = scale[i];
            for (int j = jb; j < jend; ++j)
                dst[i + (size_t)j * n] = row[j] / si;
        }
    }
}

static double seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

static double median(double *v, int n) {
    for (int i = 1; i < n; ++i) {
        double x = v[i];
        int j = i;
        while (j > 0 && v[j - 1] > x) {
            v[j] = v[j - 1];
            --j;
        }
        v[j] = x;
    }
    return v[n / 2];
}

static double measure(pack_fn fn, double *dst, const double *src,
                      int rows, int cols, int repeats) {
    enum { SAMPLES = 9 };
    double samples[SAMPLES];
    fn(dst, src, rows, cols);
    for (int s = 0; s < SAMPLES; ++s) {
        double t0 = seconds();
        for (int r = 0; r < repeats; ++r)
            fn(dst, src, rows, cols);
        samples[s] = (seconds() - t0) / repeats;
    }
    return median(samples, SAMPLES);
}

static double measure_scaled(scaled_pack_fn fn, double *dst, const double *src,
                             const double *scale, int n, int repeats) {
    enum { SAMPLES = 9 };
    double samples[SAMPLES];
    fn(dst, src, scale, n);
    for (int s = 0; s < SAMPLES; ++s) {
        double t0 = seconds();
        for (int r = 0; r < repeats; ++r)
            fn(dst, src, scale, n);
        samples[s] = (seconds() - t0) / repeats;
    }
    return median(samples, SAMPLES);
}

static int run_case(int rows, int cols) {
    size_t count = (size_t)rows * cols;
    double *src = malloc(count * sizeof(*src));
    double *ref = malloc(count * sizeof(*ref));
    double *got = malloc(count * sizeof(*got));
    double *scale = malloc((size_t)rows * sizeof(*scale));
    if (!src || !ref || !got || !scale) {
        free(src);
        free(ref);
        free(got);
        free(scale);
        return 1;
    }
    for (size_t k = 0; k < count; ++k)
        src[k] = sin((double)(k % 8191)) + (double)(k & 7u);
    for (int i = 0; i < rows; ++i) scale[i] = 1.0 + (i & 7);

    pack_naive(ref, src, rows, cols);
    pack_tiled(got, src, rows, cols);
    if (memcmp(ref, got, count * sizeof(*ref)) != 0) {
        fprintf(stderr, "transpose mismatch for %dx%d\n", rows, cols);
        free(src);
        free(ref);
        free(got);
        free(scale);
        return 1;
    }

    int repeats = (int)(100000000u / (count ? count : 1));
    if (repeats < 3) repeats = 3;
    if (repeats > 20000) repeats = 20000;
    double naive = measure(pack_naive, got, src, rows, cols, repeats);
    double tiled = measure(pack_tiled, got, src, rows, cols, repeats);

    rows_as_columns_loop(ref, src, rows, cols);
    rows_as_columns_memcpy(got, src, rows, cols);
    if (memcmp(ref, got, count * sizeof(*ref)) != 0) {
        fprintf(stderr, "row-copy mismatch for %dx%d\n", rows, cols);
        free(src);
        free(ref);
        free(got);
        free(scale);
        return 1;
    }
    double loop = measure(rows_as_columns_loop, got, src, rows, cols, repeats);
    double copy = measure(rows_as_columns_memcpy, got, src, rows, cols, repeats);

    double scaled_naive = NAN, scaled_tiled = NAN;
    if (rows == cols) {
        pack_scaled_naive(ref, src, scale, rows);
        pack_scaled_tiled(got, src, scale, rows);
        if (memcmp(ref, got, count * sizeof(*ref)) != 0) {
            fprintf(stderr, "scaled transpose mismatch for %dx%d\n", rows, cols);
            free(src);
            free(ref);
            free(got);
            free(scale);
            return 1;
        }
        scaled_naive = measure_scaled(pack_scaled_naive, got, src, scale,
                                      rows, repeats);
        scaled_tiled = measure_scaled(pack_scaled_tiled, got, src, scale,
                                      rows, repeats);
    }

    printf("%d,%d,%.9g,%.9g,%.3f,%.9g,%.9g,%.3f,%.9g,%.9g,%.3f\n",
           rows, cols, naive, tiled, naive / tiled, loop, copy, loop / copy,
           scaled_naive, scaled_tiled, scaled_naive / scaled_tiled);
    free(src);
    free(ref);
    free(got);
    free(scale);
    return 0;
}

int main(void) {
    static const int shapes[][2] = {
        {64, 64}, {256, 256}, {512, 512}, {64, 2048}, {192, 800}
    };
    puts("rows,cols,naive_s,tiled_s,transpose_speedup,loop_s,memcpy_s,row_copy_speedup,scaled_naive_s,scaled_tiled_s,scaled_speedup");
    for (size_t k = 0; k < sizeof(shapes) / sizeof(shapes[0]); ++k)
        if (run_case(shapes[k][0], shapes[k][1])) return 1;
    return 0;
}
