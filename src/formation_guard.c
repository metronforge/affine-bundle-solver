/*
 * formation_guard.c -- Strict a-posteriori formation-provenance checker for compressed rank evidence.
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
#include "formation_guard.h"
#include <float.h>
#include <math.h>
#include <stdlib.h>
#include <stdint.h>

#pragma STDC FENV_ACCESS ON

static double up(double x){ return isfinite(x) ? nextafter(x, INFINITY) : x; }
static double dn(double x){ return isfinite(x) ? nextafter(x, -INFINITY) : x; }
static double sub_dn(double a,double b){ return dn(a-b); }

double fg_up_mul_add(double acc,double a,double b){
    if(!(isfinite(acc)&&isfinite(a)&&isfinite(b))) return INFINITY;
    return up(acc + up(fabs(a)*fabs(b)));
}

double fg_up_add(double a,double b){
    if(!(isfinite(a)&&isfinite(b))) return INFINITY;
    return up(a+b);
}

static unsigned ceil_sqrt_u(unsigned n){
    unsigned q=0;
    while((uint64_t)q*(uint64_t)q < (uint64_t)n) q++;
    return q;
}

double fg_row_norm_upper_from_max(double maxabs,int n){
    if(n<=0 || maxabs==0.0) return 0.0;
    if(!isfinite(maxabs)) return INFINITY;
    return up((double)ceil_sqrt_u((unsigned)n)*maxabs);
}

double fg_sketch_formation_eps(double T,int ell,int n){
    if(ell<=0 || n<=0) return 0.0;
    if(!isfinite(T)) return INFINITY;
    const double u=0.5*DBL_EPSILON;
    /* One product plus local accumulation, and (in the parallel path) a
       reduction of nonempty thread partials.  gamma_{3 ell+2} covers both
       sequential and parallel formation, including an FMA implementation. */
    double ku=(3.0*(double)ell+2.0)*u;
    if(!(ku<0.5)) return INFINITY;
    double gamma=up(ku/(1.0-ku));
    double rel=up(gamma*T);
#ifdef DBL_TRUE_MIN
    double tiny=DBL_TRUE_MIN;
#else
    double tiny=nextafter(0.0,1.0);
#endif
    unsigned q=ceil_sqrt_u((unsigned)n);
    double absu=up((double)(2LL*ell+2LL)*(double)q*tiny);
    return up(rel+absu);
}

static double ld_pos_up(long double x, int ops){
    if(!(x>=0.0L) || !isfinite((double)x)) return INFINITY;
    long double u=0.5L*LDBL_EPSILON;
    long double ku=(long double)(ops>1?ops:1)*u;
    if(ku<0.25L) x *= (1.0L + 4.0L*ku/(1.0L-ku));
    double d=(double)x;
    if(!isfinite(d))return INFINITY;
    if((long double)d < x)d=nextafter(d,INFINITY);else d=nextafter(d,INFINITY);
    return d;
}

double fg_core_normalized_eps(double raw_eps,double raw_maxabs,double divisor,int n){
    if(!(divisor>0.0) || n<=0 || !isfinite(divisor))return INFINITY;
    double rn=fg_row_norm_upper_from_max(raw_maxabs,n);
    if(!isfinite(rn)||!isfinite(raw_eps))return INFINITY;
    const double u=0.5*DBL_EPSILON;
    double ratio=up(rn/divisor);
    /* One correctly-rounded division per coordinate.  The common divisor is
       interpreted as the stored binary64 scalar; only coordinatewise rounding
       creates off-source drift. */
    double divrel=up((u/(1.0-u))*ratio);
#ifdef DBL_TRUE_MIN
    double tiny=DBL_TRUE_MIN;
#else
    double tiny=nextafter(0.0,1.0);
#endif
    unsigned q=ceil_sqrt_u((unsigned)n);
    double divabs=up((double)q*tiny);
    double form=up(raw_eps/divisor);
    return up(form+divrel+divabs);
}

static long double ld_gamma(int ops){
    long double u=0.5L*LDBL_EPSILON;
    long double ku=(long double)(ops>0?ops:1)*u;
    if(!(ku<0.25L))return INFINITY;
    return ku/(1.0L-ku);
}

static double dot_abs_error_bound_ld(const double *a,const double *b,int n,long double *sum_out){
    long double s=0.0L,as=0.0L;
    for(int k=0;k<n;k++){long double p=(long double)a[k]*(long double)b[k];s+=p;as+=fabsl(p);}
    if(sum_out)*sum_out=s;
    long double g=ld_gamma(2*n+2);
    long double e=g*as + 8.0L*LDBL_EPSILON*(fabsl(s)+as+1.0L);
    return ld_pos_up(e,8);
}

/* A posteriori QR/provenance certificate.
   For the first j QRCP pivots, K_J^T = Q_j R_j + F.  Define
       Y^T = K_J^T R_j^{-1}.
   Then Y is an exact linear combination of computed core rows, while
       ||Y^T-Q_j|| <= ||F||_F ||R_j^{-1}||_F.
   Formation budgets propagated through R_j^{-T} bound dist(Y,row(A)).
   If that source-distance bound is smaller than a lower bound on sigma_min(Y),
   the source row space must have dimension at least j. */
int fg_qr_rank_lower_bound(const double *K,const double *eps,int rows,int n,int rmax,
                           const int *piv,const double *R,int rs,const double *Q){
    if(!K||!eps||!piv||!R||!Q||rows<=0||n<=0||rmax<=0||rs<rmax)return 0;
    if(rmax>rows)rmax=rows;if(rmax>n)rmax=n;
    double *X=(double*)calloc((size_t)rmax*rmax,sizeof(double));
    if(!X)return 0;
    /* Absolute upper bound on |R^{-1}| by positive triangular recurrence. */
    for(int j=0;j<rmax;j++){
        double d=fabs(R[(size_t)j*rs+j]);
        if(!(d>0.0)||!isfinite(d)){free(X);return 0;}
        X[(size_t)j*rmax+j]=up(1.0/d);
        for(int i=j-1;i>=0;i--){
            double di=fabs(R[(size_t)i*rs+i]);if(!(di>0.0)||!isfinite(di)){free(X);return 0;}
            long double s=0.0L;
            for(int k=i+1;k<=j;k++)s+=(long double)fabs(R[(size_t)i*rs+k])*(long double)X[(size_t)k*rmax+j];
            double su=ld_pos_up(s,2*(j-i)+8);X[(size_t)i*rmax+j]=up(su/di);
        }
    }
    int best=0;
    for(int r=1;r<=rmax;r++){
        /* ||R_r^{-1}||_F upper. */
        long double xi2=0.0L;for(int i=0;i<r;i++)for(int j=i;j<r;j++){long double x=X[(size_t)i*rmax+j];xi2+=x*x;}
        double xif=ld_pos_up(sqrtl(xi2),2*r*r+16);
        if(!isfinite(xif))break;
        /* QR residual F for the selected columns. */
        long double ff2=0.0L;
        for(int col=0;col<r;col++){
            int pr=piv[col];if(pr<0||pr>=rows){free(X);return best;}
            const double *kr=K+(size_t)pr*n;
            for(int x=0;x<n;x++){
                long double s=0.0L,as=0.0L;
                for(int k=0;k<=col && k<r;k++){long double p=(long double)Q[(size_t)k*n+x]*(long double)R[(size_t)k*rs+col];s+=p;as+=fabsl(p);}
                long double g=ld_gamma(2*(col+1)+4);
                long double err=g*as+8.0L*LDBL_EPSILON*(fabsl(s)+as+fabsl((long double)kr[x])+1.0L);
                long double fa=fabsl((long double)kr[x]-s)+err;ff2+=fa*fa;
            }
        }
        double ff=ld_pos_up(sqrtl(ff2),2*r*n+32);double eqr=up(ff*xif);
        if(!isfinite(eqr))break;
        /* Actual stored Q orthogonality, with long-double dot error envelope. */
        long double eta2=0.0L;
        for(int i=0;i<r;i++)for(int j=0;j<=i;j++){
            long double ds=0.0L;double de=dot_abs_error_bound_ld(Q+(size_t)i*n,Q+(size_t)j*n,n,&ds);
            long double target=(i==j)?1.0L:0.0L;long double a=fabsl(ds-target)+(long double)de;
            eta2+=(i==j?1.0L:2.0L)*a*a;
        }
        double eta=ld_pos_up(sqrtl(eta2),r*r+32);if(!(eta<1.0))break;
        double qmin=dn(sqrt(fmax(0.0,1.0-eta)));
        /* Propagate rowwise core formation budgets through R^{-T}. */
        long double es2=0.0L;
        for(int i=0;i<r;i++){
            long double si=0.0L;
            for(int j=0;j<=i;j++){int pr=piv[j];si+=(long double)X[(size_t)j*rmax+i]*(long double)fabs(eps[pr]);}
            double siu=ld_pos_up(si,2*i+16);es2+=(long double)siu*(long double)siu;
        }
        double es=ld_pos_up(sqrtl(es2),r*r+32);
        double ymin=sub_dn(qmin,eqr);
        if(ymin>es)best=r;else break;
    }
    free(X);return best;
}

/* Single-rank provenance certificate using only a-posteriori identities.
   Dense products/inversion are proposal computations; their actual residuals are
   bounded afterwards.  This keeps the proof O(r^3) in optimized BLAS rather than
   O(r^3) scalar long-double recurrences plus all-prefix rechecks. */
#define dtrtri_ scipy_dtrtri_
#define dgemm_  scipy_dgemm_
extern void dtrtri_(char*,char*,int*,double*,int*,int*);
extern void dgemm_(char*,char*,int*,int*,int*,double*,double*,int*,double*,int*,double*,double*,int*);

static double frob_up(const double *a,size_t z){
    long double s=0.0L;for(size_t i=0;i<z;i++){long double x=(long double)a[i];s+=x*x;}
    return ld_pos_up(sqrtl(s),(int)(2*(z>1000000?1000000:z)+16));
}
static double gamma_double_up(int ops){
    const double u=0.5*DBL_EPSILON;double ku=(double)(ops>1?ops:1)*u;if(!(ku<0.25))return INFINITY;return up(ku/(1.0-ku));
}
int fg_qr_rank_certifies(const double *K,const double *eps,int rows,int n,int r,
                         const int *piv,const double *Rrm,int rs,const double *Qcols){
    if(r<=0)return 1;if(!K||!eps||!piv||!Rrm||!Qcols||rows<=0||n<=0||r>rows||r>n||rs<r)return 0;
    int ok=0,info=0,N=r,LDA=r;char U='U',ND='N',NN='N',TT='T';double one=1.0,zero=0.0;
    double *R=(double*)calloc((size_t)r*r,sizeof(double)),*X=(double*)calloc((size_t)r*r,sizeof(double));
    double *RX=(double*)calloc((size_t)r*r,sizeof(double)),*G=(double*)calloc((size_t)r*r,sizeof(double));
    double *QR=(double*)calloc((size_t)n*r,sizeof(double));
    if(!R||!X||!RX||!G||!QR)goto done;
    for(int j=0;j<r;j++)for(int i=0;i<=j;i++){double v=Rrm[(size_t)i*rs+j];R[i+(size_t)j*r]=v;X[i+(size_t)j*r]=v;}
    dtrtri_(&U,&ND,&N,X,&LDA,&info);if(info)goto done;
    for(size_t z=0;z<(size_t)r*r;z++)if(!isfinite(X[z]))goto done;
    dgemm_(&NN,&NN,&N,&N,&N,&one,R,&LDA,X,&LDA,&zero,RX,&LDA);
    long double rr2=0.0L;for(int j=0;j<r;j++)for(int i=0;i<r;i++){long double v=(long double)RX[i+(size_t)j*r]-(i==j?1.0L:0.0L);rr2+=v*v;}
    double Rf=frob_up(R,(size_t)r*r),Xf=frob_up(X,(size_t)r*r);double gmm=gamma_double_up(2*r+8);
    double mult_err=up(gmm*up(Rf*Xf));double rho=up(ld_pos_up(sqrtl(rr2),2*r*r+32)+mult_err+up(16.0*DBL_EPSILON));
    if(!(rho<1.0))goto done;double invb=up(Xf/(1.0-rho));if(!isfinite(invb))goto done;

    /* Q is stored as r row vectors of length n, which is column-major n x r. */
    int Mq=n,Nq=r,Kq=r,ldq=n,ldr=r,ldqr=n;
    dgemm_(&NN,&NN,&Mq,&Nq,&Kq,&one,(double*)Qcols,&ldq,R,&ldr,&zero,QR,&ldqr);
    long double ff2=0.0L,kf2=0.0L;for(int j=0;j<r;j++){int pr=piv[j];if(pr<0||pr>=rows)goto done;const double *kr=K+(size_t)pr*n;for(int i=0;i<n;i++){long double kv=(long double)kr[i],dv=kv-(long double)QR[i+(size_t)j*n];ff2+=dv*dv;kf2+=kv*kv;}}
    double Qf=frob_up(Qcols,(size_t)r*n);double qr_round=up(gamma_double_up(2*r+8)*up(Qf*Rf));
    double F=up(ld_pos_up(sqrtl(ff2),2*r*n+32)+qr_round+up(16.0*DBL_EPSILON*sqrt((double)(r*n))));

    int Mg=r,Ng=r,Kg=n,ldg=r;dgemm_(&TT,&NN,&Mg,&Ng,&Kg,&one,(double*)Qcols,&ldq,(double*)Qcols,&ldq,&zero,G,&ldg);
    long double eta2=0.0L;for(int j=0;j<r;j++)for(int i=0;i<r;i++){long double v=(long double)G[i+(size_t)j*r]-(i==j?1.0L:0.0L);eta2+=v*v;}
    double orth_round=up(gamma_double_up(2*n+8)*up(Qf*Qf));double eta=up(ld_pos_up(sqrtl(eta2),2*r*r+32)+orth_round+up(16.0*DBL_EPSILON));if(!(eta<1.0))goto done;
    double qmin=dn(sqrt(fmax(0.0,1.0-eta)));
    long double e2=0.0L;for(int j=0;j<r;j++){int pr=piv[j];long double e=(long double)fabs(eps[pr]);e2+=e*e;}double ef=ld_pos_up(sqrtl(e2),2*r+16);
    double total=up(up(F*invb)+up(ef*invb));if(qmin>total)ok=1;
done:free(R);free(X);free(RX);free(G);free(QR);return ok;
}

