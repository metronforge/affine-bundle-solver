/* Exercise the same production growth/retry path without Linux RLIMIT_AS.
 * Only this translation unit intercepts realloc; installed code is unchanged. */
#define _POSIX_C_SOURCE 200809L
#include <stdlib.h>
#include <stdio.h>
#include <affine_bundle/stream.h>
static int fail_growth;
static int intercepted;
static void *test_realloc(void *p, size_t n) {
    if (fail_growth) { ++intercepted; return NULL; }
    return realloc(p, n);
}
#define realloc test_realloc
#include "../src/bsolver.c"
#undef realloc

int main(void) {
    const double row[4] = {1, 0, 0, 0};
    ABSStream *s = abs_stream_create(4);
    long long seen = -1, deferred = -1;
    double status[ABS_OUT_LEN];
    if (!s) return 1;
    fail_growth = 1;
    int rc = abs_stream_insert(s, row, 1.0);
    abs_stream_counts(s, &seen, &deferred);
    abs_stream_status(s, status);
    int failed = rc != ABS_INSERT_ENOMEM || !intercepted || seen != 0 ||
                 deferred != 0 || status[2] != 0;
    fail_growth = 0;
    rc = abs_stream_insert(s, row, 1.0);
    abs_stream_counts(s, &seen, &deferred);
    abs_stream_status(s, status);
    failed |= rc != ABS_INSERT_GROW || seen != 1 || deferred != 0 || status[2] != 1;
    abs_stream_destroy(s);
    if (failed) fprintf(stderr, "stream allocation failure/retry contract failed\n");
    else puts("stream allocation failure/retry: PASS");
    return failed;
}
