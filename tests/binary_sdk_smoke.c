#include <affine_bundle/certified_api.h>
#include <affine_bundle/stream.h>
#include <stdio.h>

#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"SDK assertion line %d\n",__LINE__); return 1; } } while (0)

int main(void) {
    const double A[]={1,0,0,1}, b[]={2,3}, zero[]={0,0};
    BSOperationalPolicyV1 p; bs_default_operational_policy(&p);
    BSCombinedSemanticResultV1 r; bs_init_combined_semantic_result(&r);
    REQUIRE(bsolve_certified_policy_api(A,b,NULL,2,2,1,2,2,777,0,&p,&r)==0);
    REQUIRE(r.operational.operational_status==ABS_STATUS_UNIQUE);
    REQUIRE(r.operational.router_meta[ABS_OUT_RANK]==2);
    /* Nearby certificates are not mutually exclusive classifications. */
    fprintf(stderr,"nearby mask=%d unique generation=%d verification=%d\n",
            r.nearby_status_mask,r.certificate_profile.unique_generator_code,
            r.certificate_profile.unique_verifier_code);
    REQUIRE(r.nearby_status_mask==7);
    REQUIRE(r.certificate_profile.unique_generator_code==0);
    REQUIRE(r.certificate_profile.unique_verifier_code==0);
    ABSStream *s=abs_stream_create(2); REQUIRE(s);
    double out[ABS_OUT_LEN]={0};
    REQUIRE(abs_stream_insert(s,A,2)==ABS_INSERT_GROW);
    abs_stream_status(s,out);
    REQUIRE(out[ABS_OUT_STATUS]==ABS_STATUS_INFINITE && out[ABS_OUT_RANK]==1);
    REQUIRE(abs_stream_insert(s,A+2,3)==ABS_INSERT_GROW);
    REQUIRE(abs_stream_insert(s,zero,0)==ABS_INSERT_ABSORB);
    abs_stream_status(s,out);
    REQUIRE(out[ABS_OUT_STATUS]==ABS_STATUS_UNIQUE && out[ABS_OUT_RANK]==2);
    REQUIRE(abs_stream_insert(s,zero,1)==ABS_INSERT_CONTRA);
    abs_stream_status(s,out);
    REQUIRE(out[ABS_OUT_STATUS]==ABS_STATUS_INCONSISTENT && out[ABS_OUT_RANK]==2);
    abs_stream_destroy(s);
    printf("{\"policy_status\":%d,\"rank\":%d,\"accepted_status_mask\":%d,"
           "\"generation\":%d,\"verification\":%d,\"stream_final_status\":%d,\"stream_rank\":%d}\n",
           r.operational.operational_status,(int)r.operational.router_meta[ABS_OUT_RANK],
           r.nearby_status_mask,r.certificate_profile.unique_generator_code,
           r.certificate_profile.unique_verifier_code,(int)out[ABS_OUT_STATUS],(int)out[ABS_OUT_RANK]);
    return 0;
}
