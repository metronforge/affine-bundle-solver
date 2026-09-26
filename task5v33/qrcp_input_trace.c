#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned long long target_calls, query_calls, execute_calls;
static unsigned long long unique_hashes[16];
static int unique_count, pivot_seed_zero = 1;

static uint64_t hash_bytes(const void *data, size_t size)
{
    const unsigned char *p = (const unsigned char *)data;
    uint64_t h = UINT64_C(1469598103934665603);
    size_t i;
    for (i = 0; i < size; ++i) { h ^= p[i]; h *= UINT64_C(1099511628211); }
    return h;
}

static void *blas_handle(void)
{
    static void *handle;
    if (!handle) handle = dlopen("libopenblas.so.0",RTLD_LAZY|RTLD_NOLOAD);
    return handle;
}

void dgeqp3_(int *m,int *n,double *a,int *lda,int *jpvt,double *tau,
             double *work,int *lwork,int *info)
{
    typedef void (*fn)(int*,int*,double*,int*,int*,double*,double*,int*,int*);
    static fn real;
    int i, seen = 0;
    uint64_t h;
    if (!real) real = (fn)dlsym(blas_handle(),"dgeqp3_");
    if (*m == 256 && *n == 128 && *lda == 256) {
        ++target_calls;
        if (*lwork == -1) ++query_calls; else ++execute_calls;
        for (i = 0; i < *n; ++i) if (jpvt[i] != 0) pivot_seed_zero = 0;
        h = hash_bytes(a,(size_t)(*lda)*(size_t)(*n)*sizeof(*a));
        for (i = 0; i < unique_count; ++i) if (unique_hashes[i] == h) seen = 1;
        if (!seen && unique_count < 16) unique_hashes[unique_count++] = h;
    }
    real(m,n,a,lda,jpvt,tau,work,lwork,info);
}

__attribute__((destructor)) static void report(void)
{
    int i;
    fprintf(stderr,"QRCP_INPUT_TRACE m=256 n=128 lda=256 storage=column-major calls=%llu query=%llu execute=%llu unique_hashes=%d jpvt_seed_zero=%d hashes=",
            target_calls,query_calls,execute_calls,unique_count,pivot_seed_zero);
    for (i = 0; i < unique_count; ++i)
        fprintf(stderr,"%s%016llx",i?",":"",unique_hashes[i]);
    fputc('\n',stderr);
}
