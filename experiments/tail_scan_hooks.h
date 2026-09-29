/* Included only by the opt-in diagnostic build, after BState is defined.
 * Diagnostic calls are serial at the API level; worker counters use atomics. */
static BState tail_saved;
static int tail_saved_live, tail_saved_p;
static double tail_stats[12], tail_phase_start;
static void tail_capture(const BState *pre, int p) {
    tail_stats[0]++;
    if(tail_saved_live)bs_free(&tail_saved);
    tail_saved_live = !bs_copy(&tail_saved, pre);
    tail_saved_p=p;
    tail_stats[9]=pre->r; tail_stats[10]=p;
}
#define ABS_TAIL_ENTER(pre,p) tail_capture(pre,p)
#define ABS_TAIL_COUNT(k,v) do { _Pragma("omp atomic update") tail_stats[k]+=(v); } while(0)
#define ABS_TAIL_START() (tail_phase_start=now_sec())
#define ABS_TAIL_STOP() (tail_stats[8]+=now_sec()-tail_phase_start)
