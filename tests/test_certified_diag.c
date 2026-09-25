/* Native contract and lifecycle test. No Python host is involved in LSan. */
#include <affine_bundle/certified_api.h>
#include <affine_bundle/router.h>
#include <math.h>
#include <limits.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

_Static_assert(ABS_OUT_LEN == 11, "router layout changed");
_Static_assert(BS_CERTIFIED_DIAG_GREY_CAP == 64, "grey capacity changed");
_Static_assert(offsetof(BSCertifiedResult, eta_x) == 24, "legacy ABI changed");
_Static_assert(sizeof(BSCertifiedResult) == 112, "legacy ABI changed");
_Static_assert(offsetof(BSCertifiedResult, inconsistent_verifier_code) == 108,
               "legacy ABI tail changed");
_Static_assert(offsetof(BSCombinedCertifiedResult, router_meta) == sizeof(BSCertifiedResult),
               "combined result prefix changed");
_Static_assert(offsetof(BSCombinedCertifiedResult, grey_rows) == 208,
               "grey row offset changed");
_Static_assert(offsetof(BSCombinedCertifiedResult, formation_guard_counters) == 488,
               "guard counter offset changed");
_Static_assert(sizeof(BSCombinedCertifiedResult) == 512, "combined ABI size changed");
_Static_assert(sizeof(((BSCombinedCertifiedResult *)0)->router_meta) / sizeof(double) == ABS_OUT_LEN,
               "meta capacity changed");
_Static_assert(sizeof(((BSCombinedCertifiedResult *)0)->grey_rows) / sizeof(int) == 64,
               "grey capacity changed");

static int same(double a, double b)
{
    if (isnan(a) || isnan(b)) return isnan(a) && isnan(b);
    return a == b;
}

#define EQI(field) if (a->field != b->field) { fprintf(stderr, "certified mismatch: %s\n", #field); return 0; }
#define EQD(field) if (!same(a->field, b->field)) { fprintf(stderr, "certified mismatch: %s\n", #field); return 0; }
static int same_certified(const BSCertifiedResult *a, const BSCertifiedResult *b)
{
    EQI(fast_status); EQI(fast_certainty); EQI(rank_estimate); EQI(rank_lo); EQI(rank_hi);
    EQD(eta_x); EQI(certified_status); EQD(eta_status); EQI(generator_code);
    EQI(verifier_code); EQI(accepted_status_mask); EQD(eta_unique);
    EQD(eta_infinite); EQD(eta_inconsistent);
    EQI(unique_generator_code); EQI(unique_verifier_code);
    EQI(infinite_generator_code); EQI(infinite_verifier_code);
    EQI(inconsistent_generator_code); EQI(inconsistent_verifier_code);
    return 1;
}

static int check_case(const char *name, const double *A, const double *b,
                      const double *xt, int m, int n, int expected_status)
{
    BSCombinedCertifiedResult combined, supplied, repeat;
    BSCertifiedResult legacy;
    double meta[ABS_OUT_LEN];
    int grey[BS_CERTIFIED_DIAG_GREY_CAP], count, interval[2];
    unsigned long long before[3], after[3];
    int i;
    if (bsolve_certified_api(A,b,NULL,m,n,1,2,2,17,0,&legacy) ||
        bsolve_certified_diag_api(A,b,NULL,m,n,1,2,2,17,0,&combined) ||
        bsolve_certified_diag_api(A,b,NULL,m,n,1,2,2,17,0,&repeat) ||
        bsolve_certified_diag_api(A,b,xt,m,n,1,2,2,17,0,&supplied)) {
        fprintf(stderr, "%s: API return failure\n", name); return 0;
    }
    if (!same_certified(&legacy,&combined.certified) ||
        !same_certified(&combined.certified,&repeat.certified) ||
        !same_certified(&combined.certified,&supplied.certified)) return 0;
    if (combined.certified.fast_status != expected_status ||
        (int)combined.router_meta[ABS_OUT_STATUS] != expected_status) {
        fprintf(stderr, "%s: expected status %d, got %d\n", name, expected_status,
                combined.certified.fast_status); return 0;
    }
    for (i=0;i<ABS_OUT_LEN;i++) {
        if (i == ABS_OUT_SECONDS || i == ABS_OUT_RELX) continue;
        if (!same(combined.router_meta[i],supplied.router_meta[i]) ||
            !same(combined.router_meta[i],repeat.router_meta[i])) {
            fprintf(stderr, "%s: NULL-xt/repeat meta mismatch at %d\n", name, i); return 0;
        }
    }
    if (combined.certified.fast_status == ABS_STATUS_UNIQUE && xt &&
        (!isnan(combined.router_meta[ABS_OUT_RELX]) ||
         !isfinite(supplied.router_meta[ABS_OUT_RELX]))) {
        fprintf(stderr, "%s: optional xt did not isolate RELX\n", name); return 0;
    }
    if (combined.grey_distinct_count != supplied.grey_distinct_count ||
        combined.grey_total_events != supplied.grey_total_events ||
        combined.grey_distinct_count != repeat.grey_distinct_count ||
        combined.grey_total_events != repeat.grey_total_events ||
        combined.grey_distinct_count < 0 ||
        combined.grey_distinct_count > BS_CERTIFIED_DIAG_GREY_CAP ||
        combined.grey_total_events < combined.grey_distinct_count ||
        memcmp(combined.grey_rows,supplied.grey_rows,sizeof(combined.grey_rows)) ||
        memcmp(combined.grey_rows,repeat.grey_rows,sizeof(combined.grey_rows)) ||
        !same(combined.last_orth_eta,supplied.last_orth_eta) ||
        !same(combined.last_orth_eta,repeat.last_orth_eta) ||
        memcmp(combined.core_rank_interval,supplied.core_rank_interval,sizeof(interval)) ||
        combined.core_qr_rank != supplied.core_qr_rank ||
        memcmp(combined.formation_guard_counters,supplied.formation_guard_counters,sizeof(after))) {
        fprintf(stderr, "%s: NULL-xt/repeat diagnostic mismatch\n", name); return 0;
    }
    if (combined.grey_distinct_count == 0) {
        for(i=0;i<BS_CERTIFIED_DIAG_GREY_CAP;i++) if(combined.grey_rows[i] != 0) {
            fprintf(stderr, "%s: unused grey row not initialized\n", name); return 0;
        }
    }
    bsolve_fg_counters_api(before);
    count=bsolve_router_diag_api(A,b,NULL,m,n,1,2,2,17,0,meta,grey,BS_CERTIFIED_DIAG_GREY_CAP);
    bsolve_fg_counters_api(after);
    if (count != combined.grey_distinct_count ||
        bsolve_last_grey_total_api() != combined.grey_total_events ||
        !same(bsolve_last_orth_eta_api(),combined.last_orth_eta) ||
        bsolve_last_core_qr_rank_api() != combined.core_qr_rank) {
        fprintf(stderr, "%s: router diagnostic mismatch\n", name); return 0;
    }
    bsolve_last_core_rank_interval_api(interval);
    if (memcmp(interval,combined.core_rank_interval,sizeof(interval)) ||
        memcmp(grey,combined.grey_rows,(size_t)count*sizeof(int))) return 0;
    for(i=0;i<3;i++) if (after[i]-before[i] != combined.formation_guard_counters[i]) return 0;
    for(i=0;i<ABS_OUT_LEN;i++) if (i!=ABS_OUT_SECONDS && !same(meta[i],combined.router_meta[i])) {
        fprintf(stderr, "%s: router meta mismatch at %d\n", name, i); return 0;
    }
    printf("%s: PASS status=%d grey=%d/%d\n",name,combined.certified.fast_status,
           combined.grey_distinct_count,combined.grey_total_events);
    return 1;
}

static int invalid_cases(void)
{
#define EXPECT_INVALID(label, call) do { int rc_=(call); if(rc_!=1) { \
    fprintf(stderr,"invalid %s returned %d, expected 1\n",label,rc_); return 0; \
} } while(0)
    const double A[]={1}, b[]={1};
    BSCombinedCertifiedResult result;
    EXPECT_INVALID("null out",bsolve_certified_diag_api(A,b,NULL,1,1,1,2,2,0,0,NULL));
    memset(&result,0xA5,sizeof(result));
    EXPECT_INVALID("zero m",bsolve_certified_diag_api(A,b,NULL,0,1,1,2,2,0,0,&result));
    { const unsigned char *bytes=(const unsigned char *)&result;
      for(size_t i=0;i<sizeof(result);i++) if(bytes[i]) return 0; }
    EXPECT_INVALID("null A",bsolve_certified_diag_api(NULL,b,NULL,1,1,1,2,2,0,0,&result));
    EXPECT_INVALID("null b",bsolve_certified_diag_api(A,NULL,NULL,1,1,1,2,2,0,0,&result));
    EXPECT_INVALID("zero n",bsolve_certified_diag_api(A,b,NULL,1,0,1,2,2,0,0,&result));
    EXPECT_INVALID("matrix overflow",bsolve_certified_diag_api(A,b,NULL,INT_MAX,INT_MAX,1,2,2,0,0,&result));
    EXPECT_INVALID("zero sp",bsolve_certified_diag_api(A,b,NULL,1,1,0,2,2,0,0,&result));
    { const double zeros[3]={0,0,0};
      /* Formation counts are signed int: three rows times INT_MAX sketches
         cannot be represented and must be rejected before router execution. */
      EXPECT_INVALID("sketch count overflow",
          bsolve_certified_diag_api(zeros,zeros,NULL,3,1,INT_MAX,2,2,0,0,&result)); }
    EXPECT_INVALID("alpha overflow",bsolve_certified_diag_api(A,b,NULL,1,1,1,2,INT_MAX,0,0,&result));
    EXPECT_INVALID("n overflow",bsolve_certified_diag_api(A,b,NULL,1,INT_MAX,1,2,2,0,0,&result));
    { const double nan_A[]={NAN};
      EXPECT_INVALID("nonfinite A",bsolve_certified_diag_api(nan_A,b,NULL,1,1,1,2,2,0,0,&result)); }
    { const unsigned char *bytes=(const unsigned char *)&result;
      for(size_t i=0;i<sizeof(result);i++) if(bytes[i]) return 0; }
    return 1;
#undef EXPECT_INVALID
}

int main(void)
{
    double thin_48_A[48]={1}, thin_48_x[48]={1};
    double thin_96_A[96]={1}, thin_96_x[96]={1};
    const double thin_b[]={1};
    const double unique_A[]={1,0,0,1}, unique_b[]={2,3}, unique_x[]={2,3};
    const double wide_A[]={1,0,0,0,1,0}, wide_b[]={2,3}, wide_x[]={2,3,0};
    const double tall_A[]={1,0,0,1,1,1}, tall_b[]={2,3,5}, tall_x[]={2,3};
    const double dep_A[]={1,0,2,0,3,0}, dep_b[]={2,4,6}, bad_b[]={2,4,7};
    const double near_A[]={1,0,1,1e-11}, near_b[]={1,1};
    const double zero_A[]={0,0,0,0}, zero_b[]={0,0}, nonzero_b[]={0,1};
    return !(invalid_cases() &&
        check_case("unique-square",unique_A,unique_b,unique_x,2,2,ABS_STATUS_UNIQUE) &&
        check_case("unique-tall",tall_A,tall_b,tall_x,3,2,ABS_STATUS_UNIQUE) &&
        check_case("infinite-wide",wide_A,wide_b,wide_x,2,3,ABS_STATUS_INFINITE) &&
        check_case("infinite-tall",dep_A,dep_b,unique_x,3,2,ABS_STATUS_INFINITE) &&
        check_case("inconsistent",dep_A,bad_b,unique_x,3,2,ABS_STATUS_INCONSISTENT) &&
        check_case("near-threshold",near_A,near_b,unique_x,2,2,ABS_STATUS_UNDECIDABLE) &&
        check_case("zero-compatible",zero_A,zero_b,unique_x,2,2,ABS_STATUS_INFINITE) &&
        check_case("zero-incompatible",zero_A,nonzero_b,unique_x,2,2,ABS_STATUS_INCONSISTENT) &&
        check_case("thin-wide-48",thin_48_A,thin_b,thin_48_x,1,48,ABS_STATUS_INFINITE) &&
        check_case("thin-wide-96",thin_96_A,thin_b,thin_96_x,1,96,ABS_STATUS_INFINITE));
}
