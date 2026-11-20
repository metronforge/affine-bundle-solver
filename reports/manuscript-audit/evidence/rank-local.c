/* Calls file-local helpers in the audited source. Compile to an object with the
 * fast router flags, then link without -ffast-math, as for the release build. */
#include "bsolver.c"

/* Log the divisor actually received by the strict function. */
static volatile double divisor_used;
extern double __real_fg_core_normalized_eps(double, double, double, int);
double __wrap_fg_core_normalized_eps(double e,double mx,double divisor,int n) {
    divisor_used=divisor;
    return __real_fg_core_normalized_eps(e,mx,divisor,n);
}
int main(int argc,char **argv) {
    double q[]={1,0x1p-27};
    BState s;
    if(bs_init(&s,2))return 2;
    bs_accumulate_new_q_defect(&s,q);
    printf("stored q=(1,2^-27) computed Gram defect=%a exact=0x1p-54\n",
           bs_orth_eta(&s));
    bs_free(&s);
    const double edges[]={1e-12,1e-9};
    for (int i=0;i<2;++i) {
        double diag[]={1,0,0,edges[i]};
        int amb=core_has_rank_boundary(diag,2,2);
        printf("diagonal core ratio=%.17g ambiguous=%d core=[%d,%d]\n",
               edges[i],amb,g_core_rank_lo,g_core_rank_hi);
    }
    const int n=9;
    double raw[9];
    const double v=strtod(argc==2 ? argv[1] : "0x1.f4c4962e56146p+0",NULL);
    for(int j=0;j<n;++j) raw[j]=v;
    ProofRows proof={0};
    if(proof_rows_init(&proof,n,1))return 2;
    if(proof_rows_add_normalized(&proof,raw,0)!=1)return 3;
    printf("normalized vector n=%d raw=%a divisor=%a eps=%a stored=",n,v,
           divisor_used,proof.eps[0]);
    for(int j=0;j<n;++j) printf(" %a",proof.row[j]);
    puts("");
    proof_rows_free(&proof);
    return 0;
}
