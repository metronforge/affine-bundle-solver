#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <affine_bundle/certified_api.h>

typedef struct { _Atomic unsigned long long ns, count; } counter;
static counter api_c, router_c, unique_gen_c, infinite_gen_c, inconsistent_gen_c, verify_c;
static counter dgelsy_c, dgeqp3_c, dgesvd_c, dgesdd_c, dormqr_c, dgemm_c, dgemv_c;
static counter lapack_top_c, router_lapack_c, generator_lapack_c, verify_lapack_c, other_lapack_c;
static _Thread_local int lapack_depth;
enum trace_phase { PHASE_OTHER, PHASE_ROUTER, PHASE_GENERATOR, PHASE_VERIFY };
static _Thread_local enum trace_phase current_phase;

static unsigned long long tick(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC_RAW, &t);
    return (unsigned long long)t.tv_sec * 1000000000ULL + (unsigned long long)t.tv_nsec;
}
static void finish(counter *c, unsigned long long start) {
    atomic_fetch_add(&c->ns, tick() - start); atomic_fetch_add(&c->count, 1);
}
static void *solver_handle(void) {
    static void *handle; if (!handle) handle=dlopen(getenv("TASK5_SOLVER_LIB"),RTLD_LAZY|RTLD_NOLOAD); return handle;
}
static void *sibling_handle(const char *leaf) {
    const char *solver=getenv("TASK5_SOLVER_LIB"); static char path[4096];
    if(!solver)return NULL; snprintf(path,sizeof(path),"%s",solver); char *slash=strrchr(path,'/');
    if(!slash)return NULL; snprintf(slash+1,sizeof(path)-(size_t)(slash+1-path),"%s",leaf);
    return dlopen(path,RTLD_LAZY|RTLD_NOLOAD);
}
static void *router_handle(void) { static void *h; if(!h)h=sibling_handle("libaffine_bundle_solver.so"); return h; }
static void *status_handle(void) { static void *h; if(!h)h=sibling_handle("libstatus_verifier.so"); return h; }
static void *blas_handle(void) { static void *h; if(!h)h=dlopen("libopenblas.so.0",RTLD_LAZY|RTLD_NOLOAD); return h; }
#define RESOLVE_FROM(name, type, handle_expr) static type real; if (!real) real = (type)dlsym((handle_expr), #name)

int bsolve_certified_diag_api(const double *A,const double *b,const double *xt,int m,int n,int sp,int qv,int alpha,
                              unsigned long long seed,int full,BSCombinedCertifiedResult *out) {
    typedef int (*fn)(const double*,const double*,const double*,int,int,int,int,int,unsigned long long,int,BSCombinedCertifiedResult*);
    RESOLVE_FROM(bsolve_certified_diag_api, fn, solver_handle()); unsigned long long t=tick(); int rc=real(A,b,xt,m,n,sp,qv,alpha,seed,full,out); finish(&api_c,t); return rc;
}

void abs_router_snapshot_internal(const double *A,const double *b,const double *xt,int m,int n,int sp,int qv,int alpha,
                                  unsigned long long seed,int full,void *out) {
    typedef void (*fn)(const double*,const double*,const double*,int,int,int,int,int,unsigned long long,int,void*);
    RESOLVE_FROM(abs_router_snapshot_internal, fn, router_handle()); enum trace_phase old=current_phase;current_phase=PHASE_ROUTER;
    unsigned long long t=tick(); real(A,b,xt,m,n,sp,qv,alpha,seed,full,out); finish(&router_c,t);current_phase=old;
}

int bs_generate_unique_witness(const double *A,const double *b,int m,int n,BSUniqueWitness *w) {
    typedef int (*fn)(const double*,const double*,int,int,BSUniqueWitness*);
    RESOLVE_FROM(bs_generate_unique_witness, fn, solver_handle()); enum trace_phase old=current_phase;current_phase=PHASE_GENERATOR;
    unsigned long long t=tick(); int rc=real(A,b,m,n,w); finish(&unique_gen_c,t);current_phase=old; return rc;
}
int bs_generate_infinite_witness(const double *A,const double *b,int m,int n,BSInfiniteWitness *w) {
    typedef int (*fn)(const double*,const double*,int,int,BSInfiniteWitness*);
    RESOLVE_FROM(bs_generate_infinite_witness, fn, solver_handle()); enum trace_phase old=current_phase;current_phase=PHASE_GENERATOR;
    unsigned long long t=tick(); int rc=real(A,b,m,n,w); finish(&infinite_gen_c,t);current_phase=old; return rc;
}
int bs_generate_inconsistent_witness(const double *A,const double *b,int m,int n,BSInconsistentWitness *w) {
    typedef int (*fn)(const double*,const double*,int,int,BSInconsistentWitness*);
    RESOLVE_FROM(bs_generate_inconsistent_witness, fn, solver_handle()); enum trace_phase old=current_phase;current_phase=PHASE_GENERATOR;
    unsigned long long t=tick(); int rc=real(A,b,m,n,w); finish(&inconsistent_gen_c,t);current_phase=old; return rc;
}

int bs_verify_unique(const double *A,const double *b,int m,int n,const BSUniqueWitness *w,double *eta) {
    typedef int (*fn)(const double*,const double*,int,int,const BSUniqueWitness*,double*);
    RESOLVE_FROM(bs_verify_unique, fn, status_handle()); enum trace_phase old=current_phase;current_phase=PHASE_VERIFY;
    unsigned long long t=tick(); int rc=real(A,b,m,n,w,eta); finish(&verify_c,t);current_phase=old; return rc;
}
int bs_verify_infinite(const double *A,const double *b,int m,int n,const BSInfiniteWitness *w,double *eta) {
    typedef int (*fn)(const double*,const double*,int,int,const BSInfiniteWitness*,double*);
    RESOLVE_FROM(bs_verify_infinite, fn, status_handle()); enum trace_phase old=current_phase;current_phase=PHASE_VERIFY;
    unsigned long long t=tick(); int rc=real(A,b,m,n,w,eta); finish(&verify_c,t);current_phase=old; return rc;
}
int bs_verify_inconsistent(const double *A,const double *b,int m,int n,const BSInconsistentWitness *w,
                           double *lo,double *hi,double *eta) {
    typedef int (*fn)(const double*,const double*,int,int,const BSInconsistentWitness*,double*,double*,double*);
    RESOLVE_FROM(bs_verify_inconsistent, fn, status_handle()); enum trace_phase old=current_phase;current_phase=PHASE_VERIFY;
    unsigned long long t=tick(); int rc=real(A,b,m,n,w,lo,hi,eta); finish(&verify_c,t);current_phase=old; return rc;
}

#define LAPACK_WRAP(name, counter_name, decl, call) \
void name decl { typedef void (*fn) decl; RESOLVE_FROM(name, fn, blas_handle()); int outer=(lapack_depth++==0); \
    unsigned long long t=tick(); real call; unsigned long long elapsed=tick()-t; --lapack_depth; \
    atomic_fetch_add(&counter_name.ns,elapsed); atomic_fetch_add(&counter_name.count,1); \
    if(outer){counter *phase_counter=current_phase==PHASE_ROUTER?&router_lapack_c:current_phase==PHASE_GENERATOR?&generator_lapack_c:current_phase==PHASE_VERIFY?&verify_lapack_c:&other_lapack_c; \
      atomic_fetch_add(&lapack_top_c.ns,elapsed);atomic_fetch_add(&lapack_top_c.count,1); \
      atomic_fetch_add(&phase_counter->ns,elapsed);atomic_fetch_add(&phase_counter->count,1);} }

LAPACK_WRAP(dgelsy_, dgelsy_c, (int*a,int*b,int*c,double*d,int*e,double*f,int*g,int*h,double*i,int*j,double*k,int*l,int*m),
            (a,b,c,d,e,f,g,h,i,j,k,l,m))
LAPACK_WRAP(dgeqp3_, dgeqp3_c, (int*a,int*b,double*c,int*d,int*e,double*f,double*g,int*h,int*i), (a,b,c,d,e,f,g,h,i))
LAPACK_WRAP(dgesvd_, dgesvd_c, (char*a,char*b,int*c,int*d,double*e,int*f,double*g,double*h,int*i,double*j,int*k,double*l,int*m,int*n),
            (a,b,c,d,e,f,g,h,i,j,k,l,m,n))
LAPACK_WRAP(dgesdd_, dgesdd_c, (char*a,int*b,int*c,double*d,int*e,double*f,double*g,int*h,double*i,int*j,double*k,int*l,int*m,int*n,int*o),
            (a,b,c,d,e,f,g,h,i,j,k,l,m,n,o))
LAPACK_WRAP(dormqr_, dormqr_c, (char*a,char*b,int*c,int*d,int*e,double*f,int*g,double*h,double*i,int*j,double*k,int*l,int*m),
            (a,b,c,d,e,f,g,h,i,j,k,l,m))
LAPACK_WRAP(dgemm_, dgemm_c, (char*a,char*b,int*c,int*d,int*e,double*f,double*g,int*h,double*i,int*j,double*k,double*l,int*m),
            (a,b,c,d,e,f,g,h,i,j,k,l,m))
LAPACK_WRAP(dgemv_, dgemv_c, (char*a,int*b,int*c,double*d,double*e,int*f,double*g,int*h,double*i,double*j,int*k),
            (a,b,c,d,e,f,g,h,i,j,k))

static unsigned long long value(counter *c) { return atomic_load(&c->ns); }
static unsigned long long calls(counter *c) { return atomic_load(&c->count); }
__attribute__((destructor)) static void report(void) {
    unsigned long long lapack_ns=value(&lapack_top_c),lapack_count=calls(&lapack_top_c);
    fprintf(stderr,"ABS_TRACE api_ns=%llu api_count=%llu router_ns=%llu router_count=%llu unique_gen_ns=%llu unique_gen_count=%llu infinite_gen_ns=%llu infinite_gen_count=%llu inconsistent_gen_ns=%llu inconsistent_gen_count=%llu verify_ns=%llu verify_count=%llu lapack_ns=%llu lapack_count=%llu router_lapack_ns=%llu generator_lapack_ns=%llu verify_lapack_ns=%llu other_lapack_ns=%llu dgelsy_ns=%llu dgelsy_count=%llu dgeqp3_ns=%llu dgeqp3_count=%llu dgesvd_ns=%llu dgesvd_count=%llu dgesdd_ns=%llu dgesdd_count=%llu dormqr_ns=%llu dormqr_count=%llu dgemm_ns=%llu dgemm_count=%llu dgemv_ns=%llu dgemv_count=%llu\n",
      value(&api_c),calls(&api_c),value(&router_c),calls(&router_c),value(&unique_gen_c),calls(&unique_gen_c),
      value(&infinite_gen_c),calls(&infinite_gen_c),value(&inconsistent_gen_c),calls(&inconsistent_gen_c),
      value(&verify_c),calls(&verify_c),lapack_ns,lapack_count,value(&router_lapack_c),value(&generator_lapack_c),
      value(&verify_lapack_c),value(&other_lapack_c),value(&dgelsy_c),calls(&dgelsy_c),
      value(&dgeqp3_c),calls(&dgeqp3_c),value(&dgesvd_c),calls(&dgesvd_c),value(&dgesdd_c),calls(&dgesdd_c),
      value(&dormqr_c),calls(&dormqr_c),value(&dgemm_c),calls(&dgemm_c),value(&dgemv_c),calls(&dgemv_c));
}
