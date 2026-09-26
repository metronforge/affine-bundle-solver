#define _POSIX_C_SOURCE 200809L
#include <affine_bundle/certified_api.h>
#include <affine_bundle/router.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static uint64_t now_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC_RAW,&t);
    return (uint64_t)t.tv_sec*1000000000ULL+(uint64_t)t.tv_nsec;
}
static int load_input(const char *path,int *m,int *n,double **A,double **b) {
    FILE *f=fopen(path,"rb");int32_t dims[2];if(!f)return 1;
    if(fread(dims,sizeof(int32_t),2,f)!=2){fclose(f);return 2;}*m=dims[0];*n=dims[1];
    *A=(double*)malloc((size_t)*m*(size_t)*n*sizeof(double));*b=(double*)malloc((size_t)*m*sizeof(double));
    if(!*A||!*b){fclose(f);free(*A);free(*b);return 3;}
    if(fread(*A,sizeof(double),(size_t)*m*(size_t)*n,f)!=(size_t)*m*(size_t)*n ||
       fread(*b,sizeof(double),(size_t)*m,f)!=(size_t)*m){fclose(f);free(*A);free(*b);return 4;}
    fclose(f);return 0;
}
static void one(const double *A,const double *b,int m,int n,int emit,int trial) {
    BSCombinedCertifiedResult combined={0};BSInconsistentWitness w={0};double lo=0,hi=0,eta=0,meta[ABS_OUT_LEN];int grey[64];
    uint64_t t=now_ns();int api=bsolve_certified_diag_api(A,b,NULL,m,n,2,2,2,17,0,&combined);uint64_t combined_ns=now_ns()-t;
    t=now_ns();int count=bsolve_router_diag_api(A,b,NULL,m,n,2,2,2,17,0,meta,grey,64);uint64_t router_ns=now_ns()-t;
    t=now_ns();int gen=bs_generate_inconsistent_witness(A,b,m,n,&w);uint64_t generator_ns=now_ns()-t;
    t=now_ns();int verify=gen?99:bs_verify_inconsistent(A,b,m,n,&w,&lo,&hi,&eta);uint64_t verifier_ns=now_ns()-t;
    bs_inconsistent_witness_free(&w);
    if(emit)printf("%d,%llu,%llu,%llu,%llu,%d,%d,%d,%d\n",trial,(unsigned long long)combined_ns,
      (unsigned long long)router_ns,(unsigned long long)generator_ns,(unsigned long long)verifier_ns,api,gen,verify,count);
}
int main(int argc,char **argv) {
    if(argc!=3){fprintf(stderr,"usage: %s INPUT REPS\n",argv[0]);return 2;}int m=0,n=0,reps=atoi(argv[2]);double *A=NULL,*b=NULL;
    int rc=load_input(argv[1],&m,&n,&A,&b);if(rc){fprintf(stderr,"input error %d\n",rc);return 3;}
    one(A,b,m,n,0,-1);puts("trial,combined_ns,router_ns,inconsistent_generator_ns,inconsistent_verifier_ns,api_rc,gen_rc,verify_rc,router_grey_count");
    for(int i=0;i<reps;i++)one(A,b,m,n,1,i);free(A);free(b);return 0;
}
