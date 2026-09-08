/*
 * certified_api.c -- Audit API: attempts all three typed proof objects independently of the router.
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
#include "affine_bundle/certified_api.h"
#include <math.h>
#include <float.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* The fast library is deliberately outside the trusted certificate checker. */
extern void bsolve_router_meta_api(const double*,const double*,const double*,int,int,int,int,int,
                                   unsigned long long,int,double*);

#include "blas_symbols.h"
extern void dgelsy_(int*,int*,int*,double*,int*,double*,int*,int*,double*,int*,double*,int*,int*);
extern void dgeqp3_(int*,int*,double*,int*,int*,double*,double*,int*,int*);
extern void dgesvd_(char*,char*,int*,int*,double*,int*,double*,double*,int*,double*,int*,double*,int*,int*);
extern void dgeqrf_(int*,int*,double*,int*,double*,double*,int*,int*);
extern void dormqr_(char*,char*,int*,int*,int*,double*,int*,double*,double*,int*,double*,int*,int*);

static double row_norm(const double *a, int n) {
    long double s = 0.0L;
    for (int j = 0; j < n; ++j) { long double v = a[j]; s += v*v; }
    return (double)sqrtl(s);
}

static int finite_array(const double *a, size_t n) {
    if (!a) return 0;
    for (size_t i = 0; i < n; ++i) if (!isfinite(a[i])) return 0;
    return 1;
}


/* Normalize each augmented source row [a_i,b_i] to unit 2-norm without
   ever forming that norm in binary64.  We retain d_i = mant_i * 2^exp_i
   so a left-null witness ybar for the normalized system can be mapped back
   as y_i proportional to ybar_i/d_i.  Independent row scalings therefore
   cancel in the witness construction itself rather than being left for the
   verifier to absorb. */
static int normalize_augmented_rows(const double *A,const double *b,int m,int n,
                                    double *An,double *bn,long double *dmant,int *dexp) {
    for(int i=0;i<m;i++){
        double mx=fabs(b[i]);
        for(int j=0;j<n;j++){double q=fabs(A[(size_t)i*n+j]);if(q>mx)mx=q;}
        if(mx==0.0){
            bn[i]=0.0;dmant[i]=0.0L;dexp[i]=0;
            for(int j=0;j<n;j++)An[(size_t)i*n+j]=0.0;
            continue;
        }
        int e=0;double mf=frexp(mx,&e); /* mx = mf * 2^e, exactly. */
        long double ss=0.0L;
        for(int j=0;j<n;j++){long double q=(long double)A[(size_t)i*n+j]/(long double)mx;ss+=q*q;}
        {long double q=(long double)b[i]/(long double)mx;ss+=q*q;}
        if(!(ss>0.0L)||!isfinite((double)fminl(ss,(long double)DBL_MAX)))return 1;
        long double qn=sqrtl(ss);
        dmant[i]=(long double)mf*qn;dexp[i]=e;
        for(int j=0;j<n;j++)An[(size_t)i*n+j]=(double)(((long double)A[(size_t)i*n+j]/(long double)mx)/qn);
        bn[i]=(double)(((long double)b[i]/(long double)mx)/qn);
    }
    return 0;
}

/* Map ybar through D^{-1} robustly.  A common power-of-two is removed before
   casting to binary64; the verifier is homogeneous in y, so this changes no
   certificate.  best_out is selected in normalized coordinates, where
   |ybar_i| is exactly the row-scaling-invariant pivot score |y_i| d_i. */
static int map_augmented_left_witness(const double *ybar,const long double *dmant,const int *dexp,
                                      int m,double *y,int *best_out) {
    int emax=INT32_MIN,best=-1;long double bestabs=-1.0L;
    for(int i=0;i<m;i++){
        if(dmant[i]==0.0L||ybar[i]==0.0)continue;
        long double c=(long double)ybar[i]/dmant[i],ac=fabsl(c);
        if(!(ac>0.0L))continue;
        int ce=0;frexpl(ac,&ce);int eraw=ce-dexp[i];if(eraw>emax)emax=eraw;
        long double ya=fabsl((long double)ybar[i]);if(ya>bestabs){bestabs=ya;best=i;}
    }
    if(emax==INT32_MIN||best<0)return 1;
    /* The verifier is homogeneous in y.  Do not waste exponent headroom by
       forcing ||y||=1: place the largest component high in the binary64
       range while reserving ~64 exponent bits plus a dimension guard for
       dot-product accumulation.  This lets inverse row scales spanning almost
       the full nonzero binary64 range coexist in one witness. */
    /* Choose the common homogeneous scale from the raw witness exponent.
       Mapping max(D^{-1}ybar) to `target` multiplies all products A_i*y_i
       and b_i*y_i by roughly 2^(target-emax).  Cap that common product scale
       near 2^500 while still using upper exponent headroom when inverse row
       scales require it. */
    int target=emax+500; if(target>1000)target=1000;
    int any=0;
    for(int i=0;i<m;i++){
        long double v=0.0L;
        if(dmant[i]!=0.0L&&ybar[i]!=0.0)
            v=scalbnl((long double)ybar[i]/dmant[i],-dexp[i]+target-emax);
        y[i]=(double)v;if(y[i]!=0.0)any=1;
    }
    if(!any)return 2;
    if(y[best]==0.0){
        best=-1;bestabs=-1.0L;
        for(int i=0;i<m;i++)if(y[i]!=0.0){long double ya=fabsl((long double)ybar[i]);if(ya>bestabs){bestabs=ya;best=i;}}
        if(best<0)return 3;
    }
    *best_out=best;return 0;
}

static int least_squares_x(const double *A, const double *b, int m, int n,
                           double *x, int *rank_out) {
    if (n <= 0 || m < 0 || !x) return 1;
    if (m == 0) { for (int j=0;j<n;++j) x[j]=0.0; if(rank_out)*rank_out=0; return 0; }
    int M=m,N=n,NRHS=1,LDA=m,LDB=(m>n?m:n),rank=0,info=0,lwork=-1;
    double *Ac=(double*)malloc((size_t)m*n*sizeof(double));
    double *B=(double*)calloc((size_t)LDB,sizeof(double));
    int *jpvt=(int*)calloc((size_t)n,sizeof(int));
    if(!Ac||!B||!jpvt){free(Ac);free(B);free(jpvt);return 2;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    memcpy(B,b,(size_t)m*sizeof(double));
    double rcond=1e-12,wq=0.0;
    dgelsy_(&M,&N,&NRHS,Ac,&LDA,B,&LDB,jpvt,&rcond,&rank,&wq,&lwork,&info);
    if(info){free(Ac);free(B);free(jpvt);return 3;}
    lwork=(int)wq; if(lwork<1)lwork=1;
    double *work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(B);free(jpvt);return 4;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    memcpy(B,b,(size_t)m*sizeof(double)); memset(jpvt,0,(size_t)n*sizeof(int));
    dgelsy_(&M,&N,&NRHS,Ac,&LDA,B,&LDB,jpvt,&rcond,&rank,work,&lwork,&info);
    if(!info) memcpy(x,B,(size_t)n*sizeof(double));
    if(rank_out)*rank_out=rank;
    free(Ac);free(B);free(jpvt);free(work);
    return info?5:0;
}

static int select_rows_qrcp(const double *A,int m,int n,int *idx) {
    if(m<n||n<=0)return 1;
    int M=n,N=m,LDA=n,info=0,lwork=-1,minmn=n;
    double *AT=(double*)calloc((size_t)n*m,sizeof(double));
    int *jpvt=(int*)calloc((size_t)m,sizeof(int));
    double *tau=(double*)malloc((size_t)minmn*sizeof(double));
    if(!AT||!jpvt||!tau){free(AT);free(jpvt);free(tau);return 2;}
    for(int i=0;i<m;i++){
        double s=row_norm(A+(size_t)i*n,n);
        if(s>0.0) for(int j=0;j<n;j++) AT[j+(size_t)i*n]=A[(size_t)i*n+j]/s;
    }
    double wq=0.0;
    dgeqp3_(&M,&N,AT,&LDA,jpvt,tau,&wq,&lwork,&info);
    if(info){free(AT);free(jpvt);free(tau);return 3;}
    lwork=(int)wq;if(lwork<1)lwork=1;double *work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(AT);free(jpvt);free(tau);return 4;}
    memset(jpvt,0,(size_t)m*sizeof(int));
    for(int i=0;i<m;i++){
        double s=row_norm(A+(size_t)i*n,n);
        for(int j=0;j<n;j++) AT[j+(size_t)i*n]=(s>0.0?A[(size_t)i*n+j]/s:0.0);
    }
    dgeqp3_(&M,&N,AT,&LDA,jpvt,tau,work,&lwork,&info);
    if(!info) for(int i=0;i<n;i++) idx[i]=jpvt[i]-1;
    free(AT);free(jpvt);free(tau);free(work);return info?5:0;
}

/* In-place partial-pivot LU: Q*N=L*U.  perm[original_row]=factor_row,
   hence N = Q^T L U and the verifier reconstructs row i from row perm[i] of LU. */
static int lu_pack(const double *N,int n,double *packed,int *perm) {
    int *order=(int*)malloc((size_t)n*sizeof(int));
    if(!order)return 1;
    memcpy(packed,N,(size_t)n*n*sizeof(double));
    for(int i=0;i<n;i++)order[i]=i;
    for(int k=0;k<n;k++){
        int piv=k; double best=fabs(packed[(size_t)k*n+k]);
        for(int i=k+1;i<n;i++){double v=fabs(packed[(size_t)i*n+k]);if(v>best){best=v;piv=i;}}
        if(!(best>0.0)||!isfinite(best)){free(order);return 2;}
        if(piv!=k){
            for(int j=0;j<n;j++){double t=packed[(size_t)k*n+j];packed[(size_t)k*n+j]=packed[(size_t)piv*n+j];packed[(size_t)piv*n+j]=t;}
            int ti=order[k];order[k]=order[piv];order[piv]=ti;
        }
        double akk=packed[(size_t)k*n+k];
        for(int i=k+1;i<n;i++){
            packed[(size_t)i*n+k]/=akk;
            double lik=packed[(size_t)i*n+k];
            for(int j=k+1;j<n;j++) packed[(size_t)i*n+j]-=lik*packed[(size_t)k*n+j];
        }
    }
    for(int pos=0;pos<n;pos++)perm[order[pos]]=pos;
    free(order);return 0;
}

int bs_generate_unique_witness(const double *A,const double *b,int m,int n,BSUniqueWitness *w) {
    if(!A||!b||!w||m<n||n<=0||!finite_array(A,(size_t)m*n)||!finite_array(b,(size_t)m))return 1;
    memset(w,0,sizeof(*w));w->m=m;w->n=n;
    w->idx=(int*)malloc((size_t)n*sizeof(int));w->scale=(double*)malloc((size_t)n*sizeof(double));
    w->perm=(int*)malloc((size_t)n*sizeof(int));w->packed_lu=(double*)malloc((size_t)n*n*sizeof(double));w->x=(double*)malloc((size_t)n*sizeof(double));
    double *N=(double*)malloc((size_t)n*n*sizeof(double));
    if(!w->idx||!w->scale||!w->perm||!w->packed_lu||!w->x||!N){free(N);bs_unique_witness_free(w);return 2;}
    int rank=0;if(least_squares_x(A,b,m,n,w->x,&rank)){free(N);bs_unique_witness_free(w);return 3;}
    if(select_rows_qrcp(A,m,n,w->idx)){free(N);bs_unique_witness_free(w);return 4;}
    for(int i=0;i<n;i++){
        int ix=w->idx[i];double s=row_norm(A+(size_t)ix*n,n);w->scale[i]=s;
        if(!(s>0.0)){free(N);bs_unique_witness_free(w);return 5;}
        for(int j=0;j<n;j++)N[(size_t)i*n+j]=A[(size_t)ix*n+j]/s;
    }
    int rc=lu_pack(N,n,w->packed_lu,w->perm);free(N);
    if(rc){bs_unique_witness_free(w);return 6;}
    return 0;
}

static int smallest_right_vector(const double *A,int m,int n,double *z) {
    if(n<=0)return 1;
    if(m==0){for(int j=0;j<n;j++)z[j]=(j==0?1.0:0.0);return 0;}
    int M=m,N=n,LDA=m,minmn=(m<n?m:n),LDVT=n,LDU=1,info=0,lwork=-1;
    char ju='N',jv='A';
    double *Ac=(double*)malloc((size_t)m*n*sizeof(double));double *s=(double*)malloc((size_t)minmn*sizeof(double));
    double *VT=(double*)malloc((size_t)n*n*sizeof(double));double udummy=0.0,wq=0.0;
    if(!Ac||!s||!VT){free(Ac);free(s);free(VT);return 2;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,s,&udummy,&LDU,VT,&LDVT,&wq,&lwork,&info);
    if(info){free(Ac);free(s);free(VT);return 3;}
    lwork=(int)wq;if(lwork<1)lwork=1;double *work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(s);free(VT);return 4;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,s,&udummy,&LDU,VT,&LDVT,work,&lwork,&info);
    if(!info){int r=n-1;for(int j=0;j<n;j++)z[j]=VT[r+(size_t)j*n];}
    free(Ac);free(s);free(VT);free(work);return info?5:0;
}

int bs_generate_infinite_witness(const double *A,const double *b,int m,int n,BSInfiniteWitness *w) {
    if(!A||!b||!w||m<0||n<=0||!finite_array(A,(size_t)m*n)||!finite_array(b,(size_t)m))return 1;
    memset(w,0,sizeof(*w));w->n=n;w->x=(double*)malloc((size_t)n*sizeof(double));w->z=(double*)malloc((size_t)n*sizeof(double));
    if(!w->x||!w->z){bs_infinite_witness_free(w);return 2;}
    int rank=0;if(least_squares_x(A,b,m,n,w->x,&rank)){bs_infinite_witness_free(w);return 3;}
    if(smallest_right_vector(A,m,n,w->z)){bs_infinite_witness_free(w);return 4;}
    return 0;
}

/* Build one explicit computed left-null direction from a pivoted QR.
   If rank_hint < m, column rank_hint of the implicit Q is orthogonal to the
   first rank_hint pivoted source columns.  For a rank-revealing rank_hint this
   gives a left-null proposal without forming an m-by-m Q.  The proposal is
   untrusted; the strict verifier still checks A^T y. */
static int left_null_vector_qrcp(const double *A,int m,int n,int rank_hint,double *y) {
    if(!A||!y||m<=0||n<0||rank_hint<0||rank_hint>=m)return 1;
    if(n==0){for(int i=0;i<m;i++)y[i]=(i==rank_hint?1.0:0.0);return 0;}
    int M=m,N=n,LDA=m,K=(m<n?m:n),info=0,lwork=-1,one=1,LDC=m;
    double *Ac=(double*)malloc((size_t)m*n*sizeof(double));
    int *jpvt=(int*)calloc((size_t)n,sizeof(int));
    double *tau=(double*)malloc((size_t)K*sizeof(double));
    double *v=(double*)calloc((size_t)m,sizeof(double));
    if(!Ac||!jpvt||!tau||!v){free(Ac);free(jpvt);free(tau);free(v);return 2;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    double wq=0.0;
    dgeqp3_(&M,&N,Ac,&LDA,jpvt,tau,&wq,&lwork,&info);
    if(info){free(Ac);free(jpvt);free(tau);free(v);return 3;}
    lwork=(int)wq;if(lwork<1)lwork=1;double *work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(jpvt);free(tau);free(v);return 4;}
    memset(jpvt,0,(size_t)n*sizeof(int));
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    dgeqp3_(&M,&N,Ac,&LDA,jpvt,tau,work,&lwork,&info);
    free(work);free(jpvt);
    if(info){free(Ac);free(tau);free(v);return 5;}
    v[rank_hint]=1.0;
    char side='L',trans='N';lwork=-1;wq=0.0;
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,&wq,&lwork,&info);
    if(info){free(Ac);free(tau);free(v);return 6;}
    lwork=(int)wq;if(lwork<1)lwork=1;work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(tau);free(v);return 7;}
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,work,&lwork,&info);
    free(work);free(Ac);free(tau);
    if(info){free(v);return 8;}
    memcpy(y,v,(size_t)m*sizeof(double));free(v);return 0;
}

/* Project b onto the computed orthogonal complement of the first
   rank_hint pivoted QR directions.  The crucial difference from the old
   tail projection is that we discard only the numerically supported rank,
   not blindly the first n Q coordinates. */
static int left_null_projection_rank_qrcp(const double *A,const double *b,int m,int n,int rank_hint,
                                          double *y,long double *tail_rel) {
    if(tail_rel)*tail_rel=0.0L;
    if(!A||!b||!y||m<=0||n<0||rank_hint<0||rank_hint>m)return 1;
    if(n==0){
        long double bn2=0.0L;for(int i=0;i<m;i++){y[i]=b[i];bn2+=(long double)b[i]*b[i];}
        if(tail_rel)*tail_rel=(bn2>0.0L?1.0L:0.0L);return 0;
    }
    int M=m,N=n,LDA=m,K=(m<n?m:n),info=0,lwork=-1,one=1,LDC=m;
    double *Ac=(double*)malloc((size_t)m*n*sizeof(double));int *jpvt=(int*)calloc((size_t)n,sizeof(int));
    double *tau=(double*)malloc((size_t)K*sizeof(double));double *v=(double*)malloc((size_t)m*sizeof(double));
    if(!Ac||!jpvt||!tau||!v){free(Ac);free(jpvt);free(tau);free(v);return 2;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    double wq=0.0;dgeqp3_(&M,&N,Ac,&LDA,jpvt,tau,&wq,&lwork,&info);
    if(info){free(Ac);free(jpvt);free(tau);free(v);return 3;}
    lwork=(int)wq;if(lwork<1)lwork=1;double *work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(jpvt);free(tau);free(v);return 4;}
    memset(jpvt,0,(size_t)n*sizeof(int));for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    dgeqp3_(&M,&N,Ac,&LDA,jpvt,tau,work,&lwork,&info);free(work);free(jpvt);
    if(info){free(Ac);free(tau);free(v);return 5;}
    memcpy(v,b,(size_t)m*sizeof(double));char side='L',trans='T';lwork=-1;wq=0.0;
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,&wq,&lwork,&info);
    if(info){free(Ac);free(tau);free(v);return 6;}
    lwork=(int)wq;if(lwork<1)lwork=1;work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(tau);free(v);return 7;}
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,work,&lwork,&info);free(work);
    if(info){free(Ac);free(tau);free(v);return 8;}
    long double bn2=0.0L,tn2=0.0L;for(int i=0;i<m;i++)bn2+=(long double)b[i]*b[i];
    for(int i=0;i<rank_hint && i<m;i++)v[i]=0.0;
    for(int i=rank_hint;i<m;i++)tn2+=(long double)v[i]*v[i];
    if(tail_rel)*tail_rel=(bn2>0.0L?sqrtl(tn2/bn2):0.0L);
    trans='N';lwork=-1;wq=0.0;dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,&wq,&lwork,&info);
    if(info){free(Ac);free(tau);free(v);return 9;}
    lwork=(int)wq;if(lwork<1)lwork=1;work=(double*)malloc((size_t)lwork*sizeof(double));
    if(!work){free(Ac);free(tau);free(v);return 10;}
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,work,&lwork,&info);
    free(work);free(Ac);free(tau);if(info){free(v);return 11;}
    long double vn2=0.0L;for(int i=0;i<m;i++){long double q=v[i];vn2+=q*q;}
    if(!(vn2>0.0L)){free(v);return 12;}
    long double inv=1.0L/sqrtl(vn2);for(int i=0;i<m;i++)y[i]=(double)((long double)v[i]*inv);
    free(v);return 0;
}

/* For m>n, compute a single left-null direction aligned with b without
   forming a full m-by-m Q.  DGEQRF stores n Householder reflectors for A=QR;
   DORMQR applies Q^T to b, we discard the first n coordinates, and then apply
   Q back.  The resulting vector lies in the computed orthogonal complement
   of col(A), up to the numerical QR/apply errors.  Normalization is important:
   the verifier's one-row correction radius is scale invariant in y. */
static int left_null_projection_qr(const double *A,const double *b,int m,int n,double *y) {
    if(!A||!b||!y||m<=n||n<=0)return 1;
    int M=m,N=n,LDA=m,K=n,info=0,lwork=-1,one=1,LDC=m;
    double *Ac=(double*)malloc((size_t)m*n*sizeof(double));
    double *tau=(double*)malloc((size_t)n*sizeof(double));
    double *v=(double*)malloc((size_t)m*sizeof(double));
    if(!Ac||!tau||!v){free(Ac);free(tau);free(v);return 2;}
    for(int j=0;j<n;j++)for(int i=0;i<m;i++)Ac[i+(size_t)j*m]=A[(size_t)i*n+j];
    memcpy(v,b,(size_t)m*sizeof(double));

    double wq=0.0;
    dgeqrf_(&M,&N,Ac,&LDA,tau,&wq,&lwork,&info);
    if(info){free(Ac);free(tau);free(v);return 3;}
    int lwqrf=(int)wq;if(lwqrf<1)lwqrf=1;
    double *work=(double*)malloc((size_t)lwqrf*sizeof(double));
    if(!work){free(Ac);free(tau);free(v);return 4;}
    dgeqrf_(&M,&N,Ac,&LDA,tau,work,&lwqrf,&info);
    free(work);
    if(info){free(Ac);free(tau);free(v);return 5;}

    char side='L',trans='T'; lwork=-1; wq=0.0;
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,&wq,&lwork,&info);
    if(info){free(Ac);free(tau);free(v);return 6;}
    int lw=(int)wq;if(lw<1)lw=1;
    work=(double*)malloc((size_t)lw*sizeof(double));
    if(!work){free(Ac);free(tau);free(v);return 7;}
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,work,&lw,&info);
    free(work);
    if(info){free(Ac);free(tau);free(v);return 8;}

    for(int i=0;i<n;i++)v[i]=0.0;
    trans='N'; lwork=-1; wq=0.0;
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,&wq,&lwork,&info);
    if(info){free(Ac);free(tau);free(v);return 9;}
    lw=(int)wq;if(lw<1)lw=1;
    work=(double*)malloc((size_t)lw*sizeof(double));
    if(!work){free(Ac);free(tau);free(v);return 10;}
    dormqr_(&side,&trans,&M,&one,&K,Ac,&LDA,tau,v,&LDC,work,&lw,&info);
    free(work);free(Ac);free(tau);
    if(info){free(v);return 11;}

    long double yn2=0.0L;
    for(int i=0;i<m;i++){long double t=v[i];yn2+=t*t;}
    if(!(yn2>0.0L)){free(v);return 12;}
    long double inv=1.0L/sqrtl(yn2);
    for(int i=0;i<m;i++)y[i]=(double)((long double)v[i]*inv);
    free(v);return 0;
}

int bs_generate_inconsistent_witness(const double *A,const double *b,int m,int n,BSInconsistentWitness *w) {
    if(!A||!b||!w||m<=0||n<0||!finite_array(A,(size_t)m*n)||!finite_array(b,(size_t)m))return 1;
    memset(w,0,sizeof(*w));w->m=m;w->y=(double*)malloc((size_t)m*sizeof(double));
    double *x=(double*)malloc((size_t)(n>0?n:1)*sizeof(double));
    double *An=(double*)malloc((size_t)m*(size_t)(n>0?n:1)*sizeof(double));
    double *bn=(double*)malloc((size_t)m*sizeof(double));
    double *ybar=(double*)malloc((size_t)m*sizeof(double));
    long double *dmant=(long double*)malloc((size_t)m*sizeof(long double));
    int *dexp=(int*)malloc((size_t)m*sizeof(int));
    if(!w->y||!x||!An||!bn||!ybar||!dmant||!dexp){free(x);free(An);free(bn);free(ybar);free(dmant);free(dexp);bs_inconsistent_witness_free(w);return 2;}
    if(normalize_augmented_rows(A,b,m,n,An,bn,dmant,dexp)){
        free(x);free(An);free(bn);free(ybar);free(dmant);free(dexp);bs_inconsistent_witness_free(w);return 3;
    }

    /* First obtain a rank-revealing least-squares solve in normalized
       augmented coordinates.  When rank(A)=n and m>n, the n Householder
       columns span col(A), so the tail projection is a valid, very accurate
       left-null construction and remains machine-scale even arbitrarily near
       compatibility.  When rank(A)<n that argument is false: some of the
       first n Q columns are arbitrary completion directions and can erase
       genuine left-null content.  In that case the rank-revealing LS residual
       is the appropriate construction. */
    int rank=0;
    if(n>0 && least_squares_x(An,bn,m,n,x,&rank)){free(x);free(An);free(bn);free(ybar);free(dmant);free(dexp);bs_inconsistent_witness_free(w);return 4;}
    int have_y=0;
    if(rank<m){
        long double tail_rel=0.0L;
        if(left_null_projection_rank_qrcp(An,bn,m,n,rank,ybar,&tail_rel)==0 && tail_rel>256.0L*(long double)DBL_EPSILON)
            have_y=1;
        else if(left_null_vector_qrcp(An,m,n,rank,ybar)==0)
            have_y=1;
    }
    if(!have_y){
        long double yn2=0.0L,btb=0.0L;
        for(int i=0;i<m;i++){
            long double ax=0.0L;for(int j=0;j<n;j++)ax+=(long double)An[(size_t)i*n+j]*(long double)x[j];
            double yi=(double)((long double)bn[i]-ax);ybar[i]=yi;yn2+=(long double)yi*yi;btb+=(long double)bn[i]*bn[i];
        }
        if(!(yn2>0.0L)){
            if(!(btb>0.0L)){free(x);free(An);free(bn);free(ybar);free(dmant);free(dexp);bs_inconsistent_witness_free(w);return 5;}
            memcpy(ybar,bn,(size_t)m*sizeof(double));
        }
    }
    int best=-1;
    int mrc=map_augmented_left_witness(ybar,dmant,dexp,m,w->y,&best);
    /* A compatible tall system may have explicit zero augmented rows.  A
       perfectly legitimate QR completion can then return a left-null basis
       vector supported only on those zero rows; such a vector cannot certify
       finite rowwise distance because every admissible pivot has zero source
       norm.  If that happens, scan the remaining computed null directions
       until one has visible support on a positive-norm source row.  This is a
       generator availability fallback only; the strict verifier remains the
       acceptance authority. */
    if((mrc||best<0) && rank<m){
        for(int qi=rank+1;qi<m;qi++){
            if(left_null_vector_qrcp(An,m,n,qi,ybar)!=0)continue;
            long double good2=0.0L;
            for(int i=0;i<m;i++)if(dmant[i]!=0.0L){long double z=ybar[i];good2+=z*z;}
            if(!(good2>1024.0L*(long double)DBL_EPSILON*(long double)DBL_EPSILON))continue;
            best=-1;mrc=map_augmented_left_witness(ybar,dmant,dexp,m,w->y,&best);
            if(!mrc&&best>=0)break;
        }
    }
    free(x);free(An);free(bn);free(ybar);free(dmant);free(dexp);
    if(mrc||best<0){bs_inconsistent_witness_free(w);return 6;}
    w->pivot_row=best;return 0;
}

static void run_unique_profile(const double *A,const double *b,int m,int n,BSCertifiedResult *out) {
    BSUniqueWitness w={0}; double eta=INFINITY;
    int grc=bs_generate_unique_witness(A,b,m,n,&w), vrc=0;
    if(!grc) vrc=bs_verify_unique(A,b,m,n,&w,&eta);
    bs_unique_witness_free(&w);
    out->unique_generator_code=grc; out->unique_verifier_code=vrc;
    if(!grc && !vrc && isfinite(eta)){out->eta_unique=eta;out->accepted_status_mask|=1;}
}

static void run_infinite_profile(const double *A,const double *b,int m,int n,BSCertifiedResult *out) {
    BSInfiniteWitness w={0}; double eta=INFINITY;
    int grc=bs_generate_infinite_witness(A,b,m,n,&w), vrc=0;
    if(!grc) vrc=bs_verify_infinite(A,b,m,n,&w,&eta);
    bs_infinite_witness_free(&w);
    out->infinite_generator_code=grc; out->infinite_verifier_code=vrc;
    if(!grc && !vrc && isfinite(eta)){out->eta_infinite=eta;out->accepted_status_mask|=2;}
}

static void run_inconsistent_profile(const double *A,const double *b,int m,int n,BSCertifiedResult *out) {
    BSInconsistentWitness w={0}; double eta=INFINITY,lo=0.0,hi=0.0;
    int grc=bs_generate_inconsistent_witness(A,b,m,n,&w), vrc=0;
    if(!grc) vrc=bs_verify_inconsistent(A,b,m,n,&w,&lo,&hi,&eta);

    /* If y^T b is interval-indeterminate, keep the verifier unchanged but
       search tiny tilts in augmented-row-normalized coordinates.  This is the
       row-scaling-equivariant analogue of the older raw-b tilt. */
    if(!grc && vrc==4 && w.y){
        double *An=(double*)malloc((size_t)m*(size_t)(n>0?n:1)*sizeof(double));
        double *bn=(double*)malloc((size_t)m*sizeof(double));
        double *ybar0=(double*)malloc((size_t)m*sizeof(double));
        double *ycand=(double*)malloc((size_t)m*sizeof(double));
        long double *dmant=(long double*)malloc((size_t)m*sizeof(long double));
        int *dexp=(int*)malloc((size_t)m*sizeof(int));
        if(An&&bn&&ybar0&&ycand&&dmant&&dexp && !normalize_augmented_rows(A,b,m,n,An,bn,dmant,dexp)){
            /* Recover ybar proportional to D y without overflowing, then normalize it. */
            int emax=INT32_MIN;
            for(int i=0;i<m;i++)if(w.y[i]!=0.0 && dmant[i]!=0.0L){
                long double c=(long double)w.y[i]*dmant[i],ac=fabsl(c);if(!(ac>0.0L))continue;
                int ce=0;frexpl(ac,&ce);int eraw=ce+dexp[i];if(eraw>emax)emax=eraw;
            }
            long double yn2=0.0L,bn2=0.0L;
            if(emax!=INT32_MIN){
                for(int i=0;i<m;i++){
                    long double yy=0.0L;
                    if(w.y[i]!=0.0 && dmant[i]!=0.0L)
                        yy=scalbnl((long double)w.y[i]*dmant[i],dexp[i]-emax);
                    ybar0[i]=(double)yy;yn2+=yy*yy;bn2+=(long double)bn[i]*bn[i];
                }
            }
            if(yn2>0.0L && bn2>0.0L){
                long double yi=1.0L/sqrtl(yn2),bi=1.0L/sqrtl(bn2);
                for(int i=0;i<m;i++)ybar0[i]=(double)((long double)ybar0[i]*yi);
                double best_eta=INFINITY; int accepted=0;
                for(int mult=1;mult<=4096;mult*=2){
                    for(int sign=-1;sign<=1;sign+=2){
                        long double tau=(long double)sign*(long double)mult*(long double)DBL_EPSILON;
                        for(int i=0;i<m;i++)ycand[i]=(double)((long double)ybar0[i]+tau*(long double)bn[i]*bi);
                        int best=-1;if(map_augmented_left_witness(ycand,dmant,dexp,m,w.y,&best))continue;
                        w.pivot_row=best;
                        double eta_try=INFINITY,lo_try=0.0,hi_try=0.0;
                        int rc_try=bs_verify_inconsistent(A,b,m,n,&w,&lo_try,&hi_try,&eta_try);
                        if(rc_try==0 && isfinite(eta_try) && eta_try<best_eta){best_eta=eta_try;accepted=1;}
                    }
                    if(accepted){eta=best_eta;vrc=0;break;}
                }
            }
        }
        free(An);free(bn);free(ybar0);free(ycand);free(dmant);free(dexp);
    }

    bs_inconsistent_witness_free(&w);
    out->inconsistent_generator_code=grc; out->inconsistent_verifier_code=vrc;
    if(!grc && !vrc && isfinite(eta)){out->eta_inconsistent=eta;out->accepted_status_mask|=4;}
}

int bsolve_certified_api(const double *A,const double *b,const double *xt,int m,int n,int sp,int qv,int alpha,
                         unsigned long long seed,int full,BSCertifiedResult *out) {
    if(!out)return 1;
    memset(out,0,sizeof(*out));
    out->eta_x=NAN;out->eta_status=INFINITY;
    out->eta_unique=INFINITY;out->eta_infinite=INFINITY;out->eta_inconsistent=INFINITY;

    double meta[11];bsolve_router_meta_api(A,b,xt,m,n,sp,qv,alpha,seed,full,meta);
    out->fast_status=(int)meta[0];out->fast_certainty=(int)meta[1];out->rank_estimate=(int)meta[2];
    out->rank_lo=(int)meta[3];out->rank_hi=(int)meta[4];out->eta_x=meta[10];

    /* The trusted audit semantics do not depend on which type the router chose. */
    run_unique_profile(A,b,m,n,out);
    run_infinite_profile(A,b,m,n,out);
    run_inconsistent_profile(A,b,m,n,out);

    /* Compatibility projection: expose the accepted radius matching fast_status,
       but do not suppress the other independently accepted coordinates. */
    if(out->fast_status==BS_STATUS_UNIQUE){
        out->generator_code=out->unique_generator_code;out->verifier_code=out->unique_verifier_code;
        if(out->accepted_status_mask&1){out->certified_status=BS_STATUS_UNIQUE;out->eta_status=out->eta_unique;}
    }else if(out->fast_status==BS_STATUS_INFINITE){
        out->generator_code=out->infinite_generator_code;out->verifier_code=out->infinite_verifier_code;
        if(out->accepted_status_mask&2){out->certified_status=BS_STATUS_INFINITE;out->eta_status=out->eta_infinite;}
    }else if(out->fast_status==BS_STATUS_INCONSISTENT){
        out->generator_code=out->inconsistent_generator_code;out->verifier_code=out->inconsistent_verifier_code;
        if(out->accepted_status_mask&4){out->certified_status=BS_STATUS_INCONSISTENT;out->eta_status=out->eta_inconsistent;}
    }
    return 0;
}
