/* Native leak-sensitive counterpart of the intentional ENOMEM stream fixture. */
#define _POSIX_C_SOURCE 200809L
#include <affine_bundle/stream.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <sys/resource.h>
#include <unistd.h>

static int virtual_bytes(rlim_t *bytes)
{
    unsigned long long pages;
    long page_size = sysconf(_SC_PAGESIZE);
    FILE *f = fopen("/proc/self/statm", "r");
    int ok = f && page_size > 0 && fscanf(f, "%llu", &pages) == 1;
    if (f) fclose(f);
    if (!ok || pages > UINT64_MAX / (unsigned long long)page_size) return 0;
    *bytes = (rlim_t)(pages * (unsigned long long)page_size);
    return 1;
}

int main(void)
{
    const int n = 250000;
    double *row = calloc((size_t)n, sizeof *row);
    ABSStream *stream = NULL;
    struct rlimit original, limited;
    rlim_t used;
    long long seen = -1, deferred = -1;
    double status[ABS_OUT_LEN];
    int rc, first_rc, result = 1;

    if (!row) goto done;
    row[0] = 1.0;
    stream = abs_stream_create(n);
    if (!stream || getrlimit(RLIMIT_AS, &original) || !virtual_bytes(&used)) goto done;
    if (used > RLIM_INFINITY - 1024 * 1024) goto done;
    limited = original;
    limited.rlim_cur = used + 1024 * 1024;
    if (limited.rlim_max != RLIM_INFINITY && limited.rlim_cur >= limited.rlim_max)
        goto done;
    if (setrlimit(RLIMIT_AS, &limited)) goto done;
    rc = abs_stream_insert(stream, row, 1.0);
    first_rc = rc;
    if (setrlimit(RLIMIT_AS, &original)) {
        fprintf(stderr, "could not restore RLIMIT_AS\n");
        goto done;
    }
    abs_stream_counts(stream, &seen, &deferred);
    abs_stream_status(stream, status);
    if (rc != ABS_INSERT_ENOMEM || seen != 0 || deferred != 0 ||
        status[ABS_OUT_RANK] != 0.0) {
        fprintf(stderr, "ENOMEM atomicity failed: rc=%d seen=%lld deferred=%lld rank=%g\n",
                rc, seen, deferred, status[ABS_OUT_RANK]);
        goto done;
    }
    rc = abs_stream_insert(stream, row, 1.0);
    abs_stream_counts(stream, &seen, &deferred);
    abs_stream_status(stream, status);
    if (rc != ABS_INSERT_GROW || seen != 1 || deferred != 0 ||
        status[ABS_OUT_RANK] != 1.0) {
        fprintf(stderr, "retry failed: rc=%d seen=%lld deferred=%lld rank=%g\n",
                rc, seen, deferred, status[ABS_OUT_RANK]);
        goto done;
    }
    printf("native stream: initial rc=%d (ABS_INSERT_ENOMEM), seen=0, "
           "deferred=0, rank=0; identical retry rc=%d (ABS_INSERT_GROW), "
           "seen=%lld, deferred=%lld, rank=%.0f: PASS\n",
           first_rc, rc, seen, deferred, status[ABS_OUT_RANK]);
    result = 0;
done:
    abs_stream_destroy(stream);
    free(row);
    return result;
}
