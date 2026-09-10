/*
 * bsolver.c -- Fast affine-bundle router: information-adaptive equality classification.
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
#define main bsolver_bench_embedded_main
/* Declarations of the exported entry points.  Included here so that the
   compiler checks the public header against the definitions below: a
   header nobody compiles against is a header that drifts. */
#include "affine_bundle/router.h"
#include "affine_bundle/stream.h"
#include "bsolver_core.c"
#undef main
#include <float.h>
#include <stdint.h>
#include <string.h>


/* Compressed evidence may reject a candidate or trigger source-level escalation,
   but it is never promoted directly to a source inconsistency claim. */

// out = {cls, rank, fallback, accepted, sec, relres, relx}
/* Allocation-failure policy.  On a large dense system an m*n request can
   legitimately fail, so the router must report that rather than dereference
   a null pointer.  Failure is reported as CLS_FAIL, which is deliberately
   distinct from CLS_UNDECIDABLE: it makes no claim about the data, only
   about resources.  This preserves the fail-closed rule of the paper --
   resource exhaustion is never converted into a status verdict. */
#define BS_FAIL_RESULT(res,tzero) do{ (res).cls=CLS_FAIL; (res).rank=0; \
    (res).relres=NAN; (res).relx=NAN; (res).sec=now_sec()-(tzero); }while(0)


/* Finiteness testing under -ffast-math.
 *
 * This translation unit is compiled with -ffast-math, which implies
 * -ffinite-math-only: the compiler is told NaN and infinity cannot occur and
 * is then free to fold isfinite()/isnan() to a constant.  Measured with GCC
 * 13 at -O3 -ffast-math, !isfinite(NaN) evaluates to 0 -- every such guard in
 * this file is dead code.  Clang reports the same situation as
 * -Wnan-infinity-disabled.
 *
 * Inspecting the bit pattern avoids the issue entirely because it performs no
 * floating-point comparison: an IEEE-754 binary64 value is non-finite exactly
 * when its 11 exponent bits are all set.
 *
 * The consequence of the dead guards was concrete: on input containing NaN or
 * infinity the router returned UNIQUE rather than refusing.  The certified
 * layer was unaffected (it is compiled without -ffast-math and correctly
 * returned an empty accepted-status mask), so no certificate was ever at
 * risk, but the router's own output was wrong.
 */
static inline int bs_nonfinite(double x) {
    uint64_t u;
    memcpy(&u, &x, sizeof u);
    return (int)(((u >> 52) & 0x7FFu) == 0x7FFu);
}

static int bs_any_nonfinite(const double *v, size_t k) {
    if (!v) return 0;
    for (size_t i = 0; i < k; ++i) if (bs_nonfinite(v[i])) return 1;
    return 0;
}

static void fill_out(Result r, double*out){
    out[0]=(double)r.cls; out[1]=(double)r.rank; out[2]=(double)r.fallback; out[3]=(double)r.accepted_random;
    out[4]=r.sec; out[5]=r.relres; out[6]=r.relx;
}

#include "blas_symbols.h"
extern void dgemv_(char*,int*,int*,double*,double*,int*,double*,int*,double*,double*,int*);

static double project_cgs2(double*g,const double*Q,int r,int n){
    if(r<=0)return 0.0;
    double*c=alloca((size_t)r*sizeof(double));
    if(r<96){
        /* Matrix-form CGS2 without BLAS startup: compute all coefficients from
           the same pass state, then apply the block correction.  This is the
           exact-arithmetic operator (I-Q^T Q)^2 used by the distance envelope. */
        double c2sq=0.0;
        for(int pass=0;pass<2;pass++){
            for(int k=0;k<r;k++){const double*q=Q+(size_t)k*n;c[k]=dot(g,q,n);if(pass==1)c2sq+=c[k]*c[k];}
            for(int k=0;k<r;k++){const double*q=Q+(size_t)k*n;double ck=c[k];for(int j=0;j<n;j++)g[j]-=ck*q[j];}
        }
        return sqrt(c2sq);
    }
    char T='T',N='N';int M=n,R=r,lda=n,inc=1;double one=1.0,zero=0.0,minus=-1.0,c2n=0.0;
    for(int pass=0;pass<2;pass++){dgemv_(&T,&M,&R,&one,(double*)Q,&lda,g,&inc,&zero,c,&inc);if(pass==1)c2n=norm2(c,r);dgemv_(&N,&M,&R,&minus,(double*)Q,&lda,c,&inc,&one,g,&inc);}
    return c2n;
}

static void bs_accumulate_certified_q_defect(BState*s,const double*q,double c2n,double gn){
    if(s->r<96){bs_accumulate_new_q_defect(s,q);return;}
    double eta=bs_orth_eta(s);
    /* For matrix-form pass two, Q g_2 = -(Q Q^T-I)c_2 in exact arithmetic.
       Thus the new cross-correlation norm is bounded by eta*||c_2||/||g_2||,
       plus a small working-precision guard. */
    double h=eta*(c2n/(gn+1e-300))+64.0*DBL_EPSILON;
    double dn=fabs(dot(q,q,s->n)-1.0)+64.0*DBL_EPSILON;
    s->orth_frob2 += 2.0L*(long double)h*(long double)h + (long double)dn*(long double)dn;
}



/* Single source of truth is the public header: these two are part of the
   contract, so a value here that drifted from the documented one would be a
   silent change of what a classification asserts. */
#define BS_GROW_THR ABS_GROWTH_THRESHOLD
#define BS_DEP_THR  ABS_DEPENDENCE_THRESHOLD
#define BS_SVD_DEP_THR 1e-14
/* Public: see ABS_QUALITY_THRESHOLD in <affine_bundle/router.h>.  It decides
   whether a UNIQUE classification is allowed to keep its solution witness, so
   it is part of what the status means and not a tuning constant. */
#define BS_QUALITY_THR ABS_QUALITY_THRESHOLD
static _Thread_local double g_max_orth_eta=0.0;

/* A posteriori distance envelope for the row-space distance.
   Let G=Q Q^T=I+E and eta=||E||_2<=||E||_F<1.  In exact arithmetic,
   the two-pass CGS residual (I-Q^T Q)^2 a differs from the exact
   orthogonal residual (I-P)a, P=Q^T G^{-1}Q, by exactly an operator
   perturbation whose spectral norm is ||G-I||_2^2.  Since the implementation
   tracks eta=||G-I||_F >= ||G-I||_2, eta^2 is a valid a-posteriori envelope.
   This certifies distance to span(Q), the computed basis; it does not by itself
   bound drift of span(Q) from the exact source row space.  Rows are normalized
   before this call.  A small working-precision cushion is kept separate from
   the theorem-derived orthogonality term. */
static void dependency_distance_interval(const BState*s,double muhat,double*lo,double*hi){
    double eta=bs_orth_eta(s); if(eta>g_max_orth_eta)g_max_orth_eta=eta;
    if(!isfinite(eta) || eta>=0.5){*lo=0.0;*hi=INFINITY;return;}
    double dorth=eta*eta;
    double deval=64.0*DBL_EPSILON*(1.0+eta);
    double d=dorth+deval;
    *lo=(muhat>d?muhat-d:0.0);
    *hi=muhat+d;
}

/* Independent local arbiter for a candidate dependency claim.
   The current Q rows are orthonormal row-space generators.  For r<n, append
   the normalized candidate row and inspect the smallest singular value of the
   (r+1) x n augmented row matrix.  Return 1 = safely dependent, 0 = resolved
   growth, 2 = grey/uncertain. */
static int local_dependency_svd(const BState*s,const double*a){
    int r=s->r,n=s->n;
    if(r>=n)return 1;
    int M=r+1,N=n,LDA=M,minmn=M<N?M:N,info=0,lw=-1;char ju='N',jv='N';
    double *Ac=malloc((size_t)M*N*sizeof(double));
    double *sv=malloc((size_t)minmn*sizeof(double));
    if(!Ac||!sv){free(Ac);free(sv);return 2;}
    for(int j=0;j<n;j++){
        for(int i=0;i<r;i++)Ac[i+(size_t)j*M]=s->Q[(size_t)i*n+j];
        Ac[r+(size_t)j*M]=a[j];
    }
    double du=0,dv=0,wq=0;int ldu=1,ldvt=1;
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,sv,&du,&ldu,&dv,&ldvt,&wq,&lw,&info);
    if(info){free(Ac);free(sv);return 2;}
    lw=(int)wq;if(lw<1)lw=1;double *work=malloc((size_t)lw*sizeof(double));
    for(int j=0;j<n;j++){
        for(int i=0;i<r;i++)Ac[i+(size_t)j*M]=s->Q[(size_t)i*n+j];
        Ac[r+(size_t)j*M]=a[j];
    }
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,sv,&du,&ldu,&dv,&ldvt,work,&lw,&info);
    int ans=2;
    if(!info && minmn>0 && sv[0]>0.0){
        double q=sv[minmn-1]/sv[0];
        if(q<BS_SVD_DEP_THR)ans=1;
        else if(q>BS_GROW_THR)ans=0;
    }
    free(Ac);free(sv);free(work);return ans;
}

/* Certificate-critical insertion: compatibility is interpreted only after dependency is resolved.
   Return: 1 growth, 0 redundant-compatible, -1 contradiction, 2 numerical-rank ambiguity. */
static int bs_insert_certified(BState*s,const double*a0,double beta0,double tolcon){
    int n=s->n;if(s->inconsistent)return -1;double an=norm2(a0,n);
    if(an==0){if(fabs(beta0)>tolcon){s->inconsistent=1;return -1;}return 0;}
    double*a=alloca((size_t)n*sizeof(double)),*g=alloca((size_t)n*sizeof(double));double inv=1.0/an;
    for(int j=0;j<n;j++){a[j]=a0[j]*inv;g[j]=a[j];}double beta=beta0*inv;
    double c2n=project_cgs2(g,s->Q,s->r,n);double gn=norm2(g,n),rho=beta-dot(a,s->x,n),ct=tolcon*(1.0+fabs(beta)+norm2(s->x,n));
    double mu_lo=0.0,mu_hi=0.0; dependency_distance_interval(s,gn,&mu_lo,&mu_hi);
    if(mu_lo>BS_GROW_THR){double*q=s->Q+(size_t)s->r*n;for(int j=0;j<n;j++)q[j]=g[j]/gn;bs_accumulate_certified_q_defect(s,q,c2n,gn);double al=rho/gn;for(int j=0;j<n;j++)s->x[j]+=al*q[j];s->r++;return 1;}
    if(mu_hi<BS_DEP_THR){
        if(fabs(rho)>ct){
            if(s->r==n){s->inconsistent=1;return -1;}
            int dep=local_dependency_svd(s,a);
            if(dep==1){s->inconsistent=1;return -1;}
            return 2;
        }
        return 0;
    }
    return 2;
}
/* Return 1 redundant-compatible, 0 definite growth, -1 contradiction, 2 ambiguous. */
static int bs_check_certified(const BState*s,const double*a0,double beta0,double tolcon){
    int n=s->n;double an=norm2(a0,n);if(an==0)return fabs(beta0)>tolcon?-1:1;
    double*a=alloca((size_t)n*sizeof(double)),*g=alloca((size_t)n*sizeof(double));double inv=1.0/an;
    for(int j=0;j<n;j++){a[j]=a0[j]*inv;g[j]=a[j];}double beta=beta0*inv;
    project_cgs2(g,s->Q,s->r,n);double gn=norm2(g,n),rho=beta-dot(a,s->x,n),ct=tolcon*(1.0+fabs(beta)+norm2(s->x,n));
    double mu_lo=0.0,mu_hi=0.0; dependency_distance_interval(s,gn,&mu_lo,&mu_hi);
    if(mu_lo>BS_GROW_THR)return 0;
    if(mu_hi<BS_DEP_THR){
        if(fabs(rho)>ct){
            if(s->r==n)return -1;
            return local_dependency_svd(s,a)==1?-1:2;
        }
        return 1;
    }
    return 2;
}

static Result solve_auto_qr(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,int stall_limit,uint64_t seed,int do_full_residual,int allow_corefast);
static Result solve_global_qr(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,uint64_t seed,int do_full_residual);
void bsolve_seq_api(const double*A,const double*b,const double*xt,int m,int n,double*out){ fill_out(solve_seq(A,b,xt,m,n),out); }
void bsolve_lapack_api(const double*A,const double*b,const double*xt,int m,int n,double*out){ fill_out(solve_lapack(A,b,xt,m,n),out); }
/* The historical sketch-only kernel remains available to the embedded benchmark,
   but exported production APIs are provenance-gated. */
void bsolve_fast_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out){ fill_out(solve_auto_qr(A,b,xt,m,n,sp,qv,alpha,1,(uint64_t)seed,full,0),out); }

static int compat_scan_fused(const double*A,const double*b,const double*x,int m,int n,double tc,double*rr_out);
static int reset_source_guarded(BState*s,const double*A,const double*b,int m,int n,double tc);
static int source_qrcp_trusted(const double*A,const double*b,const double*xt,int m,int n,double tc,Result*R);
static int source_closure_no_growth(const BState*s,const double*A,const double*b,int m,int n,double tc,double*rr_out);


#define BS_GREY_STORE_MAX 64
static _Thread_local int g_grey_total=0,g_grey_stored=0;
static _Thread_local int g_grey_rows[BS_GREY_STORE_MAX];
static void grey_reset(void){g_grey_total=0;g_grey_stored=0;}
static void grey_record(int row){
    if(row<0)return;
    g_grey_total++;
    for(int k=0;k<g_grey_stored;k++)if(g_grey_rows[k]==row)return;
    if(g_grey_stored<BS_GREY_STORE_MAX)g_grey_rows[g_grey_stored++]=row;
}

static _Thread_local double g_last_berr=0.0;
static _Thread_local int g_last_berr_valid=0;
static _Thread_local int g_source_rank_lo=-1,g_source_rank_hi=-1;

static int compat_scan_fused(const double*A,const double*b,const double*x,int m,int n,double tc,double*rr_out){
    long double nr=0.0L,nb=0.0L;int bad=0;double xn=norm2(x,n),berr=0.0;
    if(n>=192){
      #pragma omp parallel for if(((long long)m*n)>=1000000LL && n<384) reduction(+:nr,nb) reduction(|:bad) reduction(max:berr) schedule(static)
      for(int i=0;i<m;i++){const double*row=A+(size_t)i*n;double ax=0,an2=0;for(int j=0;j<n;j++){double v=row[j];ax+=v*x[j];an2+=v*v;}double r=ax-b[i];nr+=(long double)r*(long double)r;{long double bi=(long double)b[i];nb+=bi*bi;}double an=(an2>0.0 && finite_bits(an2))?sqrt(an2):norm2(row,n);if(an==0){if(fabs(b[i])>tc)bad=1;double den=fabs(b[i])+1e-300,be=fabs(r)/den;if(be>berr)berr=be;}else{double den=fabs(b[i])+an*xn+1e-300,be=fabs(r)/den;if(be>berr)berr=be;if(fabs(r)>tc*(fabs(b[i])+an*(1+xn)))bad=1;}}
    }else{
      #pragma omp parallel for if(((long long)m*n)>=1000000LL && n<384) reduction(+:nr,nb) reduction(|:bad) reduction(max:berr) schedule(static)
      for(int i=0;i<m;i++){const double*row=A+(size_t)i*n;double ax=0,amax=0;for(int j=0;j<n;j++){double v=row[j];ax+=v*x[j];double av=fabs(v);if(av>amax)amax=av;}double r=ax-b[i];nr+=(long double)r*(long double)r;{long double bi=(long double)b[i];nb+=bi*bi;}double cheap=tc*(fabs(b[i])+amax*(1+xn));double an=-1.0;if(fabs(r)>cheap){an=norm2(row,n);if(an==0){if(fabs(b[i])>tc)bad=1;}else if(fabs(r)>tc*(fabs(b[i])+an*(1+xn)))bad=1;}/* Quality needs a scale-invariant denominator.  Avoid DNRM2 on easy rows using ||a||_inf <= ||a||_2 <= sqrt(n)||a||_inf: if the conservative upper bound is already tiny, it cannot trigger quality repair. */
        double den_lo=fabs(b[i])+amax*xn+1e-300;double be_hi=fabs(r)/den_lo;if(be_hi>BS_QUALITY_THR){if(an<0)an=norm2(row,n);double den=fabs(b[i])+an*xn+1e-300,be=fabs(r)/den;if(be>berr)berr=be;}else if(be_hi>berr)berr=be_hi;}
    }
    g_last_berr=berr;g_last_berr_valid=1;*rr_out=(double)(sqrtl(nr)/(sqrtl(nb)+1e-300L));return bad;
}


/* Conservative source-only fallback.  It may prove growth/redundancy/contradiction,
   but it is not allowed to resolve a numerical dependency grey zone. */
static int reset_source_guarded(BState*s,const double*A,const double*b,int m,int n,double tc){
    bs_free(s);bs_init(s,n);
    for(int pass=0;pass<2;pass++){
        int amb=0,growth=0;
        for(int i=0;i<m;i++){
            int rc=bs_insert_certified(s,A+(size_t)i*n,b[i],tc); if(rc==2)grey_record(i);
            if(s->inconsistent)return 0;
            if(rc==1)growth=1; else if(rc==2)amb=1;
        }
        if(s->r==n || !amb)return 0;
        if(pass==1 || !growth){g_source_rank_lo=s->r;g_source_rank_hi=n;return 2;}
    }
    g_source_rank_lo=s->r;g_source_rank_hi=n;return 2;
}
void bsolve_global_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out){fill_out(solve_global_qr(A,b,xt,m,n,sp,qv,alpha,(uint64_t)seed,full),out);}

void bsolve_auto_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,int stall,unsigned long long seed,int full,double*out){fill_out(solve_auto_qr(A,b,xt,m,n,sp,qv,alpha,stall,(uint64_t)seed,full,0),out);}

extern void dgeqp3_(int*,int*,double*,int*,int*,double*,double*,int*,int*);
extern void dorgqr_(int*,int*,int*,double*,int*,double*,double*,int*,int*);
extern void dgels_(char*,int*,int*,int*,double*,int*,double*,int*,double*,int*,int*);
extern void dgemm_(char*,char*,int*,int*,int*,double*,double*,int*,double*,int*,double*,double*,int*);


static _Thread_local int g_core_undecidable=0;
static _Thread_local int g_last_core_qr_rank=-1;
static _Thread_local int g_core_rank_lo=-1,g_core_rank_hi=-1;
static _Thread_local unsigned long long g_fg_checks=0,g_fg_escalations=0,g_source_qrcp_calls=0;
/* Every accessor below the entry points reports state from "the most recent
   router call", so each entry point has to clear all of it, not some of it.
   g_last_core_qr_rank had no reset at all: a route that never reaches
   core_qr_state left the value from an earlier call in place, and a caller
   could read a rank belonging to a system of a different width.  Collected
   here so that adding a diagnostic global does not silently skip a reset. */
static void diag_reset(void){
    grey_reset();
    g_max_orth_eta=0.0;
    g_core_rank_lo=g_core_rank_hi=-1;
    g_last_core_qr_rank=-1;
}
static int core_has_rank_boundary(const double*Core,int rows,int n){
    int M=rows,N=n,LDA=rows,minmn=M<N?M:N,info=0; char ju='N',jv='N';
    double *Ac=malloc((size_t)M*N*sizeof(double));if(!Ac)return -1;for(int j=0;j<N;j++)for(int i=0;i<M;i++)Ac[i+(size_t)j*M]=Core[(size_t)i*n+j];
    double *sv=malloc((size_t)minmn*sizeof(double));double du=0,dv=0,wq;int ldu=1,ldvt=1,lw=-1;
    dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,sv,&du,&ldu,&dv,&ldvt,&wq,&lw,&info);lw=(int)wq;double*work=malloc((size_t)lw*sizeof(double));
    for(int j=0;j<N;j++)for(int i=0;i<M;i++)Ac[i+(size_t)j*M]=Core[(size_t)i*n+j];dgesvd_(&ju,&jv,&M,&N,Ac,&LDA,sv,&du,&ldu,&dv,&ldvt,work,&lw,&info);
    int amb=0;g_core_rank_lo=0;g_core_rank_hi=0;if(!info&&minmn&&sv[0]>0){for(int i=0;i<minmn;i++){double q=sv[i]/sv[0];if(q>1e-9)g_core_rank_lo++;if(q>1e-12)g_core_rank_hi++;if(q>=1e-12&&q<=1e-9)amb=1;}}
    free(Ac);free(sv);free(work);return amb;
}

static int core_qr_state(const double*Core,const double*y,int rows,int n,BState*out,double*relr,double ranktol,int*wpiv,double*wR,int wld,int*wvalid){
    /* QRCP of Core^T: Core^T Pi = Q R.  Since (Pi^T Core) Q_r = R_r^T,
       reuse R directly for the anchor least-squares solve instead of rebuilding Core*Q_r. */
    if(wvalid)*wvalid=0;
    int M=n,N=rows,LDA=n,info=0,minmn=M<N?M:N;
    double *AT=malloc((size_t)M*N*sizeof(double));
    for(int j=0;j<N;j++)for(int i=0;i<M;i++)AT[i+(size_t)j*M]=Core[(size_t)j*n+i];
    int *jpvt=calloc(N,sizeof(int)); double *tau=malloc((size_t)minmn*sizeof(double)); double wq; int lw=-1;
    dgeqp3_(&M,&N,AT,&LDA,jpvt,tau,&wq,&lw,&info); if(info){free(AT);free(jpvt);free(tau);return -1;} lw=(int)wq; double*work=malloc((size_t)lw*sizeof(double));
    for(int j=0;j<N;j++)for(int i=0;i<M;i++)AT[i+(size_t)j*M]=Core[(size_t)j*n+i]; memset(jpvt,0,(size_t)N*sizeof(int));
    dgeqp3_(&M,&N,AT,&LDA,jpvt,tau,work,&lw,&info); if(info){free(AT);free(jpvt);free(tau);free(work);return -1;}
    double r00=minmn?fabs(AT[0]):0; int r=0; for(int i=0;i<minmn;i++){double rii=fabs(AT[i+(size_t)i*M]); if(rii>r00*ranktol)r++; else break;}
    g_last_core_qr_rank=r; int ambiguous=0; if(r00>0){
      if(r>0){ double qmin=fabs(AT[(r-1)+(size_t)(r-1)*M])/r00; if(qmin < 100.0*ranktol) ambiguous=1; }
      if(r<minmn){ double qnext=fabs(AT[r+(size_t)r*M])/r00; if(qnext > 0.01*ranktol) ambiguous=1; }
    }
    if(!ambiguous && wpiv && wR && wld>=r){for(int j=0;j<r;j++){wpiv[j]=jpvt[j]-1;for(int i=0;i<r;i++)wR[(size_t)i*wld+j]=(i<=j)?AT[i+(size_t)j*M]:0.0;}}
    if(ambiguous){g_core_undecidable=core_has_rank_boundary(Core,rows,n);free(AT);free(jpvt);free(tau);free(work);return core_svd_state(Core,y,rows,n,out,relr,ranktol);}
    if(r==0){bs_init(out,n);double nr=norm2(y,rows),ny=nr;*relr=nr/(ny+1e-300);free(AT);free(jpvt);free(tau);free(work);return 0;}
    /* Rtop is rows x r, column-major, and rhs follows the QRCP row permutation. */
    int RR=rows,Rr=r,NRHS=1,LDB=rows>r?rows:r; double *Rtop=calloc((size_t)rows*r,sizeof(double)),*rhs=calloc((size_t)LDB,sizeof(double));
    for(int j=0;j<rows;j++){rhs[j]=y[jpvt[j]-1]; for(int i=0;i<r;i++)Rtop[j+(size_t)i*rows]=(i<=j)?AT[i+(size_t)j*M]:0.0;}
    char trans='N'; lw=-1; dgels_(&trans,&RR,&Rr,&NRHS,Rtop,&RR,rhs,&LDB,&wq,&lw,&info); if(info){free(AT);free(jpvt);free(tau);free(work);free(Rtop);free(rhs);return -1;} int lw3=(int)wq; double *work3=malloc((size_t)lw3*sizeof(double));
    /* DGELS workspace query may touch the matrix; reconstruct R^T. */
    for(int j=0;j<rows;j++)for(int i=0;i<r;i++)Rtop[j+(size_t)i*rows]=(i<=j)?AT[i+(size_t)j*M]:0.0;
    dgels_(&trans,&RR,&Rr,&NRHS,Rtop,&RR,rhs,&LDB,work3,&lw3,&info); if(info){free(AT);free(jpvt);free(tau);free(work);free(Rtop);free(rhs);free(work3);return -1;}
    int NQ=r,K=r; lw=-1; dorgqr_(&M,&NQ,&K,AT,&LDA,tau,&wq,&lw,&info); if(info){free(AT);free(jpvt);free(tau);free(work);free(Rtop);free(rhs);free(work3);return -1;} int lw2=(int)wq; double*work2=malloc((size_t)lw2*sizeof(double));
    dorgqr_(&M,&NQ,&K,AT,&LDA,tau,work2,&lw2,&info); if(info){free(AT);free(jpvt);free(tau);free(work);free(Rtop);free(rhs);free(work3);free(work2);return -1;}
    bs_init(out,n);out->r=r; for(int l=0;l<r;l++){double*q=out->Q+(size_t)l*n;double c=rhs[l];for(int j=0;j<n;j++){q[j]=AT[j+(size_t)l*n];out->x[j]+=q[j]*c;}} bs_set_backend_orth_bound(out); if(wvalid)*wvalid=1;
    double nr=0,ny=0;for(int i=0;i<rows;i++){double rr0=dot(Core+(size_t)i*n,out->x,n)-y[i];nr+=rr0*rr0;ny+=y[i]*y[i];}*relr=sqrt(nr)/(sqrt(ny)+1e-300);
    free(AT);free(jpvt);free(tau);free(work);free(Rtop);free(rhs);free(work3);free(work2);return 0;
}


/* Uniform provenance container for every row that may support a deterministic
   source-rank lower bound.  The stored row is the actual binary64 row consumed
   by the proposal backend; eps bounds its Euclidean distance from row(A). */
typedef struct { double *row,*eps; int n,used,cap; } ProofRows;
static int proof_rows_init(ProofRows *p,int n,int cap){
    if(cap<1)cap=1;p->n=n;p->used=0;p->cap=cap;
    p->row=(double*)malloc((size_t)cap*n*sizeof(double));p->eps=(double*)malloc((size_t)cap*sizeof(double));
    return p->row&&p->eps?0:-1;
}
static void proof_rows_free(ProofRows *p){if(!p)return;free(p->row);free(p->eps);memset(p,0,sizeof(*p));}
static int proof_rows_reserve(ProofRows *p,int need){
    if(need<=p->cap)return 0;int nc=p->cap;
    while(nc<need){int nn=nc+nc/2+8;if(nn<=nc)return -1;nc=nn;}
    double *nr=(double*)realloc(p->row,(size_t)nc*p->n*sizeof(double));if(!nr)return -1;p->row=nr;
    double *ne=(double*)realloc(p->eps,(size_t)nc*sizeof(double));if(!ne)return -1;p->eps=ne;p->cap=nc;return 0;
}
static int proof_rows_add_normalized(ProofRows *p,const double *raw,double raw_eps){
    int n=p->n;double an=norm2(raw,n);if(an==0.0)return 0;if(!isfinite(an))return -1;
    if(proof_rows_reserve(p,p->used+1))return -1;double mx=0.0,*dst=p->row+(size_t)p->used*n;
    for(int j=0;j<n;j++){double v=raw[j];dst[j]=v/an;double av=fabs(v);if(av>mx)mx=av;}
    p->eps[p->used]=fg_core_normalized_eps(raw_eps,mx,an,n);p->used++;return 1;
}
static int proof_rows_add_source(ProofRows *p,const double *raw){return proof_rows_add_normalized(p,raw,0.0);}

/* Proposal-independent proof step.  QRCP only chooses a convenient witness;
   fg_qr_rank_lower_bound re-checks its residual/orthogonality and provenance.
   Failure to prove is conservative: compressed evidence may not raise source rank. */
static int certified_proof_rank_lo(const ProofRows *p,int proposal){
    if(!p||proposal<=0||p->used<=0)return 0;int qdim=p->used<p->n?p->used:p->n;
    int *wpiv=(int*)malloc((size_t)qdim*sizeof(int));double *wR=(double*)calloc((size_t)qdim*qdim,sizeof(double));
    double *zero=(double*)calloc((size_t)p->used,sizeof(double));if(!wpiv||!wR||!zero){free(wpiv);free(wR);free(zero);return 0;}
    BState qst;double rr=0.0;int wvalid=0;g_core_undecidable=0;
    int rc=core_qr_state(p->row,zero,p->used,p->n,&qst,&rr,1e-11,wpiv,wR,qdim,&wvalid);
    int lo=0;if(rc==0){int rmax=proposal;if(rmax>qst.r)rmax=qst.r;if(wvalid&&rmax>0&&fg_qr_rank_certifies(p->row,p->eps,p->used,p->n,rmax,wpiv,wR,qdim,qst.Q))lo=rmax;bs_free(&qst);}
    free(wpiv);free(wR);free(zero);return lo;
}

#include "blas_symbols.h"
extern void dtrcon_(char*,char*,char*,int*,double*,int*,double*,double*,int*,int*);


/* Trusted grey-zone arbiter.
   QRCP is applied to individually normalized SOURCE rows as columns of A^T.
   Because every source row has unit norm, |R_ii| is the unexplained norm of
   the greedily selected next row.  Duplicate rows become (numerically) zero
   after the first representative and therefore do not gain rank by multiplicity.
   Return 1 if the source policy resolves rank/status, 0 if it remains unresolved,
   -1 on backend failure. */
static int source_qrcp_trusted(const double*A,const double*b,const double*xt,
                               int m,int n,double tc,Result*R){
    g_source_qrcp_calls++;
    double t0=now_sec();
    int M=n,N=m,LDA=n,minmn=M<N?M:N,info=0,lw=-1;
    double *AT=malloc((size_t)M*N*sizeof(double));
    double *yn=malloc((size_t)m*sizeof(double));
    if(!AT||!yn){free(AT);free(yn);return -1;}
    int *jpvt=calloc((size_t)N,sizeof(int));
    double *tau=malloc((size_t)minmn*sizeof(double));
    if(!AT||!yn||!jpvt||!tau){free(AT);free(yn);free(jpvt);free(tau);return -1;}
    for(int j=0;j<m;j++){
        const double *row=A+(size_t)j*n;
        double an=norm2(row,n);
        if(an==0.0){
            yn[j]=b[j];
            for(int i=0;i<n;i++)AT[i+(size_t)j*n]=0.0;
        }else{
            double inv=1.0/an; yn[j]=b[j]*inv;
            for(int i=0;i<n;i++)AT[i+(size_t)j*n]=row[i]*inv;
        }
    }
    double wq=0.0;
    dgeqp3_(&M,&N,AT,&LDA,jpvt,tau,&wq,&lw,&info);
    if(info){free(AT);free(yn);free(jpvt);free(tau);return -1;}
    lw=(int)wq; if(lw<1)lw=1;
    double *work=malloc((size_t)lw*sizeof(double));
    if(!work){free(AT);free(yn);free(jpvt);free(tau);return -1;}
    /* Workspace query may touch AT on some implementations: rebuild input. */
    for(int j=0;j<m;j++){
        const double *row=A+(size_t)j*n; double an=norm2(row,n);
        if(an==0.0){for(int i=0;i<n;i++)AT[i+(size_t)j*n]=0.0;}
        else{double inv=1.0/an;for(int i=0;i<n;i++)AT[i+(size_t)j*n]=row[i]*inv;}
    }
    memset(jpvt,0,(size_t)N*sizeof(int));
    dgeqp3_(&M,&N,AT,&LDA,jpvt,tau,work,&lw,&info);
    if(info){free(AT);free(yn);free(jpvt);free(tau);free(work);return -1;}

    int rlo=0,rhi=0;
    for(int i=0;i<minmn;i++){
        double d=fabs(AT[i+(size_t)i*n]);
        if(d>BS_GROW_THR)rlo++;
        if(d>=BS_DEP_THR)rhi++;
        if(d>=BS_DEP_THR && d<=BS_GROW_THR && jpvt[i]>0)grey_record(jpvt[i]-1);
    }
    g_source_rank_lo=rlo; g_source_rank_hi=rhi;
    if(rlo!=rhi){
        R->cls=CLS_UNDECIDABLE;R->rank=rlo;R->fallback=1;R->accepted_random=0;
        R->relres=NAN;R->relx=NAN;R->sec=now_sec()-t0;
        free(AT);free(yn);free(jpvt);free(tau);free(work);return 0;
    }
    int r=rlo;
    if(r==0){
        double *x0=calloc((size_t)n,sizeof(double));double rr=0.0;
        int bad=compat_scan_fused(A,b,x0,m,n,tc,&rr);
        R->cls=bad?CLS_INCONSISTENT:CLS_INFINITE;R->rank=0;R->fallback=1;
        R->accepted_random=0;R->relres=rr;R->relx=relxerr(x0,xt,n);R->sec=now_sec()-t0;
        free(x0);free(AT);free(yn);free(jpvt);free(tau);free(work);return 1;
    }

    /* Save R11^T before DORGQR overwrites the reflectors/upper triangle. */
    int RR=r,NRHS=1,LDB=r;
    double *Rt=calloc((size_t)r*r,sizeof(double));
    double *coef=calloc((size_t)r,sizeof(double));
    double *Ksel=malloc((size_t)r*n*sizeof(double)),*Keps=calloc((size_t)r,sizeof(double)),*Rw=calloc((size_t)r*r,sizeof(double));int *ipivw=malloc((size_t)r*sizeof(int));
    if(!Rt||!coef||!Ksel||!Keps||!Rw||!ipivw){free(Rt);free(coef);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);return -1;}
    for(int col=0;col<r;col++){
        int src=jpvt[col]-1;coef[col]=yn[src];ipivw[col]=col;const double *ar=A+(size_t)src*n;double an=norm2(ar,n),mx=0.0;
        for(int j=0;j<n;j++){double v=ar[j];Ksel[(size_t)col*n+j]=v/an;double av=fabs(v);if(av>mx)mx=av;}Keps[col]=fg_core_normalized_eps(0.0,mx,an,n);
        /* Rt = R11^T in column-major storage; Rw = R11 row-major. */
        for(int row=0;row<r;row++){double rv=(col<=row)?AT[col+(size_t)row*n]:0.0;Rt[row+(size_t)col*r]=rv;Rw[(size_t)col*r+row]=rv;}
    }
    char trans='N'; int lw3=-1; double wq3=0.0;
    dgels_(&trans,&RR,&RR,&NRHS,Rt,&RR,coef,&LDB,&wq3,&lw3,&info);
    if(info){free(Rt);free(coef);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);return -1;}
    lw3=(int)wq3;if(lw3<1)lw3=1;double *work3=malloc((size_t)lw3*sizeof(double));
    /* Rebuild R11^T after workspace query. */
    for(int col=0;col<r;col++)for(int row=0;row<r;row++)
        Rt[row+(size_t)col*r]=(col<=row)?AT[col+(size_t)row*n]:0.0;
    dgels_(&trans,&RR,&RR,&NRHS,Rt,&RR,coef,&LDB,work3,&lw3,&info);
    if(info){free(Rt);free(coef);free(work3);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);return -1;}

    int NQ=r,K=r,lw2=-1;double wq2=0.0;
    dorgqr_(&M,&NQ,&K,AT,&LDA,tau,&wq2,&lw2,&info);
    if(info){free(Rt);free(coef);free(work3);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);return -1;}
    lw2=(int)wq2;if(lw2<1)lw2=1;double *work2=malloc((size_t)lw2*sizeof(double));
    dorgqr_(&M,&NQ,&K,AT,&LDA,tau,work2,&lw2,&info);
    if(info){free(Rt);free(coef);free(work3);free(work2);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);return -1;}
    g_fg_checks++;
    if(!fg_qr_rank_certifies(Ksel,Keps,r,n,r,ipivw,Rw,r,AT)){
        g_fg_escalations++;int plo=fg_qr_rank_lower_bound(Ksel,Keps,r,n,r,ipivw,Rw,r,AT);g_source_rank_lo=plo;g_source_rank_hi=r;
        R->cls=CLS_UNDECIDABLE;R->rank=plo;R->fallback=1;R->accepted_random=0;R->relres=NAN;R->relx=NAN;R->sec=now_sec()-t0;
        free(Rt);free(coef);free(work3);free(work2);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);return 0;
    }
    double *x=calloc((size_t)n,sizeof(double));
    for(int k=0;k<r;k++){double c=coef[k];for(int j=0;j<n;j++)x[j]+=AT[j+(size_t)k*n]*c;}
    double rr=0.0;int bad=compat_scan_fused(A,b,x,m,n,tc,&rr);
    R->cls=bad?CLS_INCONSISTENT:(r==n?CLS_UNIQUE:CLS_INFINITE);
    R->rank=r;R->fallback=1;R->accepted_random=0;R->relres=rr;
    R->relx=relxerr(x,xt,n);R->sec=now_sec()-t0;
    free(x);free(Rt);free(coef);free(work3);free(work2);free(Ksel);free(Keps);free(Rw);free(ipivw);free(AT);free(yn);free(jpvt);free(tau);free(work);
    return 1;
}

/* Cheap source-level closure for a small already source-derived prefix.
   This path never promotes rank: it asks only whether every source row is
   deterministically dependent-compatible with the fixed prefix state.  Thus a
   failed compressed provenance check can be demoted to the existing source
   rank without paying for a full source QRCP when the source itself closes at
   that rank.  Return 1=closed compatible, -1=source contradiction,
   0=definite additional source direction, 2=grey. */
static int source_closure_no_growth(const BState*s,const double*A,const double*b,int m,int n,double tc,double*rr_out){
    for(int i=0;i<m;i++){
        int ck=bs_check_certified(s,A+(size_t)i*n,b[i],tc);
        if(ck==-1)return -1;
        if(ck==0)return 0;
        if(ck==2)return 2;
    }
    if(rr_out){double rr=0.0;int bad=compat_scan_fused(A,b,s->x,m,n,tc,&rr);*rr_out=rr;if(bad)return -1;}
    return 1;
}

static int try_tall_qr_unique_core(const double*Core,const double*y,int rows,int n,double*x,double*rcond_out,double*rr_out){
    if(rows<n) return 0;
    int M=rows,N=n,NRHS=1,LDA=rows,LDB=rows>n?rows:n,info=0,lw=-1; char trans='N';
    double *Ac=malloc((size_t)rows*n*sizeof(double)), *rhs=calloc((size_t)LDB,sizeof(double));
    for(int j=0;j<n;j++)for(int i=0;i<rows;i++)Ac[i+(size_t)j*rows]=Core[(size_t)i*n+j]; memcpy(rhs,y,(size_t)rows*sizeof(double));
    double wq=0; dgels_(&trans,&M,&N,&NRHS,Ac,&LDA,rhs,&LDB,&wq,&lw,&info); if(info){free(Ac);free(rhs);return 0;} lw=(int)wq; double*work=malloc((size_t)lw*sizeof(double));
    for(int j=0;j<n;j++)for(int i=0;i<rows;i++)Ac[i+(size_t)j*rows]=Core[(size_t)i*n+j]; memcpy(rhs,y,(size_t)rows*sizeof(double));
    dgels_(&trans,&M,&N,&NRHS,Ac,&LDA,rhs,&LDB,work,&lw,&info); if(info){free(Ac);free(rhs);free(work);return 0;}
    char norm='1',uplo='U',diag='N'; double rcond=0; double *w2=malloc((size_t)3*n*sizeof(double)); int *iw=malloc((size_t)n*sizeof(int));
    dtrcon_(&norm,&uplo,&diag,&N,Ac,&LDA,&rcond,w2,iw,&info); *rcond_out=rcond;
    if(info || rcond<1e-8){free(Ac);free(rhs);free(work);free(w2);free(iw);return 0;}
    double nr=0,ny=0; for(int i=0;i<rows;i++){double d=dot(Core+(size_t)i*n,rhs,n)-y[i];nr+=d*d;ny+=y[i]*y[i];} double rr=sqrt(nr)/(sqrt(ny)+1e-300);*rr_out=rr;
    if(rr>1e-11){free(Ac);free(rhs);free(work);free(w2);free(iw);return 0;}
    memcpy(x,rhs,(size_t)n*sizeof(double)); free(Ac);free(rhs);free(work);free(w2);free(iw);return 1;
}
static Result solve_auto_qr(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,int stall_limit,uint64_t seed,int do_full_residual,int allow_corefast){
 Result R={0}; double t0=now_sec(); double tr=1e-10,tc=2e-10; BState pre;bs_init(&pre,n); int p=0,stall=0;
 // Adaptive exact prefix: keep going while information keeps growing; switch after a redundancy streak.
 /* A grey (rc==2) prefix row needs no separate ambiguity flag: it does not
    raise pre.r, it is recorded by grey_record for diagnostics, and the row
    itself is re-entered below as a source row of the QRCP core, where any
    rank promotion beyond pre.r must pass fg_qr_rank_certifies.  The rank
    lower bound therefore carries the ambiguity, not a local boolean. */
 for(;p<m;p++){
   int rc=bs_insert_certified(&pre,A+(size_t)p*n,b[p],tc); if(rc==2)grey_record(p);
   if(pre.inconsistent){p++;break;}
   if(rc==2){p++;break;}
   if(rc>0) stall=0; else stall++;
   if(pre.r==n){p++;break;}
   if(stall>=stall_limit){p++;break;}
 }
 if(pre.inconsistent){R.cls=CLS_INCONSISTENT;R.rank=pre.r;R.sec=now_sec()-t0;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);bs_free(&pre);return R;}
 if(pre.r==n){double rr=0;int bad=compat_scan_fused(A,b,pre.x,m,n,tc,&rr);R.cls=bad?CLS_INCONSISTENT:CLS_UNIQUE;R.rank=n;R.sec=now_sec()-t0;R.relres=rr;R.relx=relxerr(pre.x,xt,n);bs_free(&pre);return R;}
 int dh=(n+1)-pre.r; int k=dh + dh/8 + 4;if(k<dh)k=dh;if(k>m-p)k=m-p;if(k<1)k=1;
 double*C=calloc((size_t)k*n,sizeof(double)),*d=calloc(k,sizeof(double)),*E=calloc((size_t)qv*n,sizeof(double)),*f=calloc(qv,sizeof(double));
 double*formT=calloc((size_t)k,sizeof(double));int*formL=calloc((size_t)k,sizeof(int));
 if(!C||!d||!E||!f||!formT||!formL){free(C);free(d);free(E);free(f);free(formT);free(formL);BS_FAIL_RESULT(R,t0);bs_free(&pre);return R;}
 sketch_remainder(A,b,p,m,n,k,sp,qv,seed,C,d,E,f,formT,formL,NULL,NULL);
 int crmax=p+k,cr=0;double*Core=malloc((size_t)crmax*n*sizeof(double)),*cy=malloc(crmax*sizeof(double)),*CoreEps=calloc((size_t)crmax,sizeof(double));
 if(!Core||!cy||!CoreEps){free(Core);free(cy);free(CoreEps);free(C);free(d);free(E);free(f);free(formT);free(formL);BS_FAIL_RESULT(R,t0);bs_free(&pre);return R;}
 for(int i=0;i<p;i++){double an=norm2(A+(size_t)i*n,n);if(an==0)continue;double mx=0.0;for(int j=0;j<n;j++){double v=A[(size_t)i*n+j];Core[(size_t)cr*n+j]=v/an;double av=fabs(v);if(av>mx)mx=av;}cy[cr]=b[i]/an;CoreEps[cr]=fg_core_normalized_eps(0.0,mx,an,n);cr++;}
 for(int i=0;i<k;i++){double an=norm2(C+(size_t)i*n,n);if(an==0)continue;double mx=0.0;for(int j=0;j<n;j++){double v=C[(size_t)i*n+j];Core[(size_t)cr*n+j]=v/an;double av=fabs(v);if(av>mx)mx=av;}cy[cr]=d[i]/an;double eraw=fg_sketch_formation_eps(formT[i],formL[i],n);CoreEps[cr]=fg_core_normalized_eps(eraw,mx,an,n);cr++;}
 int qdim=cr<n?cr:n;int*wpiv=malloc((size_t)(qdim>0?qdim:1)*sizeof(int));double*wR=calloc((size_t)(qdim>0?qdim:1)*(size_t)(qdim>0?qdim:1),sizeof(double));int wvalid=0;
 if(!wpiv||!wR){free(wpiv);free(wR);free(Core);free(cy);free(CoreEps);free(C);free(d);free(E);free(f);free(formT);free(formL);BS_FAIL_RESULT(R,t0);bs_free(&pre);return R;}
 /* The former unverified tall-core UNIQUE shortcut is deliberately bypassed:
    QRCP now produces the proposal and the a-posteriori provenance witness in one pass. */
 (void)allow_corefast;
 g_core_undecidable=0; BState cand;double core_rr=0;if(core_qr_state(Core,cy,cr,n,&cand,&core_rr,1e-11,wpiv,wR,qdim,&wvalid)!=0){R.fallback=1;bs_copy(&cand,&pre);int samb0=reset_source_guarded(&cand,A,b,m,n,tc);if(samb0==2){R.cls=CLS_UNDECIDABLE;R.rank=cand.r;R.relres=NAN;R.relx=NAN;R.sec=now_sec()-t0;free(Core);free(cy);free(CoreEps);free(wpiv);free(wR);free(formT);free(formL);goto done;}}
 g_fg_checks++;int form_lo=pre.r;if(wvalid && cand.r>form_lo && fg_qr_rank_certifies(Core,CoreEps,cr,n,cand.r,wpiv,wR,qdim,cand.Q))form_lo=cand.r;if(form_lo<cand.r){g_fg_escalations++;/* If only the compressed rows claim growth beyond a very small source prefix, first ask the source whether that fixed prefix already closes.  This is O(m n r_pre), never raises rank, and avoids QRCP over all m source columns in the common low-rank cancellation case. */if(pre.r<=8){double srr=0.0;int scl=source_closure_no_growth(&pre,A,b,m,n,tc,&srr);if(scl==1){R.cls=pre.r==n?CLS_UNIQUE:CLS_INFINITE;R.rank=pre.r;R.fallback=1;R.accepted_random=0;R.relres=srr;R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;free(Core);free(cy);free(CoreEps);free(wpiv);free(wR);free(formT);free(formL);goto done;}if(scl==-1){R.cls=CLS_INCONSISTENT;R.rank=pre.r;R.fallback=1;R.accepted_random=0;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;free(Core);free(cy);free(CoreEps);free(wpiv);free(wR);free(formT);free(formL);goto done;}}Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;free(Core);free(cy);free(CoreEps);free(wpiv);free(wR);free(formT);free(formL);goto done;}R.cls=CLS_UNDECIDABLE;R.rank=form_lo;R.fallback=1;R.relres=NAN;R.relx=NAN;R.sec=now_sec()-t0;free(Core);free(cy);free(CoreEps);free(wpiv);free(wR);free(formT);free(formL);goto done;}
 free(Core);free(cy);free(CoreEps);free(wpiv);free(wR);free(formT);free(formL);
 if(g_core_undecidable){/* A boundary inside a rounded compressed core need not force a global source QRCP when a small source-derived prefix already closes deterministically.  Closure can only keep the existing source rank; it never promotes it. */if(pre.r<=8){double srr=0.0;int scl=source_closure_no_growth(&pre,A,b,m,n,tc,&srr);if(scl==1){R.cls=pre.r==n?CLS_UNIQUE:CLS_INFINITE;R.rank=pre.r;R.fallback=1;R.accepted_random=0;R.relres=srr;R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto done;}if(scl==-1){R.cls=CLS_INCONSISTENT;R.rank=pre.r;R.fallback=1;R.accepted_random=0;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto done;}}R.cls=CLS_UNDECIDABLE;R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done;}
 if(core_rr>1e-8){/* A large residual of a rounded compressed core is rejection evidence, not a source contradiction.  For a very small source-derived prefix, try source closure at the already certified rank before invoking the global arbiter. */if(pre.r<=8){double srr=0.0;int scl=source_closure_no_growth(&pre,A,b,m,n,tc,&srr);if(scl==1){R.cls=pre.r==n?CLS_UNIQUE:CLS_INFINITE;R.rank=pre.r;R.fallback=1;R.accepted_random=0;R.relres=srr;R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto done;}if(scl==-1){R.cls=CLS_INCONSISTENT;R.rank=pre.r;R.fallback=1;R.accepted_random=0;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto done;}}R.cls=CLS_UNDECIDABLE;R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done;}
 if(core_rr>1e-11){if(cand.r==n){Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto done;}}R.fallback=1;int samb=reset_source_guarded(&cand,A,b,m,n,tc);R.cls=samb==2?CLS_UNDECIDABLE:(cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done;}
 int vfail=0;for(int v=0;v<qv;v++){int ck=bs_check_certified(&cand,E+(size_t)v*n,f[v],tc);if(ck!=1){vfail=1;break;}}
 if(!vfail){double rr=0;int bad=compat_scan_fused(A,b,cand.x,m,n,tc,&rr);if(bad)vfail=1;else{R.cls=(cand.r==n?CLS_UNIQUE:CLS_INFINITE);R.rank=cand.r;R.accepted_random=(cand.r==n?0:1);R.relres=rr;R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done;}}
 if(cand.r>=n-8){Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto done;}}
 R.fallback=1;int samb=reset_source_guarded(&cand,A,b,m,n,tc);R.cls=samb==2?CLS_UNDECIDABLE:(cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;
 done:free(C);free(d);free(E);free(f);bs_free(&cand);bs_free(&pre);return R;
}
void bsolve_auto_qr_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,int stall,unsigned long long seed,int full,double*out){fill_out(solve_auto_qr(A,b,xt,m,n,sp,qv,alpha,stall,(uint64_t)seed,full,1),out);}

static Result solve_global_qr(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,uint64_t seed,int do_full_residual){
    Result R={0}; double t0=now_sec(); double tr=1e-10,tc=2e-10;
    int k=alpha*(n+1); if(k>m)k=m; if(k<1)k=1;
    double*C=calloc((size_t)k*n,sizeof(double)),*d=calloc(k,sizeof(double)),*E=calloc((size_t)qv*n,sizeof(double)),*f=calloc(qv,sizeof(double));
    double*formT=calloc((size_t)k,sizeof(double));int*formL=calloc((size_t)k,sizeof(int));
    if(!C||!d||!E||!f||!formT||!formL){free(C);free(d);free(E);free(f);free(formT);free(formL);BS_FAIL_RESULT(R,t0);return R;}
    sketch_remainder(A,b,0,m,n,k,sp,qv,seed,C,d,E,f,formT,formL,NULL,NULL);
    int cr=0; double*Core=malloc((size_t)k*n*sizeof(double)),*cy=malloc(k*sizeof(double)),*CoreEps=calloc((size_t)k,sizeof(double));
    if(!Core||!cy||!CoreEps){free(Core);free(cy);free(CoreEps);free(C);free(d);free(E);free(f);free(formT);free(formL);BS_FAIL_RESULT(R,t0);return R;}
    for(int i=0;i<k;i++){ double an=norm2(C+(size_t)i*n,n); if(an==0)continue;double mx=0.0; for(int j=0;j<n;j++){double vv=C[(size_t)i*n+j];Core[(size_t)cr*n+j]=vv/an;double av=fabs(vv);if(av>mx)mx=av;} cy[cr]=d[i]/an;double eraw=fg_sketch_formation_eps(formT[i],formL[i],n);CoreEps[cr]=fg_core_normalized_eps(eraw,mx,an,n);cr++; }
    int qdim=cr<n?cr:n;int*wpiv=malloc((size_t)(qdim>0?qdim:1)*sizeof(int));double*wR=calloc((size_t)(qdim>0?qdim:1)*(size_t)(qdim>0?qdim:1),sizeof(double));int wvalid=0;
    if(!wpiv||!wR){free(wpiv);free(wR);free(Core);free(cy);free(CoreEps);free(C);free(d);free(E);free(f);free(formT);free(formL);BS_FAIL_RESULT(R,t0);return R;}
    g_core_undecidable=0; BState cand; double core_rr=0; if(core_qr_state(Core,cy,cr,n,&cand,&core_rr,1e-11,wpiv,wR,qdim,&wvalid)!=0){
        BState s;bs_init(&s,n); int samb=reset_source_guarded(&s,A,b,m,n,tc); R.fallback=1;R.cls=samb==2?CLS_UNDECIDABLE:(s.inconsistent?CLS_INCONSISTENT:(s.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=s.r;R.relres=relres(A,b,s.x,m,n);R.relx=relxerr(s.x,xt,n);R.sec=now_sec()-t0;bs_free(&s);goto done0;
    }
    g_fg_checks++;int form_lo=(wvalid&&fg_qr_rank_certifies(Core,CoreEps,cr,n,cand.r,wpiv,wR,qdim,cand.Q))?cand.r:0;if(form_lo<cand.r){g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto done1;}R.cls=CLS_UNDECIDABLE;R.rank=form_lo;R.fallback=1;R.relres=NAN;R.relx=NAN;R.sec=now_sec()-t0;goto done1;}
    if(g_core_undecidable){R.cls=CLS_UNDECIDABLE;R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done1;}
    if(core_rr>1e-8){ R.cls=CLS_UNDECIDABLE;R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done1; }
    if(core_rr>1e-11){ if(cand.r==n){Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto done1;}} R.fallback=1;int samb=reset_source_guarded(&cand,A,b,m,n,tc);R.cls=samb==2?CLS_UNDECIDABLE:(cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done1; }
    int vfail=0; for(int v=0;v<qv;v++){int ck=bs_check_certified(&cand,E+(size_t)v*n,f[v],tc);if(ck!=1){vfail=1;break;}}
    if(!vfail){double rr=0;int bad=compat_scan_fused(A,b,cand.x,m,n,tc,&rr);if(bad)vfail=1;else{R.cls=(cand.r==n?CLS_UNIQUE:CLS_INFINITE);R.rank=cand.r;R.accepted_random=(cand.r==n?0:1);R.relres=rr;R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto done1;}}
    if(cand.r>=n-8){Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto done1;}}
    R.fallback=1;int samb=reset_source_guarded(&cand,A,b,m,n,tc);R.cls=samb==2?CLS_UNDECIDABLE:(cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;
done1: bs_free(&cand);
done0: free(formT);free(formL);free(CoreEps);free(wpiv);free(wR);free(C);free(d);free(E);free(f);free(Core);free(cy);return R;
}
void bsolve_global_qr_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out){fill_out(solve_global_qr(A,b,xt,m,n,sp,qv,alpha,(uint64_t)seed,full),out);}


static int bs_insert_guarded(BState*s,const double*a0,double beta0,double tolcon){ return bs_insert_certified(s,a0,beta0,tolcon); }

static int bs_insert_tail_guarded(BState*s,const double*a0,double beta0,double tolcon,int row_index){
    /* Tail screening may be approximate, but once a row is selected for exact insertion
       it must use the same four-way certificate policy as every other source-row path. */
    int rc=bs_insert_certified(s,a0,beta0,tolcon); if(rc==2)grey_record(row_index); return rc;
}

static void secant_refresh(double*z,const BState*s,uint64_t salt){
    int n=s->n; for(int j=0;j<n;j++)z[j]=uhash(salt + 0x9e3779b97f4a7c15ULL*(uint64_t)(j+1));
    project_cgs2(z,s->Q,s->r,n);
    double zn=norm2(z,n); if(zn>0)for(int j=0;j<n;j++)z[j]/=zn;
}
static void secant_downdate(double*z,const double*q,int n,uint64_t salt,const BState*s){
    double c=dot(z,q,n);for(int j=0;j<n;j++)z[j]-=c*q[j]; double zn=norm2(z,n);
    if(zn<1e-12)secant_refresh(z,s,salt);else for(int j=0;j<n;j++)z[j]/=zn;
}
static int try_secant_tail(const double*A,const double*b,const double*xt,int m,int n,int p,const BState*pre,uint64_t seed,double tc,Result*R){
    enum{NS=2,NV=2,W=2048};uint64_t rseed=sm64(seed^0xA4093822299F31D0ULL),vseed=sm64(seed^0x082EFA98EC4E6C89ULL);BState s;bs_copy(&s,pre);double*Z=malloc((size_t)2*n*sizeof(double)),*E=calloc((size_t)2*n,sizeof(double));double f[2]={0,0};for(int t=0;t<2;t++)secant_refresh(Z+(size_t)t*n,&s,rseed+(uint64_t)(t+1)*0xD1B54A32D192ED03ULL);
    int nt=omp_get_max_threads(),parallel_ok=(pre->r>=n/2 && nt>1),i=p,streak=0,covered=p,growths=0;double invm=1.0/sqrt((double)(m-p>0?m-p:1)),xn=norm2(s.x,n);unsigned char*hit=calloc(W,1);double*LE=calloc((size_t)nt*2*n,sizeof(double)),*Lf=calloc((size_t)nt*2,sizeof(double));
    while(i<m && !s.inconsistent && s.r<n){
      int ishit=0;
      if(parallel_ok && streak>=32 && i>=covered && (long long)(m-i)*n>=1000000LL){
        int lo=i,hi=i+W;if(hi>m)hi=m;int mb=hi-lo;memset(hit,0,(size_t)mb);memset(LE,0,(size_t)nt*2*n*sizeof(double));memset(Lf,0,(size_t)nt*2*sizeof(double));
        #pragma omp parallel
        {
          int tid=omp_get_thread_num();double*e0=LE+(size_t)tid*2*n,*e1=e0+n,*ff=Lf+(size_t)tid*2;
          #pragma omp for schedule(static)
          for(int ii=0;ii<mb;ii++){int ri=lo+ii;const double*row=A+(size_t)ri*n;double an2=0,ax=0,az0=0,az1=0;for(int j=0;j<n;j++){double v=row[j];an2+=v*v;ax+=v*s.x[j];az0+=v*Z[j];az1+=v*Z[n+j];}double an=(an2>0.0 && finite_bits(an2))?sqrt(an2):norm2(row,n);if(an==0){if(fabs(b[ri])>tc)hit[ii]=1;continue;}double iv=1.0/an,beta=b[ri]*iv,w0=uhash(vseed+0x94D049BB133111EBULL*(uint64_t)(ri+1))*invm,w1=uhash(vseed+0xBF58476D1CE4E5B9ULL*(uint64_t)(ri+1))*invm,c0=w0*iv,c1=w1*iv;for(int j=0;j<n;j++){double v=row[j];e0[j]+=c0*v;e1[j]+=c1*v;}ff[0]+=w0*beta;ff[1]+=w1*beta;double rho=(b[ri]-ax)*iv,score=fmax(fabs(az0),fabs(az1))*iv,ct=tc*(1+fabs(beta)+xn);if(score>1e-12||fabs(rho)>ct)hit[ii]=1;}
        }
        for(int t=0;t<nt;t++){double*e=LE+(size_t)t*2*n,*ff=Lf+(size_t)t*2;for(int j=0;j<2*n;j++)E[j]+=e[j];f[0]+=ff[0];f[1]+=ff[1];}covered=hi;int first=-1;for(int ii=0;ii<mb;ii++)if(hit[ii]){first=ii;break;}if(first<0){i=hi;streak+=mb;continue;}i=lo+first;ishit=1;
      }else{
        const double*row=A+(size_t)i*n;double an2=0,ax=0,az0=0,az1=0;for(int j=0;j<n;j++){double v=row[j];an2+=v*v;ax+=v*s.x[j];az0+=v*Z[j];az1+=v*Z[n+j];}double an=(an2>0.0 && finite_bits(an2))?sqrt(an2):norm2(row,n);if(an==0){if(fabs(b[i])>tc)ishit=1;else{if(i>=covered){covered=i+1;}i++;streak++;continue;}}else{double iv=1.0/an,beta=b[i]*iv;if(i>=covered){double w0=uhash(vseed+0x94D049BB133111EBULL*(uint64_t)(i+1))*invm,w1=uhash(vseed+0xBF58476D1CE4E5B9ULL*(uint64_t)(i+1))*invm,c0=w0*iv,c1=w1*iv;for(int j=0;j<n;j++){double v=row[j];E[j]+=c0*v;E[n+j]+=c1*v;}f[0]+=w0*beta;f[1]+=w1*beta;covered=i+1;}double rho=(b[i]-ax)*iv,score=fmax(fabs(az0),fabs(az1))*iv,ct=tc*(1+fabs(beta)+xn);ishit=(score>1e-12||fabs(rho)>ct);if(!ishit){i++;streak++;continue;}}
      }
      if(ishit){const double*row=A+(size_t)i*n;int oldr=s.r,rc=bs_insert_tail_guarded(&s,row,b[i],tc,i);if(rc==2){bs_free(&s);free(Z);free(E);free(hit);free(LE);free(Lf);return 0;}if(s.inconsistent)break;if(rc>0){growths++;xn=norm2(s.x,n);streak=0;if(s.r==n)break;const double*q=s.Q+(size_t)oldr*n;for(int t=0;t<2;t++)secant_downdate(Z+(size_t)t*n,q,n,rseed+(uint64_t)(t+1+growths*7)*0xD1B54A32D192ED03ULL,&s);}else streak++;i++;}
    }
    free(hit);free(LE);free(Lf);
    if(s.inconsistent){R->cls=CLS_INCONSISTENT;R->rank=s.r;R->relres=relres(A,b,s.x,m,n);R->relx=relxerr(s.x,xt,n);bs_free(&s);free(Z);free(E);return 1;}
    if(s.r==n){double rr=0;int bad=compat_scan_fused(A,b,s.x,m,n,tc,&rr);R->cls=bad?CLS_INCONSISTENT:CLS_UNIQUE;R->rank=n;R->relres=rr;R->relx=relxerr(s.x,xt,n);R->accepted_random=0;bs_free(&s);free(Z);free(E);return 1;}
    for(int v=0;v<2;v++){int ck=bs_check_certified(&s,E+(size_t)v*n,f[v],tc);if(ck!=1){bs_free(&s);free(Z);free(E);return 0;}}
    {double rr=0;int bad=compat_scan_fused(A,b,s.x,m,n,tc,&rr);if(bad){bs_free(&s);free(Z);free(E);return 0;}R->cls=CLS_INFINITE;R->rank=s.r;R->relres=rr;R->relx=relxerr(s.x,xt,n);R->accepted_random=1;bs_free(&s);free(Z);free(E);return 1;}
}

static Result solve_blockprefix_qr(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,uint64_t seed,int do_full_residual){
 Result R={0}; double t0=now_sec(); int p=n<m?n:m; double tc=2e-10;
 double *Pcore=NULL,*py=NULL,*C=NULL,*d=NULL,*E=NULL,*f=NULL,*Core=NULL,*cy=NULL;
 double *formT=NULL,*valT=NULL;int *formL=NULL,*valL=NULL;BState pre={0},fcan={0},cand={0};int pre_live=0,fcan_live=0,cand_live=0;
 ProofRows proof={0};if(proof_rows_init(&proof,n,p+32)){R.cls=CLS_FAIL;return R;}
 Pcore=(double*)malloc((size_t)p*n*sizeof(double));py=(double*)malloc((size_t)p*sizeof(double));if(!Pcore||!py){R.cls=CLS_FAIL;goto cleanup;}
 int pr=0;
 for(int i=0;i<p;i++){
   const double *row=A+(size_t)i*n;double an=norm2(row,n);
   if(an==0){if(fabs(b[i])>tc){R.cls=CLS_INCONSISTENT;R.rank=0;R.relres=INFINITY;R.sec=now_sec()-t0;goto cleanup;}continue;}
   for(int j=0;j<n;j++)Pcore[(size_t)pr*n+j]=row[j]/an;py[pr]=b[i]/an;pr++;
   if(proof_rows_add_source(&proof,row)<0){R.cls=CLS_UNDECIDABLE;R.rank=0;R.fallback=1;R.sec=now_sec()-t0;goto cleanup;}
 }
 int pre_qdim=pr<n?pr:n;int *pre_piv=(int*)malloc((size_t)(pre_qdim>0?pre_qdim:1)*sizeof(int));double *pre_R=(double*)calloc((size_t)(pre_qdim>0?pre_qdim:1)*(size_t)(pre_qdim>0?pre_qdim:1),sizeof(double));int pre_wvalid=0;
 if(!pre_piv||!pre_R){free(pre_piv);free(pre_R);R.cls=CLS_FAIL;R.sec=now_sec()-t0;goto cleanup;}
 g_core_undecidable=0;double pre_rr=0;if(core_qr_state(Pcore,py,pr,n,&pre,&pre_rr,1e-11,pre_piv,pre_R,pre_qdim,&pre_wvalid)!=0){free(pre_piv);free(pre_R);R.cls=CLS_FAIL;R.sec=now_sec()-t0;goto cleanup;}pre_live=1;
 g_fg_checks++;int pre_lo=(pre_wvalid&&fg_qr_rank_certifies(Pcore,proof.eps,pr,n,pre.r,pre_piv,pre_R,pre_qdim,pre.Q))?pre.r:0;free(pre_piv);free(pre_R);
 if(pre_lo<pre.r){
   g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);
   if(qrc>=0){R=q;R.sec=now_sec()-t0;goto cleanup;}R.cls=CLS_UNDECIDABLE;R.rank=pre_lo;R.fallback=1;R.relres=NAN;R.relx=NAN;R.sec=now_sec()-t0;goto cleanup;
 }
 if(g_core_undecidable||pre_rr>1e-8){R.cls=CLS_UNDECIDABLE;R.rank=pre_lo;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}
 if(pre_rr>1e-11){R.cls=CLS_UNDECIDABLE;R.rank=pre_lo;R.relres=relres(A,b,pre.x,m,n);R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}
 if(pre.r==n){double rr=0;int bad=compat_scan_fused(A,b,pre.x,m,n,tc,&rr);R.cls=bad?CLS_INCONSISTENT:CLS_UNIQUE;R.rank=n;R.relres=rr;R.relx=relxerr(pre.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}

 /* Secant-tail remains a proposal accelerator.  Until its selected source rows are
    exported as an explicit witness, any rank growth beyond the certified prefix is
    resolved by the source arbiter rather than being silently promoted. */
 if(n>=192 && n-pre.r<=256){Result SR={0};if(try_secant_tail(A,b,xt,m,n,p,&pre,seed,tc,&SR)){
   if(SR.rank<=pre_lo){SR.sec=now_sec()-t0;R=SR;goto cleanup;}
   g_fg_checks++;g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);
   if(qrc>=0){R=q;R.sec=now_sec()-t0;goto cleanup;}R.cls=CLS_UNDECIDABLE;R.rank=pre_lo;R.fallback=1;R.relres=NAN;R.relx=NAN;R.sec=now_sec()-t0;goto cleanup;
 }}

 int dh=(n+1)-pre.r,k=dh+dh/8+4;if(k<dh)k=dh;if(k>m-p)k=m-p;if(k<1)k=1;
 C=(double*)calloc((size_t)k*n,sizeof(double));d=(double*)calloc((size_t)k,sizeof(double));E=(double*)calloc((size_t)qv*n,sizeof(double));f=(double*)calloc((size_t)qv,sizeof(double));
 formT=(double*)calloc((size_t)k,sizeof(double));formL=(int*)calloc((size_t)k,sizeof(int));valT=(double*)calloc((size_t)qv,sizeof(double));valL=(int*)calloc((size_t)qv,sizeof(int));
 if(!C||!d||!E||!f||!formT||!formL||!valT||!valL){R.cls=CLS_FAIL;R.sec=now_sec()-t0;goto cleanup;}
 sketch_remainder(A,b,p,m,n,k,sp,qv,seed,C,d,E,f,formT,formL,valT,valL);
 for(int i=0;i<k;i++){double er=fg_sketch_formation_eps(formT[i],formL[i],n);if(proof_rows_add_normalized(&proof,C+(size_t)i*n,er)<0){R.cls=CLS_UNDECIDABLE;R.rank=pre_lo;R.fallback=1;R.sec=now_sec()-t0;goto cleanup;}}
 for(int v=0;v<qv;v++){double er=fg_sketch_formation_eps(valT[v],valL[v],n);if(proof_rows_add_normalized(&proof,E+(size_t)v*n,er)<0){R.cls=CLS_UNDECIDABLE;R.rank=pre_lo;R.fallback=1;R.sec=now_sec()-t0;goto cleanup;}}

 bs_copy(&fcan,&pre);fcan_live=1;int famb=0;for(int i=0;i<k;i++){int rc=bs_insert_guarded(&fcan,C+(size_t)i*n,d[i],tc);if(rc==2){famb=1;break;}if(fcan.inconsistent)break;}
 if(!famb){
   int vf=fcan.inconsistent?2:0;fcan.inconsistent=0;
   for(int v=0;v<qv;v++){int ck=bs_check_certified(&fcan,E+(size_t)v*n,f[v],tc);if(ck!=1){vf=1;if(ck==-1||ck==2){vf=2;break;}int rc=bs_insert_guarded(&fcan,E+(size_t)v*n,f[v],tc);if(rc==2){vf=2;break;}}}
   if(fcan.inconsistent){vf=2;fcan.inconsistent=0;}
   if(!vf){double rr=0;int bad=compat_scan_fused(A,b,fcan.x,m,n,tc,&rr);if(!bad){g_fg_checks++;int lo=certified_proof_rank_lo(&proof,fcan.r);if(lo>=fcan.r){R.cls=fcan.r==n?CLS_UNIQUE:CLS_INFINITE;R.rank=fcan.r;R.accepted_random=(fcan.r==n?0:1);R.relres=rr;R.relx=relxerr(fcan.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto cleanup;}vf=2;}else vf=1;}
   for(int round=1;round<=3 && vf==1;round++){
     if(fcan.r==n){double rr=0;int bad=compat_scan_fused(A,b,fcan.x,m,n,tc,&rr);if(!bad){g_fg_checks++;int lo=certified_proof_rank_lo(&proof,n);if(lo>=n){R.cls=CLS_UNIQUE;R.rank=n;R.relres=rr;R.relx=relxerr(fcan.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto cleanup;}vf=2;break;}vf=2;break;}
     int dh2=(n+1)-fcan.r,k2=dh2+dh2/8+4;if(k2<dh2)k2=dh2;if(k2>k)k2=k;if(k2>m-p)k2=m-p;if(k2<1)k2=1;
     double *C2=(double*)calloc((size_t)k2*n,sizeof(double)),*d2=(double*)calloc((size_t)k2,sizeof(double)),*E2=(double*)calloc((size_t)qv*n,sizeof(double)),*f2=(double*)calloc((size_t)qv,sizeof(double));
     double *t2=(double*)calloc((size_t)k2,sizeof(double)),*vt2=(double*)calloc((size_t)qv,sizeof(double));int *l2=(int*)calloc((size_t)k2,sizeof(int)),*vl2=(int*)calloc((size_t)qv,sizeof(int));
     if(!C2||!d2||!E2||!f2||!t2||!vt2||!l2||!vl2){free(C2);free(d2);free(E2);free(f2);free(t2);free(vt2);free(l2);free(vl2);vf=2;break;}
     uint64_t s2=seed+(uint64_t)round*0x9e3779b97f4a7c15ULL;sketch_remainder(A,b,p,m,n,k2,sp,qv,s2,C2,d2,E2,f2,t2,l2,vt2,vl2);
     int proof_bad=0;for(int i=0;i<k2;i++){double er=fg_sketch_formation_eps(t2[i],l2[i],n);if(proof_rows_add_normalized(&proof,C2+(size_t)i*n,er)<0){proof_bad=1;break;}}
     if(!proof_bad)for(int v=0;v<qv;v++){double er=fg_sketch_formation_eps(vt2[v],vl2[v],n);if(proof_rows_add_normalized(&proof,E2+(size_t)v*n,er)<0){proof_bad=1;break;}}
     int amb2=proof_bad?1:0;if(!amb2)for(int i=0;i<k2;i++){int rc=bs_insert_guarded(&fcan,C2+(size_t)i*n,d2[i],tc);if(rc==2){amb2=1;break;}if(fcan.inconsistent){amb2=1;fcan.inconsistent=0;break;}}
     vf=amb2?2:0;if(!amb2){for(int v=0;v<qv;v++){int ck=bs_check_certified(&fcan,E2+(size_t)v*n,f2[v],tc);if(ck!=1){vf=1;if(ck==-1||ck==2){vf=2;break;}int rc=bs_insert_guarded(&fcan,E2+(size_t)v*n,f2[v],tc);if(rc==2){vf=2;break;}}}}
     free(C2);free(d2);free(E2);free(f2);free(t2);free(vt2);free(l2);free(vl2);if(fcan.inconsistent){vf=2;fcan.inconsistent=0;}
     if(vf==0){double rr=0;int bad=compat_scan_fused(A,b,fcan.x,m,n,tc,&rr);if(!bad){g_fg_checks++;int lo=certified_proof_rank_lo(&proof,fcan.r);if(lo>=fcan.r){R.cls=fcan.r==n?CLS_UNIQUE:CLS_INFINITE;R.rank=fcan.r;R.accepted_random=(fcan.r==n?0:1);R.relres=rr;R.relx=relxerr(fcan.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto cleanup;}vf=2;}else vf=1;}
   }
   if(vf!=0){R.fallback=1;int samb=reset_source_guarded(&fcan,A,b,m,n,tc);R.cls=samb==2?CLS_UNDECIDABLE:(fcan.inconsistent?CLS_INCONSISTENT:(fcan.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=fcan.r;R.relres=relres(A,b,fcan.x,m,n);R.relx=relxerr(fcan.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}
 }
 if(fcan_live){bs_free(&fcan);fcan_live=0;}

 /* Grey fast insertion falls back to the QR proposal, but the same accumulated
    provenance proof is mandatory before any QR-derived rank is accepted. */
 {int crmax=pr+k,cr=0;Core=(double*)malloc((size_t)crmax*n*sizeof(double));cy=(double*)malloc((size_t)crmax*sizeof(double));if(!Core||!cy){R.cls=CLS_FAIL;R.sec=now_sec()-t0;goto cleanup;}
  memcpy(Core,Pcore,(size_t)pr*n*sizeof(double));memcpy(cy,py,(size_t)pr*sizeof(double));cr=pr;
  for(int i=0;i<k;i++){double an=norm2(C+(size_t)i*n,n);if(an==0)continue;for(int j=0;j<n;j++)Core[(size_t)cr*n+j]=C[(size_t)i*n+j]/an;cy[cr]=d[i]/an;cr++;}
  g_core_undecidable=0;double core_rr=0;if(core_qr_state(Core,cy,cr,n,&cand,&core_rr,1e-11,NULL,NULL,0,NULL)!=0){R.cls=CLS_FAIL;R.sec=now_sec()-t0;goto cleanup;}cand_live=1;
  g_fg_checks++;int lo=certified_proof_rank_lo(&proof,cand.r);if(lo<cand.r){g_fg_escalations++;Result q={0};int qrc=source_qrcp_trusted(A,b,xt,m,n,tc,&q);if(qrc>=0){R=q;R.sec=now_sec()-t0;goto cleanup;}R.cls=CLS_UNDECIDABLE;R.rank=lo;R.fallback=1;R.relres=NAN;R.relx=NAN;R.sec=now_sec()-t0;goto cleanup;}
  if(g_core_undecidable||core_rr>1e-8){R.cls=CLS_UNDECIDABLE;R.rank=lo;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}
  if(core_rr>1e-11){R.cls=CLS_UNDECIDABLE;R.rank=lo;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}
  int vfail=0;for(int v=0;v<qv;v++){int ck=bs_check_certified(&cand,E+(size_t)v*n,f[v],tc);if(ck!=1){vfail=1;break;}}
  if(!vfail){double rr=0;int bad=compat_scan_fused(A,b,cand.x,m,n,tc,&rr);if(!bad){R.cls=cand.r==n?CLS_UNIQUE:CLS_INFINITE;R.rank=cand.r;R.accepted_random=(cand.r==n?0:1);R.relres=rr;R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;goto cleanup;}}
  R.fallback=1;int samb=reset_source_guarded(&cand,A,b,m,n,tc);R.cls=samb==2?CLS_UNDECIDABLE:(cand.inconsistent?CLS_INCONSISTENT:(cand.r==n?CLS_UNIQUE:CLS_INFINITE));R.rank=cand.r;R.relres=relres(A,b,cand.x,m,n);R.relx=relxerr(cand.x,xt,n);R.sec=now_sec()-t0;
 }
cleanup:
 if(cand_live)bs_free(&cand);if(fcan_live)bs_free(&fcan);if(pre_live)bs_free(&pre);proof_rows_free(&proof);
 free(Pcore);free(py);free(C);free(d);free(E);free(f);free(formT);free(formL);free(valT);free(valL);free(Core);free(cy);return R;
}

void bsolve_block_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out){fill_out(solve_blockprefix_qr(A,b,xt,m,n,sp,qv,alpha,(uint64_t)seed,full),out);}


#include "blas_symbols.h"
extern void dgetrf_(int*,int*,double*,int*,int*,int*);
extern void dgetrs_(char*,int*,int*,double*,int*,int*,double*,int*,int*);
extern void dgecon_(char*,int*,double*,int*,double*,double*,double*,int*,int*);


/* Meta-logic repair: status and solution quality are separate claims.
   A full-rank witness may establish UNIQUE while its anchor is not accurate enough.
   A randomized correction proposes delta; only the deterministic full-system scan
   accepts the repaired anchor. */

static int try_square_lu_unique(const double*A,const double*b,const double*xt,int m,int n,double tc,Result*R){
    if(m<n) return 0; int N=n,LDA=n,info=0; double *Ac=malloc((size_t)n*n*sizeof(double));if(!Ac)return 0; double *rhs=malloc((size_t)n*sizeof(double)); int *ipiv=malloc((size_t)n*sizeof(int)); double *rn=malloc((size_t)n*sizeof(double));
    for(int i=0;i<n;i++){rn[i]=norm2(A+(size_t)i*n,n);if(rn[i]==0){free(Ac);free(rhs);free(ipiv);free(rn);return 0;}rhs[i]=b[i]/rn[i];}
    double anorm=0.0;
    for(int j=0;j<n;j++){
        double cs=0.0;
        for(int i=0;i<n;i++){double v=A[(size_t)i*n+j]/rn[i]; Ac[i+(size_t)j*n]=v; cs+=fabs(v);}
        if(cs>anorm)anorm=cs;
    }
    dgetrf_(&N,&N,Ac,&LDA,ipiv,&info); if(info!=0){free(Ac);free(rhs);free(ipiv);free(rn);return 0;}
    char one='1'; double rcond=0.0; double *work=malloc((size_t)4*n*sizeof(double)); int *iwork=malloc((size_t)n*sizeof(int));
    dgecon_(&one,&N,Ac,&LDA,&anorm,&rcond,work,iwork,&info); if(info!=0 || rcond<1e-8){free(Ac);free(rhs);free(ipiv);free(work);free(iwork);free(rn);return 0;}
    char trans='N'; int nrhs=1,ldb=n; dgetrs_(&trans,&N,&nrhs,Ac,&LDA,ipiv,rhs,&ldb,&info); if(info!=0){free(Ac);free(rhs);free(ipiv);free(work);free(iwork);free(rn);return 0;}
    // One LU refinement on the normalized square core.
    double *corr=malloc((size_t)n*sizeof(double));
    for(int i=0;i<n;i++){const double *row=A+(size_t)i*n;double ax=0.0;for(int j=0;j<n;j++)ax+=row[j]*rhs[j];corr[i]=(b[i]-ax)/rn[i];}
    dgetrs_(&trans,&N,&nrhs,Ac,&LDA,ipiv,corr,&ldb,&info); if(info==0)for(int j=0;j<n;j++)rhs[j]+=corr[j]; free(corr);
    double rr=0; int bad=compat_scan_fused(A,b,rhs,m,n,tc,&rr);
    if(!bad && g_last_berr>BS_QUALITY_THR){R->cls=CLS_UNIQUE;R->rank=n;R->relres=rr;R->relx=relxerr(rhs,xt,n);free(Ac);free(rhs);free(ipiv);free(work);free(iwork);free(rn);return 2;}
    R->cls=bad?CLS_INCONSISTENT:CLS_UNIQUE;R->rank=n;R->relres=rr;R->relx=relxerr(rhs,xt,n);
    free(Ac);free(rhs);free(ipiv);free(work);free(iwork);free(rn);return 1;
}


/* Source-level full-rank witness used only to certify a suspected contradiction.
   Unlike a sketched core, these rows are actual equations from the source system.
   A well-conditioned full-rank subset fixes a unique x; a full source scan can
   then certify UNIQUE vs INCONSISTENT without promoting compressed residuals. */
static int try_sampled_source_fullrank(const double*A,const double*b,const double*xt,
                                       int m,int n,double tc,uint64_t seed,Result*R){
    if(m<n)return 0;
    int N=n,LDA=n,info=0;double *Ac=malloc((size_t)n*n*sizeof(double));if(!Ac)return 0;
    double *rhs=malloc((size_t)n*sizeof(double)),*rn=malloc((size_t)n*sizeof(double));
    int *ipiv=malloc((size_t)n*sizeof(int));
    if(!Ac||!rhs||!rn||!ipiv){free(Ac);free(rhs);free(rn);free(ipiv);return 0;}
    int span=m/n;if(span<1)span=1;int off=(int)(sm64(seed^0x8CB92BA72F3D8DD7ULL)%(uint64_t)span);
    int *idxs=malloc((size_t)n*sizeof(int));
    for(int i=0;i<n;i++){long long base=((long long)i*m)/n;int ix=(int)((base+off)%m);idxs[i]=ix;rn[i]=norm2(A+(size_t)ix*n,n);if(rn[i]==0.0){free(Ac);free(rhs);free(rn);free(ipiv);free(idxs);return 0;}rhs[i]=b[ix]/rn[i];}
    double anorm=0.0;
    for(int j=0;j<n;j++){double cs=0.0;for(int i=0;i<n;i++){int ix=idxs[i];double v=A[(size_t)ix*n+j]/rn[i];Ac[i+(size_t)j*n]=v;cs+=fabs(v);}if(cs>anorm)anorm=cs;}
    dgetrf_(&N,&N,Ac,&LDA,ipiv,&info);if(info){free(Ac);free(rhs);free(rn);free(ipiv);free(idxs);return 0;}
    char one='1';double rcond=0.0;double *work=malloc((size_t)4*n*sizeof(double));int *iwork=malloc((size_t)n*sizeof(int));
    dgecon_(&one,&N,Ac,&LDA,&anorm,&rcond,work,iwork,&info);
    if(info||rcond<1e-8){free(Ac);free(rhs);free(rn);free(ipiv);free(idxs);free(work);free(iwork);return 0;}
    char trans='N';int nrhs=1,ldb=n;dgetrs_(&trans,&N,&nrhs,Ac,&LDA,ipiv,rhs,&ldb,&info);
    if(info){free(Ac);free(rhs);free(rn);free(ipiv);free(idxs);free(work);free(iwork);return 0;}
    double *corr=malloc((size_t)n*sizeof(double));
    for(int i=0;i<n;i++){int ix=idxs[i];const double*row=A+(size_t)ix*n;corr[i]=(b[ix]-dot(row,rhs,n))/rn[i];}
    dgetrs_(&trans,&N,&nrhs,Ac,&LDA,ipiv,corr,&ldb,&info);if(!info)for(int j=0;j<n;j++)rhs[j]+=corr[j];
    free(corr);
    double rr=0.0;int bad=compat_scan_fused(A,b,rhs,m,n,tc,&rr);
    /* If compatible, require solution-quality as well; if incompatible the
       well-conditioned source subset already pins x, so the violated source
       equation is a source-level contradiction witness under the FP policy. */
    if(!bad && g_last_berr>BS_QUALITY_THR){free(Ac);free(rhs);free(rn);free(ipiv);free(idxs);free(work);free(iwork);return 0;}
    R->cls=bad?CLS_INCONSISTENT:CLS_UNIQUE;R->rank=n;R->fallback=1;R->accepted_random=0;
    R->relres=rr;R->relx=relxerr(rhs,xt,n);
    free(Ac);free(rhs);free(rn);free(ipiv);free(idxs);free(work);free(iwork);return 1;
}

static Result solve_router_raw(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,uint64_t seed,int do_full_residual){
    if(n < 48) return solve_auto_qr(A,b,xt,m,n,sp,qv,alpha,1,seed,do_full_residual,0);
    BState probe;bs_init(&probe,n);int target=(n<96?2:4);int p0=n<target?n:target;int allgrow=1;for(int i=0;i<p0;i++){int rc=bs_insert_certified(&probe,A+(size_t)i*n,b[i],2e-10); if(rc==2)grey_record(i);if(probe.inconsistent){Result R={0};R.cls=CLS_INCONSISTENT;R.rank=probe.r;R.relres=relres(A,b,probe.x,m,n);R.relx=relxerr(probe.x,xt,n);bs_free(&probe);return R;}if(rc!=1)allgrow=0;}bs_free(&probe);
    if(allgrow){Result fast={0};double tfast=now_sec();int frc=try_square_lu_unique(A,b,xt,m,n,2e-10,&fast);if(frc==1){fast.sec=now_sec()-tfast;return fast;}if(frc==2)return solve_global_qr(A,b,xt,m,n,sp,qv,alpha,seed,do_full_residual); if(n>=192) return solve_blockprefix_qr(A,b,xt,m,n,sp,qv,alpha,seed,do_full_residual); return solve_auto_qr(A,b,xt,m,n,sp,qv,alpha,1,seed,do_full_residual,0);}
    int allow_corefast=(n>=192 || m<8192);
    return solve_auto_qr(A,b,xt,m,n,sp,qv,alpha,1,seed,do_full_residual,allow_corefast);
}
static Result solve_router(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,uint64_t seed,int do_full_residual){
    g_source_rank_lo=g_source_rank_hi=-1;g_last_berr=0.0;g_last_berr_valid=0;Result r=solve_router_raw(A,b,xt,m,n,sp,qv,alpha,seed,do_full_residual);
    if(r.cls==CLS_UNDECIDABLE || (r.cls==CLS_INCONSISTENT && r.fallback)){
        Result t={0};
        if(try_sampled_source_fullrank(A,b,xt,m,n,2e-10,seed,&t)){t.sec=r.sec+t.sec;return t;}
        int trc=source_qrcp_trusted(A,b,xt,m,n,2e-10,&t);
        if(trc>=0){
            /* Same gate as below.  source_qrcp_trusted can return UNIQUE
               having computed a backward error but without comparing it
               against the quality threshold, so this call site used to accept
               a witness the other call site of the same helper would have
               demoted.  A UNIQUE that leaves this function must carry a
               quality certificate, on every path, or ABS_QUALITY_THRESHOLD is
               not a contract. */
            if(t.cls==CLS_UNIQUE && (!g_last_berr_valid || g_last_berr>BS_QUALITY_THR)){
                t.cls=CLS_UNDECIDABLE;t.fallback=1;t.relres=NAN;t.relx=NAN;
            }
            return t;
        }
    }
    /* A deterministic UNIQUE status and a high-quality solution witness are
       separate claims.  If the selected route did not export a rowwise mixed-2-norm
       fixed-solution quality certificate, or if that certificate fails, repair only
       the numerical witness using the trusted source QRCP backend. */
    if(r.cls==CLS_UNIQUE && (!g_last_berr_valid || g_last_berr>BS_QUALITY_THR)){
        Result q={0};
        int qrc=source_qrcp_trusted(A,b,xt,m,n,2e-10,&q);
        if(qrc>=0){
            if(q.cls==CLS_UNIQUE && (!g_last_berr_valid || g_last_berr>BS_QUALITY_THR)){
                q.cls=CLS_UNDECIDABLE;q.fallback=1;q.relres=NAN;q.relx=NAN;
            }
            return q;
        }
        /* If the quality repair itself cannot certify the source problem, do
           not silently return an uncertified UNIQUE witness. */
        if(!g_last_berr_valid || g_last_berr>BS_QUALITY_THR){r.cls=CLS_UNDECIDABLE;r.fallback=1;r.relres=NAN;r.relx=NAN;}
    }
    return r;
}
void bsolve_router_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out){
    /* Reject non-finite input at the boundary; see bs_nonfinite above for why
       the internal isfinite() guards cannot do this under -ffast-math. */
    if(m>0&&n>0&&(bs_any_nonfinite(A,(size_t)m*n)||bs_any_nonfinite(b,(size_t)m))){
        Result R={0}; BS_FAIL_RESULT(R,now_sec()); fill_out(R,out); return; }
    /* This entry point ran the router without clearing the diagnostics, so
       grey counts accumulated across calls and the accessors described a
       mixture of two systems.  It exports no diagnostics itself, but it
       shares the accessors with bsolve_router_meta_api and the header
       promises them per call. */
    diag_reset();
    fill_out(solve_router(A,b,xt,m,n,sp,qv,alpha,(uint64_t)seed,full),out);}
void bsolve_router_meta_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out){
    if(m>0&&n>0&&(bs_any_nonfinite(A,(size_t)m*n)||bs_any_nonfinite(b,(size_t)m))){
        /* fill_out writes the SEVEN-field layout, which is not this
           function's.  Writing it here put the elapsed time into
           out[4] (the upper end of the rank interval, reported as a small
           negative number) and left out[1] and out[9] at values that are not
           valid codes at all.  The meta layout is written explicitly. */
        out[0]=(double)CLS_FAIL;  out[1]=3.0;  /* certainty: none */
        out[2]=0.0; out[3]=0.0; out[4]=0.0;
        out[5]=(double)NAN; out[6]=(double)NAN;
        out[7]=0.0; out[8]=0.0;
        out[9]=(double)CLS_FAIL;
        out[10]=(double)NAN; return; }
    diag_reset();Result r=solve_router(A,b,xt,m,n,sp,qv,alpha,(uint64_t)seed,full);
    /* out[0] carries the class itself.  It used to map both CLS_FAIL and
       CLS_UNDECIDABLE onto 4, which erased the distinction the whole
       classification rests on: FAIL is a refusal on resource grounds that
       asserts nothing about the data, while UNDECIDABLE asserts that the
       data sits too close to a rank transition for a point answer and
       returns an interval instead.  The seven-field fill_out layout has
       always reported the class unmapped, so the two entry points of this
       library disagreed about the meaning of their first field. */
    int status=(int)r.cls;
    int certainty=((r.cls==CLS_UNDECIDABLE||r.cls==CLS_FAIL)?3:(r.accepted_random?2:1));
    int lo,hi;
    if(r.cls==CLS_UNDECIDABLE && g_source_rank_lo>=0){lo=g_source_rank_lo;hi=g_source_rank_hi;}
    else if(r.cls==CLS_UNDECIDABLE && g_core_rank_lo>=0){lo=g_core_rank_lo;hi=g_core_rank_hi;}
    else if(r.accepted_random){lo=r.rank;hi=(m<n?m:n);}
    else{lo=r.rank;hi=r.rank;}
    out[0]=status;out[1]=certainty;out[2]=r.rank;out[3]=lo;out[4]=hi;
    /* INCONSISTENT and UNDECIDABLE statuses export no solution witness.
       out[5] may still carry a residual diagnostic for INCONSISTENT, but out[6]
       is a solution/reference-solution error and is therefore semantically absent
       for both statuses.  A deterministic UNIQUE result is accepted only after a
       rowwise mixed-2-norm fixed-solution quality certificate has been computed;
       out[10] is finite only when that witness is actually claimed. */
    out[5]=((r.cls==CLS_FAIL||r.cls==CLS_UNDECIDABLE)?NAN:r.relres);
    out[6]=((r.cls==CLS_INCONSISTENT||r.cls==CLS_FAIL||r.cls==CLS_UNDECIDABLE)?NAN:r.relx);
    out[7]=r.sec;out[8]=r.fallback;out[9]=r.cls;
    out[10]=(certainty==1 && r.cls==CLS_UNIQUE && g_last_berr_valid)?g_last_berr:NAN;
}


/* Extended diagnostic API.  The 11-element out vector has the same semantics
   as bsolve_router_meta_api.  The return value is the number of distinct grey
   source-row indices retained by the diagnostic buffer; up to grey_cap of
   those indices are copied into grey_rows.  bsolve_last_grey_total_api()
   exposes the total number of grey events, including repeats. */
int bsolve_router_diag_api(const double*A,const double*b,const double*xt,int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,double*out,int*grey_rows,int grey_cap){
    bsolve_router_meta_api(A,b,xt,m,n,sp,qv,alpha,seed,full,out);
    int k=g_grey_stored<grey_cap?g_grey_stored:grey_cap;
    if(grey_rows && grey_cap>0)for(int i=0;i<k;i++)grey_rows[i]=g_grey_rows[i];
    return g_grey_stored;
}
int bsolve_last_grey_total_api(void){return g_grey_total;}
double bsolve_last_orth_eta_api(void){return g_max_orth_eta;}

void bsolve_fg_counters_reset_api(void){g_fg_checks=0;g_fg_escalations=0;g_source_qrcp_calls=0;}
void bsolve_fg_counters_api(unsigned long long*out){if(!out)return;out[0]=g_fg_checks;out[1]=g_fg_escalations;out[2]=g_source_qrcp_calls;}
void bsolve_last_core_rank_interval_api(int*out){if(!out)return;out[0]=g_core_rank_lo;out[1]=g_core_rank_hi;}
int bsolve_last_core_qr_rank_api(void){return g_last_core_qr_rank;}

/* ==========================================================================
 * Incremental classification API.  See include/affine_bundle/stream.h.
 *
 * This wraps bs_insert_certified, not bs_insert: the threshold routine
 * always produces a verdict, including across the band where the interval
 * routine declines, and shipping it as the library's only streaming
 * interface would put a decision with nothing behind it at the front of the
 * API.
 *
 * The per-row scratch inside bs_insert_certified is alloca'd and therefore
 * proportional to n.  That is safe here only because abs_stream_create
 * checks its own O(n^2) allocation first: an n large enough to overflow the
 * stack with 2n doubles needs a Q of n^2 doubles, which fails long before.
 * ========================================================================== */

struct ABSStream {
    BState    s;
    int       n;
    int       closed;      /* a contradiction was seen; state is final */
    long long seen;
    long long deferred;
    double    tolcon;
};

ABSStream *abs_stream_create(int n)
{
    ABSStream *st;
    if (n <= 0) return NULL;
    st = (ABSStream*)calloc(1, sizeof(*st));
    if (!st) return NULL;

    /* bs_init does not report failure, so the allocation is done here where
       it can be checked.  Q is n*n doubles. */
    st->s.n = n;
    st->s.r = 0;
    st->s.inconsistent = 0;
    st->s.orth_frob2 = 0.0L;
    st->s.Q = (double*)calloc((size_t)n * (size_t)n, sizeof(double));
    st->s.x = (double*)calloc((size_t)n, sizeof(double));
    if (!st->s.Q || !st->s.x) {
        free(st->s.Q); free(st->s.x); free(st);
        return NULL;
    }
    st->n = n;
    st->closed = 0;
    st->seen = 0;
    st->deferred = 0;
    /* The value the batch sequential path uses.  Deliberately not a
       parameter: a caller-chosen constant would make the classification a
       function of that choice. */
    st->tolcon = 2e-10;
    return st;
}

void abs_stream_destroy(ABSStream *st)
{
    if (!st) return;
    free(st->s.Q);
    free(st->s.x);
    free(st);
}

int abs_stream_insert(ABSStream *st, const double *row, double rhs)
{
    int rc;
    if (!st || !row) return ABS_INSERT_EINVAL;

    /* Same boundary check as the batch entry points, and for the same
       reason: this translation unit is compiled with -ffast-math, under
       which the compiler may fold isfinite() to a constant, and does. */
    if (bs_any_nonfinite(row, (size_t)st->n) || bs_any_nonfinite(&rhs, 1))
        return ABS_INSERT_EINVAL;

    if (st->closed) return ABS_INSERT_CONTRA;

    st->seen++;
    rc = bs_insert_certified(&st->s, row, rhs, st->tolcon);

    if (rc == -1) { st->closed = 1; return ABS_INSERT_CONTRA; }
    if (rc ==  2) { st->deferred++; return ABS_INSERT_DEFER;  }
    return rc; /* 1 grow, 0 absorb */
}

void abs_stream_status(const ABSStream *st, double *out)
{
    int i, r, lo, hi, cls;
    if (!out) return;
    for (i = 0; i < ABS_OUT_LEN; i++) out[i] = 0.0;
    out[ABS_OUT_RELRES] = (double)NAN;
    out[ABS_OUT_RELX]   = (double)NAN;
    out[ABS_OUT_BERR]   = (double)NAN;
    if (!st) { out[ABS_OUT_STATUS] = 4; out[ABS_OUT_CLS] = ABS_CLS_FAIL;
               out[ABS_OUT_CERTAINTY] = ABS_CERTAINTY_NONE; return; }

    r = st->s.r;

    if (st->closed || st->s.inconsistent) {
        /* A contradiction, once established, cannot be undone by rows that
           were never resolved: no addition makes an inconsistent system
           consistent.  So INCONSISTENT stands even with rows deferred, while
           the rank stays an interval, because those rows may still have been
           independent. */
        long long h = (long long)r + st->deferred;
        cls = ABS_CLS_INCONSISTENT;
        lo = r;
        hi = (h > (long long)st->n) ? st->n : (int)h;
    } else if (st->deferred > 0) {
        /* Sound both ways: the inserted rows are a subset of the rows seen,
           so r is a lower bound; d deferred rows lift the rank by at most d. */
        long long h = (long long)r + st->deferred;
        cls = ABS_CLS_UNDECIDABLE;
        lo = r;
        hi = (h > (long long)st->n) ? st->n : (int)h;
    } else if (r >= st->n) {
        cls = ABS_CLS_UNIQUE; lo = r; hi = r;
    } else {
        cls = ABS_CLS_INFINITE; lo = r; hi = r;
    }

    out[ABS_OUT_CLS]     = (double)cls;
    out[ABS_OUT_STATUS]  = (double)cls;   /* the two fields agree; see router.h */
    out[ABS_OUT_CERTAINTY] = (double)(cls == ABS_CLS_UNDECIDABLE
                                      ? ABS_CERTAINTY_NONE
                                      : ABS_CERTAINTY_DETERMINISTIC);
    out[ABS_OUT_RANK]    = (double)r;
    out[ABS_OUT_RANK_LO] = (double)lo;
    out[ABS_OUT_RANK_HI] = (double)hi;
}

void abs_stream_counts(const ABSStream *st, long long *seen, long long *deferred)
{
    if (!st) return;
    if (seen)     *seen     = st->seen;
    if (deferred) *deferred = st->deferred;
}

int abs_stream_solution(const ABSStream *st, double *x)
{
    int j;
    if (!st || !x) return 0;
    if (st->closed || st->s.inconsistent || st->deferred > 0) return 0;
    for (j = 0; j < st->n; j++) x[j] = st->s.x[j];
    return 1;
}

/* Reports the values this shared object was actually built with, so a caller
   can detect a header that does not match the library it linked against. */
void abs_thresholds(double *dependence, double *growth)
{
    if (dependence) *dependence = ABS_DEPENDENCE_THRESHOLD;
    if (growth)     *growth     = ABS_GROWTH_THRESHOLD;
}

/* Companion to abs_thresholds().  Separate function rather than a third
   parameter there: that entry point is already published, and widening it
   would break every caller compiled against the earlier header. */
double abs_quality_threshold(void)
{
    return ABS_QUALITY_THRESHOLD;
}
