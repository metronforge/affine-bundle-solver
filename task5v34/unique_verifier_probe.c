#define _POSIX_C_SOURCE 200809L
#pragma STDC FENV_ACCESS ON
#include <affine_bundle/certified_api.h>
#include <fenv.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint64_t tick(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return(uint64_t)t.tv_sec*1000000000ULL+(uint64_t)t.tv_nsec;}
static int load_input(const char*path,int*m,int*n,double**A,double**b){
 FILE*f=fopen(path,"rb");int32_t d[2];if(!f)return 1;if(fread(d,sizeof(int32_t),2,f)!=2){fclose(f);return 2;}*m=d[0];*n=d[1];
 *A=malloc((size_t)*m*(size_t)*n*sizeof(double));*b=malloc((size_t)*m*sizeof(double));if(!*A||!*b){fclose(f);free(*A);free(*b);return 3;}
 if(fread(*A,sizeof(double),(size_t)*m*(size_t)*n,f)!=(size_t)*m*(size_t)*n||fread(*b,sizeof(double),(size_t)*m,f)!=(size_t)*m){fclose(f);free(*A);free(*b);return 4;}fclose(f);return 0;}
static void dot_interval(const double*a,const double*b,int n,double*lo,double*hi){volatile double s,p;fesetround(FE_DOWNWARD);s=0.0;for(int k=0;k<n;++k){p=a[k]*b[k];s=s+p;}*lo=s;fesetround(FE_UPWARD);s=0.0;for(int k=0;k<n;++k){p=a[k]*b[k];s=s+p;}*hi=s;}
static void packed_interval(const double*lu,int n,int lr,int j,double*lo,double*hi){
 int last=lr<j?lr:j;volatile double s,p,l,u;fesetround(FE_DOWNWARD);s=0.0;for(int k=0;k<=last;++k){l=k<lr?lu[(size_t)lr*n+k]:1.0;u=lu[(size_t)k*n+j];p=l*u;s=s+p;}*lo=s;
 fesetround(FE_UPWARD);s=0.0;for(int k=0;k<=last;++k){l=k<lr?lu[(size_t)lr*n+k]:1.0;u=lu[(size_t)k*n+j];p=l*u;s=s+p;}*hi=s;}
static void baseline_kernel(const BSUniqueWitness*w,double*lo,double*hi,double*lrow,double*ucol){int n=w->n;for(int ks=0;ks<n;++ks){int lr=w->perm[ks];for(int k=0;k<n;++k)lrow[k]=k<lr?w->packed_lu[(size_t)lr*n+k]:(k==lr?1.0:0.0);for(int j=0;j<n;++j){for(int k=0;k<n;++k)ucol[k]=k<=j?w->packed_lu[(size_t)k*n+j]:0.0;dot_interval(lrow,ucol,n,&lo[(size_t)ks*n+j],&hi[(size_t)ks*n+j]);}}}
static void direct_kernel(const BSUniqueWitness*w,double*lo,double*hi){int n=w->n;for(int ks=0;ks<n;++ks){int lr=w->perm[ks];for(int j=0;j<n;++j)packed_interval(w->packed_lu,n,lr,j,&lo[(size_t)ks*n+j],&hi[(size_t)ks*n+j]);}}
int main(int argc,char**argv){
 if(argc!=3){fprintf(stderr,"usage: %s INPUT TRIALS\n",argv[0]);return 2;}int m=0,n=0,trials=atoi(argv[2]);double*A=0,*b=0;if(load_input(argv[1],&m,&n,&A,&b))return 3;
 BSUniqueWitness w={0};uint64_t gs=tick();int grc=bs_generate_unique_witness(A,b,m,n,&w);uint64_t gns=tick()-gs;
 printf("meta,m=%d,n=%d,gen_rc=%d,gen_ns=%llu\n",m,n,grc,(unsigned long long)gns);
 if(grc){free(A);free(b);return 0;}double eta=0.0;(void)bs_verify_unique(A,b,m,n,&w,&eta);
 puts("trial,verify_ns,verify_rc,eta");for(int i=0;i<trials;++i){uint64_t s=tick();int rc=bs_verify_unique(A,b,m,n,&w,&eta);uint64_t ns=tick()-s;printf("%d,%llu,%d,%.17g\n",i,(unsigned long long)ns,rc,eta);}
 size_t nn=(size_t)n*(size_t)n;double*blo=malloc(nn*sizeof(double)),*bhi=malloc(nn*sizeof(double)),*dlo=malloc(nn*sizeof(double)),*dhi=malloc(nn*sizeof(double)),*lrow=malloc((size_t)n*sizeof(double)),*ucol=malloc((size_t)n*sizeof(double));if(!blo||!bhi||!dlo||!dhi||!lrow||!ucol)return 5;
 int old=fegetround();baseline_kernel(&w,blo,bhi,lrow,ucol);direct_kernel(&w,dlo,dhi);fesetround(old);unsigned long long mismatches=0;double max_abs=0.0;for(size_t k=0;k<nn;++k){if(memcmp(&blo[k],&dlo[k],sizeof(double))||memcmp(&bhi[k],&dhi[k],sizeof(double)))++mismatches;double q=fmax(fabs(blo[k]-dlo[k]),fabs(bhi[k]-dhi[k]));if(q>max_abs)max_abs=q;}
 printf("kernel_meta,mismatches=%llu,max_abs=%.17g\n",mismatches,max_abs);puts("trial,baseline_kernel_ns,direct_kernel_ns");for(int i=0;i<trials;++i){uint64_t s,a,d;if(i&1){s=tick();direct_kernel(&w,dlo,dhi);d=tick()-s;s=tick();baseline_kernel(&w,blo,bhi,lrow,ucol);a=tick()-s;}else{s=tick();baseline_kernel(&w,blo,bhi,lrow,ucol);a=tick()-s;s=tick();direct_kernel(&w,dlo,dhi);d=tick()-s;}printf("%d,%llu,%llu\n",i,(unsigned long long)a,(unsigned long long)d);}fesetround(old);
 free(blo);free(bhi);free(dlo);free(dhi);free(lrow);free(ucol);
 bs_unique_witness_free(&w);free(A);free(b);return 0;}
