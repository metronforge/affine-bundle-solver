/* Public C interfaces only. All nonzero input data in these cases are normal. */
#include <math.h>
#include <stdio.h>
#include <affine_bundle/candidate_check.h>
#include <affine_bundle/solve.h>

static void report(const char *label, const double *a, const double *b,
                   const double *reference, int m, int n,
                   const BSOperationalPolicyV1 *policy) {
    BSOperationalResultV1 result;
    bs_init_operational_result(&result);
    int rc = bsolve_router_policy_api(a,b,reference,m,n,1,2,2,777,0,
                                       policy,&result);
    printf("%s rc=%d status=%d certainty=%d rank=[%.0f,%.0f] "
           "relx=%g BERR=%.17g guard_checks=%llu exact=%d\n",
           label,rc,result.operational_status,result.operational_certainty,
           result.router_meta[3],result.router_meta[4],result.router_meta[6],
           result.router_meta[10],result.formation_guard_counters[0],
           result.exact_source_status);
}

int main(void) {
    BSOperationalPolicyV1 p;
    bs_default_operational_policy(&p);
    double x[]={1}, zero[]={0,0,0}, unit[]={1,1}, b[]={1,1+0x1p-32};
    report("quality unscaled",unit,b,x,2,1,&p);
    for (int i=0;i<2;++i) { unit[i]*=0x1p-1015; b[i]*=0x1p-1015; }
    report("quality scaled",unit,b,x,2,1,&p);
    BSCandidateCheckResultV1 ck;
    bs_init_candidate_check_result(&ck);
    int rc=abs_check_candidate(unit,b,x,2,1,&p,&ck);
    printf("strict candidate x=1 rc=%d verdict=%d mixed_up=%.17g "
           "exact=1/(2^33+1)\n",rc,ck.verdict,ck.mixed_backward_error_up);
    BSSolveResultV1 sr;
    bs_init_solve_result(&sr);
    double candidate=0;
    rc=bsolve(unit,b,2,1,&p,&candidate,&sr);
    bs_init_candidate_check_result(&ck);
    int cr=abs_check_candidate(unit,b,&candidate,2,1,&p,&ck);
    printf("bsolve rc=%d x=%.17g status=%d router_BERR=%.17g "
           "candidate_check_rc=%d verdict=%d mixed_up=%.17g\n",
           rc,candidate,sr.operational_status,sr.router_meta[10],cr,ck.verdict,
           ck.mixed_backward_error_up);
    double a[]={1,0,0x1.2p0,0x1.2p-30};
    report("direction unscaled",a,zero,zero,2,2,&p);
    a[2]*=0x1p-537; a[3]*=0x1p-537;
    report("direction scaled",a,zero,zero,2,2,&p);
    double same[]={1,0,1,0}, rhs[]={0,1}, shift[]={0,-0x1p40};
    report("null translation e=40",same,rhs,shift,2,2,&p);
    double a1[]={3,6,9,7,14,21,11,22,33};
    report("rank one default",a1,zero,zero,3,3,&p);
    p.dependence_threshold=1e-34; p.growth_threshold=0x1p-60;
    report("rank one custom",a1,zero,zero,3,3,&p);
    p.dependence_threshold=0.5; p.growth_threshold=1;
    double ident[]={1,0,0,1};
    report("exact growth equality",ident,zero,zero,2,2,&p);
    return 0;
}
