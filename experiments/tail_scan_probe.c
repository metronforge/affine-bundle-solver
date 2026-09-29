/* Diagnostic-only exports; production installed ABI is unchanged. */
#include "bsolver.c"

#ifdef ABS_TAIL_DIAGNOSTICS
void abs_tail_reset(void) { memset(tail_stats,0,sizeof(tail_stats)); }
void abs_tail_stats(double *out) { memcpy(out,tail_stats,sizeof(tail_stats)); }
const void *abs_tail_state(int *p) {
    *p=tail_saved_p;
    return tail_saved_live ? &tail_saved : NULL;
}
void abs_tail_release(void) {
    if(tail_saved_live)bs_free(&tail_saved);
    tail_saved_live=0;
}
#endif
/* The state is captured by the separate untimed diagnostic library. It stays
 * owned there. try_secant_tail copies it exactly as in production. */
void abs_tail_replay(const double *a,const double *b,int m,int n,int p,
                     const void *state,unsigned long long seed,double *out) {
    Result r={0};
    int rc=try_secant_tail(a,b,NULL,m,n,p,(const BState *)state,seed,2e-10,&r);
    fill_out(r,out); out[7]=rc;
}

/* Context-isolated microprobe, NOT a full production route. The included row
 * body is byte-checked against production during build. covered=m models a
 * previously covered row (four reductions only); covered=0 also updates E.
 * No selected-row insertion is performed: report every hit to the caller. */
void abs_tail_rows(const double *A,const double *b,const double *x,const double *Z,
                   int m,int n,int updates,unsigned long long seed,double *out) {
    BState s={0};s.x=(double *)x;
    double *E=calloc((size_t)2*n,sizeof(double));
    if(!E){out[0]=-1;return;}
    double f[2]={0,0},tc=2e-10,xn=norm2(x,n),invm=1.0/sqrt((double)(m?m:1));
    uint64_t vseed=sm64(seed^0x082EFA98EC4E6C89ULL);
    int i=0,covered=updates?0:m,streak=0,hits=0;
    while(i<m){int ishit=0;
#include "tail_scan_row.inc"
        hits+=ishit;i++;
    }
    out[0]=hits;out[1]=f[0];out[2]=f[1];out[3]=0;out[4]=0;
    for(int j=0;j<n;j++){out[3]+=E[j];out[4]+=E[n+j];}
    free(E);
}
