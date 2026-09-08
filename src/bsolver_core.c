/*
 * bsolver_core.c -- Affine-bundle state, exact insertion calculus, and support routines.
 *
 * Copyright 2026 Viktor Mikhalkin
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <time.h>
#include <alloca.h>
#include <omp.h>
#include "formation_guard.h"
#include "blas_symbols.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

extern void dgelsy_(int*,int*,int*,double*,int*,double*,int*,int*,double*,int*,double*,int*,int*);
extern void dgesvd_(char*,char*,int*,int*,double*,int*,double*,double*,int*,double*,int*,double*,int*,int*);

typedef struct { int n, r, inconsistent; double *Q; double *x; long double orth_frob2; } BState;
typedef struct { int cls; int rank; int fallback; int accepted_random; double sec; double relres; double relx; } Result;

enum { CLS_UNIQUE=1, CLS_INFINITE=2, CLS_INCONSISTENT=3, CLS_FAIL=4, CLS_UNDECIDABLE=5 };

static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+1e-9*ts.tv_nsec; }
static uint64_t sm64(uint64_t x){ x+=0x9e3779b97f4a7c15ULL; x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL; x=(x^(x>>27))*0x94d049bb133111ebULL; return x^(x>>31); }
static double uhash(uint64_t x){ uint64_t z=sm64(x); return ((z>>11)*(1.0/9007199254740992.0))*2.0-1.0; }
static double gauss(uint64_t *s){ double u1=(uhash((*s)++)+1)*0.5; double u2=(uhash((*s)++)+1)*0.5; if(u1<1e-15)u1=1e-15; return sqrt(-2*log(u1))*cos(2*M_PI*u2); }
static double dot(const double*a,const double*b,int n){ double s=0; for(int i=0;i<n;i++)s+=a[i]*b[i]; return s; }
static int finite_bits(double x){union{double d;uint64_t u;}v={x};return ((v.u>>52)&0x7ffULL)!=0x7ffULL;}
static double norm2(const double*a,int n){
    double ss=dot(a,a,n); if(ss>0.0 && finite_bits(ss)) return sqrt(ss);
    double scale=0.0,sumsq=1.0; for(int i=0;i<n;i++){double av=fabs(a[i]);if(av!=0.0){if(scale<av){double q=scale/av;sumsq=1.0+sumsq*q*q;scale=av;}else{double q=av/scale;sumsq+=q*q;}}} return scale==0.0?0.0:scale*sqrt(sumsq);
}

static long double dot_ld(const double*a,const double*b,int n){ long double s=0.0L; for(int i=0;i<n;i++)s+=(long double)a[i]*(long double)b[i]; return s; }
static void bs_accumulate_new_q_defect(BState*s,const double*q){
    /* Incremental a-posteriori Gram defect.  Double accumulation is deliberate:
       the defect enters the distance envelope quadratically, while a small
       explicit floating-point cushion is added by the certificate layer. */
    double di=dot(q,q,s->n)-1.0; long double e2=(long double)di*(long double)di;
    for(int k=0;k<s->r;k++){const double*qk=s->Q+(size_t)k*s->n; double c=dot(q,qk,s->n); e2+=2.0L*(long double)c*(long double)c;}
    s->orth_frob2+=e2;
}
static double bs_orth_eta(const BState*s){ long double v=s->orth_frob2; return v<=0.0L?0.0:(double)sqrtl(v); }
static void bs_set_backend_orth_bound(BState*s){
    long double e=64.0L*(long double)DBL_EPSILON*(long double)(s->r>0?s->r:1);
    s->orth_frob2=e*e;
}
static void bs_init(BState*s,int n){ s->n=n;s->r=0;s->inconsistent=0;s->orth_frob2=0.0L;s->Q=calloc((size_t)n*n,sizeof(double));s->x=calloc(n,sizeof(double)); }
static void bs_copy(BState*d,const BState*s){ bs_init(d,s->n); d->r=s->r;d->inconsistent=s->inconsistent;d->orth_frob2=s->orth_frob2; memcpy(d->Q,s->Q,(size_t)s->n*s->n*sizeof(double));memcpy(d->x,s->x,s->n*sizeof(double)); }
static void bs_free(BState*s){ free(s->Q);free(s->x); }

static int bs_insert(BState*s,const double*a0,double beta0,double tolrank,double tolcon){
    int n=s->n; if(s->inconsistent)return -1;
    double an=norm2(a0,n); if(an==0){ if(fabs(beta0)>tolcon){s->inconsistent=1;return -1;} return 0; }
    double *a=alloca(n*sizeof(double)); double *g=alloca(n*sizeof(double));
    double inv=1.0/an; for(int j=0;j<n;j++){a[j]=a0[j]*inv;g[j]=a[j];} double beta=beta0*inv;
    // two-pass MGS residual
    for(int pass=0;pass<2;pass++) for(int k=0;k<s->r;k++){ double *q=s->Q+(size_t)k*n; double c=dot(g,q,n); for(int j=0;j<n;j++)g[j]-=c*q[j]; }
    double gn=norm2(g,n); double rho=beta-dot(a,s->x,n);
    double rt=tolrank;
    double ct=tolcon*(1.0+fabs(beta)+norm2(s->x,n));
    if(gn>rt){
        double *q=s->Q+(size_t)s->r*n; for(int j=0;j<n;j++)q[j]=g[j]/gn;
        bs_accumulate_new_q_defect(s,q);
        double alpha=rho/gn; for(int j=0;j<n;j++)s->x[j]+=alpha*q[j]; s->r++; return 1;
    }
    if(fabs(rho)>ct){ s->inconsistent=1; return -1; }
    return 0;
}

static int bs_check_row(const BState*s,const double*a0,double beta0,double tolrank,double tolcon,int *is_contra){
    int n=s->n; *is_contra=0; double an=norm2(a0,n); if(an==0){ if(fabs(beta0)>tolcon){*is_contra=1;return 0;} return 1; }
    double *a=alloca(n*sizeof(double)); double *g=alloca(n*sizeof(double)); double inv=1.0/an;
    for(int j=0;j<n;j++){a[j]=a0[j]*inv;g[j]=a[j];} double beta=beta0*inv;
    for(int pass=0;pass<2;pass++) for(int k=0;k<s->r;k++){ const double*q=s->Q+(size_t)k*n; double c=dot(g,q,n); for(int j=0;j<n;j++)g[j]-=c*q[j]; }
    double gn=norm2(g,n); double rho=beta-dot(a,s->x,n); double ct=tolcon*(1+fabs(beta)+norm2(s->x,n));
    if(gn>tolrank) return 0; if(fabs(rho)>ct){*is_contra=1;return 0;} return 1;
}

static double relres(const double*A,const double*b,const double*x,int m,int n){ long double nr=0,nb=0;
#pragma omp parallel for if(((long long)m*n)>=1000000LL && n<384) reduction(+:nr,nb) schedule(static)
for(int i=0;i<m;i++){ long double t=(long double)dot(A+(size_t)i*n,x,n)-(long double)b[i];nr+=t*t;long double bi=(long double)b[i];nb+=bi*bi;} long double den=sqrtl(nb);if(den==0)den=1;return (double)(sqrtl(nr)/den); }
static double relxerr(const double*x,const double*xt,int n){ if(!xt)return NAN; double a=0,b=0;for(int i=0;i<n;i++){double d=x[i]-xt[i];a+=d*d;b+=xt[i]*xt[i];}return sqrt(a)/(sqrt(b)+1e-300); }

static Result solve_seq(const double*A,const double*b,const double*xt,int m,int n){ Result R={0}; double t0=now_sec(); BState s;bs_init(&s,n); double tr=1e-10,tc=2e-10;
 for(int i=0;i<m;i++){ if(s.r==n){ double an=norm2(A+(size_t)i*n,n); double rho=b[i]-dot(A+(size_t)i*n,s.x,n); if(an>0 && fabs(rho/an)>tc*(1+fabs(b[i]/an)+norm2(s.x,n))){s.inconsistent=1;break;} } else bs_insert(&s,A+(size_t)i*n,b[i],tr,tc); if(s.inconsistent)break; }
 R.sec=now_sec()-t0; R.rank=s.r; R.cls=s.inconsistent?CLS_INCONSISTENT:(s.r==n?CLS_UNIQUE:CLS_INFINITE); R.relres=relres(A,b,s.x,m,n);R.relx=relxerr(s.x,xt,n);bs_free(&s);return R; }

static void sketch_remainder(const double*A,const double*b,int start,int m,int n,int k,int sp,int qv,uint64_t seed,double*C,double*d,double*E,double*f,double*formT,int*formL,double*valT,int*valL){
    uint64_t sseed=sm64(seed^0x243F6A8885A308D3ULL),vseed=sm64(seed^0x13198A2E03707344ULL);
    double invs=1.0/sqrt((double)sp),invm=1.0/sqrt((double)(m-start>0?m-start:1));long long work=(long long)(m-start)*n;
    if(sp==1 && qv==2 && work>=1000000LL && omp_get_max_threads()>1){
        int nt=omp_get_max_threads();double *LC=calloc((size_t)nt*k*n,sizeof(double)),*Ld=calloc((size_t)nt*k,sizeof(double)),*LE=calloc((size_t)nt*2*n,sizeof(double)),*Lf=calloc((size_t)nt*2,sizeof(double)); double *LT=formT?calloc((size_t)nt*k,sizeof(double)):NULL; int *LL=formL?calloc((size_t)nt*k,sizeof(int)):NULL; double *LVT=valT?calloc((size_t)nt*qv,sizeof(double)):NULL; int *LVL=valL?calloc((size_t)nt*qv,sizeof(int)):NULL;
        #pragma omp parallel
        {
          int tid=omp_get_thread_num();double *cbase=LC+(size_t)tid*k*n,*dbase=Ld+(size_t)tid*k,*ebase=LE+(size_t)tid*2*n,*fbase=Lf+(size_t)tid*2; double *tbase=LT?LT+(size_t)tid*k:NULL; int *lbase=LL?LL+(size_t)tid*k:NULL; double *vtbase=LVT?LVT+(size_t)tid*qv:NULL; int *vlbase=LVL?LVL+(size_t)tid*qv:NULL;
          #pragma omp for schedule(static)
          for(int i=start;i<m;i++){
            const double*row=A+(size_t)i*n;double an=norm2(row,n);if(an==0)continue;double invan=1.0/an,beta=b[i]*invan;
            uint64_t h=sm64(sseed ^ ((uint64_t)i*0x9e3779b97f4a7c15ULL) ^ 0xbf58476d1ce4e5b9ULL);int bucket=(int)(h%(uint64_t)k);double sg=(h>>63)?invs:-invs;
            double w0=uhash(vseed+0xD1B54A32D192ED03ULL*(uint64_t)(i+1)+0x94D049BB133111EBULL)*invm,w1=uhash(vseed+0xD1B54A32D192ED03ULL*(uint64_t)(i+1)+2ULL*0x94D049BB133111EBULL)*invm;
            double *cr=cbase+(size_t)bucket*n,*e0=ebase,*e1=ebase+n;double cs=sg*invan,c0=w0*invan,c1=w1*invan; double mx=0.0;
            for(int j=0;j<n;j++){double v=row[j],av=fabs(v);if(av>mx)mx=av;cr[j]+=cs*v;e0[j]+=c0*v;e1[j]+=c1*v;} {double rnup=(tbase||vtbase)?fg_row_norm_upper_from_max(mx,n):0.0;if(tbase)tbase[bucket]=fg_up_mul_add(tbase[bucket],cs,rnup);if(vtbase){vtbase[0]=fg_up_mul_add(vtbase[0],c0,rnup);vtbase[1]=fg_up_mul_add(vtbase[1],c1,rnup);}} if(lbase)lbase[bucket]++;if(vlbase){vlbase[0]++;vlbase[1]++;}dbase[bucket]+=sg*beta;fbase[0]+=w0*beta;fbase[1]+=w1*beta;
          }
        }
        for(int t=0;t<nt;t++){double*cbase=LC+(size_t)t*k*n,*dbase=Ld+(size_t)t*k,*ebase=LE+(size_t)t*2*n,*fbase=Lf+(size_t)t*2;for(size_t z=0;z<(size_t)k*n;z++)C[z]+=cbase[z];for(int z=0;z<k;z++){d[z]+=dbase[z]; if(formT)formT[z]=fg_up_add(formT[z],LT[(size_t)t*k+z]); if(formL)formL[z]+=LL[(size_t)t*k+z];}for(int z=0;z<2*n;z++)E[z]+=ebase[z];for(int v=0;v<qv;v++){if(valT)valT[v]=fg_up_add(valT[v],LVT[(size_t)t*qv+v]);if(valL)valL[v]+=LVL[(size_t)t*qv+v];}f[0]+=fbase[0];f[1]+=fbase[1];}
        free(LVT);free(LVL);free(LT);free(LL);free(LC);free(Ld);free(LE);free(Lf);return;
    }
    for(int i=start;i<m;i++){
        const double*row=A+(size_t)i*n;double an=norm2(row,n);if(an==0)continue;double invan=1.0/an,beta=b[i]*invan;
        if(sp==1 && qv==2){uint64_t h=sm64(sseed ^ ((uint64_t)i*0x9e3779b97f4a7c15ULL) ^ 0xbf58476d1ce4e5b9ULL);int bucket=(int)(h%(uint64_t)k);double sg=(h>>63)?invs:-invs;double w0=uhash(vseed+0xD1B54A32D192ED03ULL*(uint64_t)(i+1)+0x94D049BB133111EBULL)*invm,w1=uhash(vseed+0xD1B54A32D192ED03ULL*(uint64_t)(i+1)+2ULL*0x94D049BB133111EBULL)*invm;double*cr=C+(size_t)bucket*n,*e0=E,*e1=E+n;double cs=sg*invan,c0=w0*invan,c1=w1*invan;double mx=0.0;for(int j=0;j<n;j++){double v=row[j],av=fabs(v);if(av>mx)mx=av;cr[j]+=cs*v;e0[j]+=c0*v;e1[j]+=c1*v;}{double rnup=(formT||valT)?fg_row_norm_upper_from_max(mx,n):0.0;if(formT)formT[bucket]=fg_up_mul_add(formT[bucket],cs,rnup);if(valT){valT[0]=fg_up_mul_add(valT[0],c0,rnup);valT[1]=fg_up_mul_add(valT[1],c1,rnup);}}if(formL)formL[bucket]++;if(valL){valL[0]++;valL[1]++;}d[bucket]+=sg*beta;f[0]+=w0*beta;f[1]+=w1*beta;continue;}
        double rnup=0.0;if(formT||valT){double mx=0.0;for(int jj=0;jj<n;jj++){double av=fabs(row[jj]);if(av>mx)mx=av;}rnup=fg_row_norm_upper_from_max(mx,n);}for(int t=0;t<sp;t++){uint64_t h=sm64(sseed ^ ((uint64_t)i*0x9e3779b97f4a7c15ULL) ^ (uint64_t)(t+1)*0xbf58476d1ce4e5b9ULL);int bucket=(int)(h%(uint64_t)k);double sg=(h>>63)?invs:-invs,*cr=C+(size_t)bucket*n,c=sg*invan;if(formT)formT[bucket]=fg_up_mul_add(formT[bucket],c,rnup);if(formL)formL[bucket]++;for(int j=0;j<n;j++)cr[j]+=c*row[j];d[bucket]+=sg*beta;}for(int v=0;v<qv;v++){double w=uhash(vseed+0xD1B54A32D192ED03ULL*(uint64_t)(i+1)+0x94D049BB133111EBULL*(uint64_t)(v+1))*invm,*er=E+(size_t)v*n,c=w*invan;if(valT)valT[v]=fg_up_mul_add(valT[v],c,rnup);if(valL)valL[v]++;for(int j=0;j<n;j++)er[j]+=c*row[j];f[v]+=w*beta;}
    }
}

static int core_svd_state(const double*Core,const double*y,int rows,int n,BState*out,double*relr,double ranktol);

static Result solve_fast(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,uint64_t seed,int do_full_residual){
 Result R={0}; double t0=now_sec(); double tr=1e-10,tc=2e-10; BState pre;bs_init(&pre,n); int p=n<m?n:m;
 for(int i=0;i<p;i++){bs_insert(&pre,A+(size_t)i*n,b[i],tr,tc);if(pre.inconsistent)break;}
 if(pre.inconsistent){R.cls=CLS_INCONSISTENT;R.rank=pre.r;R.sec=now_sec()-t0;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);bs_free(&pre);return R;}
 if(pre.r==n){ // residual stream
   int bad=0; for(int i=p;i<m;i++){double an=norm2(A+(size_t)i*n,n);if(an==0)continue;double rr=(b[i]-dot(A+(size_t)i*n,pre.x,n))/an;if(fabs(rr)>tc*(1+fabs(b[i]/an)+norm2(pre.x,n))){bad=1;break;}}
   R.cls=bad?CLS_INCONSISTENT:CLS_UNIQUE;R.rank=n;R.sec=now_sec()-t0;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);bs_free(&pre);return R;
 }
 int dh=(n+1)-pre.r; int k=alpha*dh; if(k<dh)k=dh; if(k>m-p)k=m-p; if(k<1)k=1;
 double*C=calloc((size_t)k*n,sizeof(double)),*d=calloc(k,sizeof(double)),*E=calloc((size_t)qv*n,sizeof(double)),*f=calloc(qv,sizeof(double));
 sketch_remainder(A,b,p,m,n,k,sp,qv,seed,C,d,E,f,NULL,NULL,NULL,NULL);
 // Build one small normalized core = exact prefix rows + sketch rows; solve it stably by SVD.
 int crmax=p+k, cr=0; double*Core=malloc((size_t)crmax*n*sizeof(double)), *cy=malloc(crmax*sizeof(double));
 for(int i=0;i<p;i++){double an=norm2(A+(size_t)i*n,n);if(an==0)continue;for(int j=0;j<n;j++)Core[(size_t)cr*n+j]=A[(size_t)i*n+j]/an;cy[cr]=b[i]/an;cr++;}
 for(int i=0;i<k;i++){double an=norm2(C+(size_t)i*n,n);if(an==0)continue;for(int j=0;j<n;j++)Core[(size_t)cr*n+j]=C[(size_t)i*n+j]/an;cy[cr]=d[i]/an;cr++;}
 BState cand; double core_rr=0; if(core_svd_state(Core,cy,cr,n,&cand,&core_rr,1e-11)!=0){R.fallback=1;bs_copy(&cand,&pre);for(int i=p;i<m;i++){bs_insert(&cand,A+(size_t)i*n,b[i],tr,tc);if(cand.inconsistent)break;}}
 free(Core);free(cy);
 if(core_rr>1e-8){ /* robust contradiction in a subsystem of linear combinations */ cand.inconsistent=1; R.cls=CLS_INCONSISTENT;R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done; }
 if(core_rr>1e-11){ /* numerical grey zone */ R.fallback=1; bs_free(&cand);bs_copy(&cand,&pre);for(int i=p;i<m;i++){bs_insert(&cand,A+(size_t)i*n,b[i],tr,tc);if(cand.inconsistent)break;}R.cls=cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE);R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done; }
 /* A validator may report contra=1, i.e. the compressed row looks
    contradictory.  That signal is deliberately NOT acted on here: a
    sketched residual must not be promoted to source-level inconsistency.
    Setting vfail alone routes the case to the deterministic source rescan
    below, which is the only path allowed to declare INCONSISTENT. */
 int vfail=0; for(int v=0;v<qv;v++){int contra=0; if(!bs_check_row(&cand,E+(size_t)v*n,f[v],5e-9,2e-9,&contra)){vfail=1;(void)contra;break;}}
 if(!vfail){
    if(do_full_residual){ double rr=relres(A,b,cand.x,m,n); if(rr>2e-9) vfail=1; }
 }
 if(!vfail){R.cls=(cand.r==n?CLS_UNIQUE:CLS_INFINITE);R.rank=cand.r;R.accepted_random=1;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done;}
 // deterministic fallback: scan all original rows starting from candidate
 R.fallback=1; for(int i=0;i<m;i++){bs_insert(&cand,A+(size_t)i*n,b[i],tr,tc);if(cand.inconsistent)break;}
 R.cls=cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE);R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;
 done: free(C);free(d);free(E);free(f);bs_free(&cand);bs_free(&pre);return R;
}


static int core_svd_state(const double*Core,const double*y,int rows,int n,BState*out,double*relr,double ranktol){
    int M=rows,N=n,LDA=rows,minmn=M<N?M:N,info=0; char ju='S',jv='A';
    double *Ac=malloc((size_t)M*N*sizeof(double)); for(int j=0;j<N;j++)for(int i=0;i<M;i++)Ac[(size_t)j*M+i]=Core[(size_t)i*N+j];
    double *sv=malloc(minmn*sizeof(double)), *U=malloc((size_t)M*minmn*sizeof(double)), *VT=malloc((size_t)N*N*sizeof(double)); int LDU=M,LDVT=N; double wq;int lw=-1;
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,sv,U,&LDU,VT,&LDVT,&wq,&lw,&info); lw=(int)wq; double*work=malloc((size_t)lw*sizeof(double));
    for(int j=0;j<N;j++)for(int i=0;i<M;i++)Ac[(size_t)j*M+i]=Core[(size_t)i*N+j];
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,sv,U,&LDU,VT,&LDVT,work,&lw,&info);
    if(info){free(Ac);free(sv);free(U);free(VT);free(work);return -1;}
    int r=0; double thresh=(minmn?sv[0]:0)*ranktol; for(int l=0;l<minmn;l++)if(sv[l]>thresh)r++;
    bs_init(out,n); out->r=r;
    for(int l=0;l<r;l++){ double*q=out->Q+(size_t)l*n; for(int j=0;j<n;j++)q[j]=VT[l+(size_t)j*N]; }
    bs_set_backend_orth_bound(out);
    // min-norm x = V Sigma^-1 U^T y
    for(int l=0;l<r;l++){ double uy=0; for(int i=0;i<M;i++)uy+=U[i+(size_t)l*M]*y[i]; double c=uy/sv[l]; for(int j=0;j<N;j++)out->x[j]+=VT[l+(size_t)j*N]*c; }
    double nr=0,ny=0; for(int i=0;i<M;i++){double rr=dot(Core+(size_t)i*N,out->x,N)-y[i];nr+=rr*rr;ny+=y[i]*y[i];} *relr=sqrt(nr)/(sqrt(ny)+1e-300);
    free(Ac);free(sv);free(U);free(VT);free(work);return 0;
}

static Result solve_lapack(const double*A,const double*b,const double*xt,int m,int n){ Result R={0}; int M=m,N=n,NRHS=1,LDA=m,LDB=(m>n?m:n),rank=0,info=0; double *Ac=malloc((size_t)m*n*sizeof(double)); double *B=calloc(LDB,sizeof(double)); int*jpvt=calloc(n,sizeof(int));
 for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[(size_t)j*m+i]=A[(size_t)i*n+j];memcpy(B,b,m*sizeof(double));double rcond=1e-10,wq;int lwork=-1;dgelsy_(&M,&N,&NRHS,Ac,&LDA,B,&LDB,jpvt,&rcond,&rank,&wq,&lwork,&info);lwork=(int)wq;double*work=malloc((size_t)lwork*sizeof(double));
 // restore after query because query should not modify materially, but be safe
 for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[(size_t)j*m+i]=A[(size_t)i*n+j];memcpy(B,b,m*sizeof(double));memset(jpvt,0,n*sizeof(int)); double t0=now_sec();dgelsy_(&M,&N,&NRHS,Ac,&LDA,B,&LDB,jpvt,&rcond,&rank,work,&lwork,&info);R.sec=now_sec()-t0;R.rank=rank;R.relres=relres(A,b,B,m,n);R.relx=relxerr(B,xt,n);R.cls=(R.relres>2e-9?CLS_INCONSISTENT:(rank==n?CLS_UNIQUE:CLS_INFINITE));free(Ac);free(B);free(jpvt);free(work);return R; }

static void hadamard_row(double*out,int idx,int n){ double inv=1.0/sqrt((double)n);for(int j=0;j<n;j++){unsigned v=(unsigned)(idx & j);int parity=__builtin_parity(v);out[j]=(parity?-inv:inv);} }
static void gen_grouped(double*A,double*b,double*x,int m,int n,int inconsistent){uint64_t s=1234;for(int j=0;j<n;j++)x[j]=gauss(&s);int grp=(m+n-1)/n;double*dir=malloc(n*sizeof(double));for(int i=0;i<m;i++){int d=i/grp;if(d>=n)d=n-1;hadamard_row(dir,d,n);memcpy(A+(size_t)i*n,dir,n*sizeof(double));b[i]=dot(dir,x,n);}if(inconsistent)b[m-1]+=0.25;free(dir);}
static void gen_random(double*A,double*b,double*x,int m,int n,int r,int inconsistent){uint64_t s=99123;for(int j=0;j<n;j++)x[j]=gauss(&s);double*B=malloc((size_t)r*n*sizeof(double));for(int k=0;k<r;k++)hadamard_row(B+(size_t)k*n,k,n);for(int i=0;i<m;i++){double*row=A+(size_t)i*n;memset(row,0,n*sizeof(double));for(int k=0;k<r;k++){double c=gauss(&s);for(int j=0;j<n;j++)row[j]+=c*B[(size_t)k*n+j];}b[i]=dot(row,x,n);}if(inconsistent)b[m-1]+=0.3;free(B);}

static const char*cn(int c){return c==CLS_UNIQUE?"U":c==CLS_INFINITE?"I":c==CLS_INCONSISTENT?"X":"F";}
static void run_case(const char*name,double*A,double*b,double*x,int m,int n,int lapack){
 Result a=solve_seq(A,b,x,m,n);Result f=solve_fast(A,b,x,m,n,4,2,2,777,0);Result v=solve_fast(A,b,x,m,n,4,2,2,777,1);printf("CASE %-16s m=%d n=%d | seq %s r%d %.3fms rr%.1e | fast1 %s r%d %.3fms fb%d rr%.1e | fast2 %s r%d %.3fms fb%d rr%.1e",name,m,n,cn(a.cls),a.rank,a.sec*1e3,a.relres,cn(f.cls),f.rank,f.sec*1e3,f.fallback,f.relres,cn(v.cls),v.rank,v.sec*1e3,v.fallback,v.relres);if(lapack){Result l=solve_lapack(A,b,x,m,n);printf(" | gelsy %s r%d %.3fms rr%.1e",cn(l.cls),l.rank,l.sec*1e3,l.relres);}printf("\n");
}

static int load_matrix(const char*fn,double**A,int*m,int*n){FILE*f=fopen(fn,"rb");if(!f)return 0;int64_t mm,nn;if(fread(&mm,8,1,f)!=1||fread(&nn,8,1,f)!=1){fclose(f);return 0;}*m=(int)mm;*n=(int)nn;*A=malloc((size_t)(*m)*(*n)*sizeof(double));size_t z=fread(*A,sizeof(double),(size_t)(*m)*(*n),f);fclose(f);return z==(size_t)(*m)*(*n);}


static void gen_rare(double*A,double*b,double*x,int m,int n,int inconsistent){
 uint64_t ss=4567; for(int j=0;j<n;j++)x[j]=gauss(&ss); double*dir=malloc(n*sizeof(double));
 // first n rows all direction 0 => prefix rank 1
 hadamard_row(dir,0,n); for(int i=0;i<n && i<m;i++){memcpy(A+(size_t)i*n,dir,n*sizeof(double));b[i]=dot(dir,x,n);} 
 int pos=n; // place each missing direction exactly once, fill remaining with direction 0
 for(int d=1;d<n && pos<m;d++,pos++){hadamard_row(dir,d,n);memcpy(A+(size_t)pos*n,dir,n*sizeof(double));b[pos]=dot(dir,x,n);} 
 hadamard_row(dir,0,n); for(int i=pos;i<m;i++){memcpy(A+(size_t)i*n,dir,n*sizeof(double));b[i]=dot(dir,x,n);} 
 if(inconsistent && m>0)b[m-1]+=0.2; free(dir);
}
static void stress_case(const char*name,const double*A,const double*b,const double*x,int m,int n,int trials,int sp,int qv,int alpha){
 Result truth=solve_seq(A,b,x,m,n); int wrong=0,fb=0,accept=0; double tsum=0,maxrr=0; for(int t=0;t<trials;t++){Result r=solve_fast(A,b,x,m,n,sp,qv,alpha,1000+(uint64_t)t,0); if(r.cls!=truth.cls|| (r.cls!=CLS_INCONSISTENT && r.rank!=truth.rank)){ if(wrong<3) fprintf(stderr,"WRONG %s seed%llu got%s/r%d fb%d rr%.3e truth%s/r%d\n",name,(unsigned long long)(1000+t),cn(r.cls),r.rank,r.fallback,r.relres,cn(truth.cls),truth.rank); wrong++;} fb+=r.fallback;accept+=r.accepted_random;tsum+=r.sec;if(r.relres>maxrr)maxrr=r.relres;} printf("STRESS %-14s sp%d q%d a%d trials%d wrong%d fallback%d accept%d avg%.3fms maxrr%.1e truth%s/r%d\n",name,sp,qv,alpha,trials,wrong,fb,accept,tsum*1e3/trials,maxrr,cn(truth.cls),truth.rank);
}

int main(int argc,char**argv){
 int n=64; int ms[]={16384,65536,131072};for(int t=0;t<3;t++){int m=ms[t];double*A=malloc((size_t)m*n*sizeof(double)),*b=malloc(m*sizeof(double)),*x=malloc(n*sizeof(double));gen_grouped(A,b,x,m,n,0);run_case("grouped",A,b,x,m,n,t<2);free(A);free(b);free(x);}
 {int m=32768;double*A=malloc((size_t)m*n*sizeof(double)),*b=malloc(m*sizeof(double)),*x=malloc(n*sizeof(double));gen_random(A,b,x,m,n,n,0);run_case("random-full",A,b,x,m,n,1);free(A);free(b);free(x);} 
 {int m=32768;double*A=malloc((size_t)m*n*sizeof(double)),*b=malloc(m*sizeof(double)),*x=malloc(n*sizeof(double));gen_random(A,b,x,m,n,n-8,0);run_case("rankdef",A,b,x,m,n,1);free(A);free(b);free(x);} 
 {int m=32768;double*A=malloc((size_t)m*n*sizeof(double)),*b=malloc(m*sizeof(double)),*x=malloc(n*sizeof(double));gen_grouped(A,b,x,m,n,1);run_case("inconsistent",A,b,x,m,n,1);free(A);free(b);free(x);} 
 for(int ai=1;ai<argc;ai++){double*A=NULL;int m,ncase;if(!load_matrix(argv[ai],&A,&m,&ncase)){fprintf(stderr,"load fail %s\n",argv[ai]);continue;}double*x=malloc(ncase*sizeof(double)),*b=malloc(m*sizeof(double));uint64_t s=123;for(int j=0;j<ncase;j++)x[j]=gauss(&s);for(int i=0;i<m;i++)b[i]=dot(A+(size_t)i*ncase,x,ncase);run_case(argv[ai],A,b,x,m,ncase,1); stress_case("real-cons",A,b,x,m,ncase,100,4,2,2); if(m>ncase+2){b[m-1]+=0.15;run_case("real-incons",A,b,x,m,ncase,1);stress_case("real-X",A,b,x,m,ncase,100,4,2,2);}free(A);free(b);free(x);} {int m=4096,ncase=64;double*A=malloc((size_t)m*ncase*sizeof(double)),*b=malloc(m*sizeof(double)),*x=malloc(ncase*sizeof(double));gen_rare(A,b,x,m,ncase,0);stress_case("rare-s1",A,b,x,m,ncase,200,1,2,2);stress_case("rare-s4",A,b,x,m,ncase,200,4,2,2);b[m-1]+=0.2;stress_case("rare-X-s1",A,b,x,m,ncase,200,1,2,2);stress_case("rare-X-s4",A,b,x,m,ncase,200,4,2,2);free(A);free(b);free(x);} return 0;
}
