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
