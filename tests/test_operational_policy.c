#include <affine_bundle/certified_api.h>
#include <affine_bundle/operational_policy.h>
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>

static const double A[]={1,0,0,1}, b[]={1,2};
static int run(const BSOperationalPolicyV1 *p, BSCombinedSemanticResultV1 *r) {
    return bsolve_certified_policy_api(A,b,NULL,2,2,1,2,2,17,0,p,r);
}
static void *worker(void *arg) {
    BSOperationalPolicyV1 p; bs_default_operational_policy(&p);
    if(arg)p.compatibility_tolerance=1e-16;
    for(int i=0;i<20;i++) {
        BSCombinedSemanticResultV1 r; bs_init_combined_semantic_result(&r);
        assert(run(&p,&r)==0);
        assert(r.operational.policy_used.compatibility_tolerance==p.compatibility_tolerance);
        assert(r.operational.exact_source_status==BS_EXACT_SOURCE_UNKNOWN);
        assert(r.operational.exact_source_verification==BS_EXACT_VERIFY_NOT_VERIFIED);
        const double dependent[]={1,0,1,0}, shifted[]={1,1+1e-12};
        BSOperationalResultV1 op;bs_init_operational_result(&op);
        assert(!bsolve_router_policy_api(dependent,shifted,NULL,2,2,1,2,2,17,0,&p,&op));
        assert(op.operational_status==(arg?ABS_STATUS_INCONSISTENT:ABS_STATUS_INFINITE));
        assert(op.router_meta[2]==1);
    }
    return NULL;
}
int main(void) {
    BSOperationalPolicyV1 p={0}; bs_default_operational_policy(&p);
    assert(p.struct_size==sizeof(p));
    assert(p.dependence_threshold==1e-13 && p.growth_threshold==1e-9);
    assert(p.compatibility_tolerance==2e-10 && p.quality_threshold==1e-14);
    BSCombinedSemanticResultV1 r; bs_init_combined_semantic_result(&r);
    assert(r.struct_size==sizeof(r)); assert(run(&p,&r)==0);
    BSCombinedCertifiedResult old;
    assert(bsolve_certified_diag_api(A,b,NULL,2,2,1,2,2,17,0,&old)==0);
    for(int i=0;i<ABS_OUT_LEN;i++)if(i!=7)
        assert(r.operational.router_meta[i]==old.router_meta[i] ||
               (isnan(r.operational.router_meta[i]) && isnan(old.router_meta[i])));
    assert(!memcmp(&r.certificate_profile,&old.certified,sizeof(old.certified)));
    assert(r.nearby_status_mask==old.certified.accepted_status_mask);
    struct { BSOperationalPolicyV1 p; unsigned char tail[24]; } future;
    memset(&future,0xA5,sizeof(future)); future.p=p;future.p.struct_size=sizeof(future);
    struct { BSCombinedSemanticResultV1 r; unsigned char tail[24]; } output;
    memset(&output,0x5A,sizeof(output));bs_init_combined_semantic_result(&output.r);
    output.r.struct_size=sizeof(output);assert(run(&future.p,&output.r)==0);
    assert(output.r.struct_size==sizeof(output));
    for(int i=0;i<24;i++)assert(output.tail[i]==0x5A && future.tail[i]==0xA5);
    p.struct_size=sizeof(size_t); assert(run(&p,&r)==BS_POLICY_INVALID_ARGUMENT);
    assert(r.nearby_status_mask==0 && r.operational.operational_status==ABS_STATUS_FAIL);
    bs_default_operational_policy(&p);
    r.struct_size=sizeof(size_t);assert(run(&p,&r)==BS_POLICY_INVALID_ARGUMENT);
    assert(r.struct_size==sizeof(size_t));bs_init_combined_semantic_result(&r);
    double invalid[]={NAN,INFINITY,-1,0,2};
    for(int j=0;j<4;j++)for(int i=0;i<5;i++) {
        bs_default_operational_policy(&p);
        double *fields[]={&p.dependence_threshold,&p.growth_threshold,&p.compatibility_tolerance,&p.quality_threshold};
        *fields[j]=invalid[i];assert(run(&p,&r)==BS_POLICY_INVALID_ARGUMENT);
        assert(r.nearby_status_mask==0 && r.operational.exact_source_status==BS_EXACT_SOURCE_UNKNOWN);
    }
    bs_default_operational_policy(&p);p.dependence_threshold=p.growth_threshold;
    assert(run(&p,&r)==BS_POLICY_INVALID_ARGUMENT);
    assert(run(NULL,&r)==BS_POLICY_INVALID_ARGUMENT);
    BSOperationalResultV1 op;bs_init_operational_result(&op);
    bs_default_operational_policy(&p);
    op.struct_size=sizeof(size_t);
    assert(bsolve_router_policy_api(A,b,NULL,2,2,1,2,2,17,0,&p,&op)==1);
    assert(op.struct_size==sizeof(size_t));bs_init_operational_result(&op);
    struct { BSOperationalResultV1 r; unsigned char tail[24]; } router_future;
    memset(&router_future,0x3C,sizeof(router_future));
    bs_init_operational_result(&router_future.r);
    assert(router_future.r.struct_size==sizeof(BSOperationalResultV1));
    router_future.r.struct_size=sizeof(router_future);
    assert(!bsolve_router_policy_api(A,b,NULL,2,2,1,2,2,17,0,&future.p,&router_future.r));
    assert(router_future.r.struct_size==sizeof(router_future));
    for(int i=0;i<24;i++)assert(router_future.tail[i]==0x3C);
    double near[]={1,0,1,1e-8},rhs[]={1,1};
    p.growth_threshold=1e-7;
    assert(!bsolve_router_policy_api(near,rhs,NULL,2,2,1,2,2,17,0,&p,&op));
    assert(op.operational_status==ABS_STATUS_UNDECIDABLE);
    assert(op.router_meta[3]==1 && op.router_meta[4]==2);
    p.dependence_threshold=1e-7;p.growth_threshold=1e-6;
    assert(!bsolve_router_policy_api(near,rhs,NULL,2,2,1,2,2,17,0,&p,&op));
    assert(op.router_meta[3]==1 && op.router_meta[4]==1);
    double tall[]={1,0,0,1,1,1},tb[]={1,2,3+1e-12};
    bs_default_operational_policy(&p);p.quality_threshold=1e-10;
    assert(!bsolve_router_policy_api(tall,tb,NULL,3,2,1,2,2,17,0,&p,&op));
    assert(op.operational_status==ABS_STATUS_UNIQUE);
    p.quality_threshold=1e-16;
    assert(!bsolve_router_policy_api(tall,tb,NULL,3,2,1,2,2,17,0,&p,&op));
    assert(op.operational_status==ABS_STATUS_UNDECIDABLE);
    /* Overflow in a custom quality computation must never pass as zero error. */
    double extreme[]={1e200,1e200,1e-200,0},eb[]={0,1};
    double reversed[]={1e-200,0,1e200,1e200},rb[]={1,0};
    bs_default_operational_policy(&p);p.quality_threshold=1e-10;
    assert(!bsolve_router_policy_api(extreme,eb,NULL,2,2,1,2,2,17,0,&p,&op));
    assert(op.operational_status==ABS_STATUS_UNDECIDABLE);
    assert(!bsolve_router_policy_api(reversed,rb,NULL,2,2,1,2,2,17,0,&p,&op));
    assert(op.operational_status==ABS_STATUS_UNDECIDABLE);
    pthread_t t[2]; assert(!pthread_create(&t[0],NULL,worker,NULL));
    assert(!pthread_create(&t[1],NULL,worker,(void*)1));
    pthread_join(t[0],NULL);pthread_join(t[1],NULL);
    BSCombinedCertifiedResult after;
    assert(!bsolve_certified_diag_api(A,b,NULL,2,2,1,2,2,17,0,&after));
    assert(!memcmp(&after.certified,&old.certified,sizeof(old.certified)));
    puts("policy ABI, validation, default equivalence, isolation and concurrency: PASS");
}
