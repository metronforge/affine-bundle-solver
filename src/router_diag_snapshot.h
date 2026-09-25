/* Private bridge: a router result and diagnostics captured in one call. */
#ifndef ABS_ROUTER_DIAG_SNAPSHOT_H
#define ABS_ROUTER_DIAG_SNAPSHOT_H
#include "affine_bundle/router.h"

#define ABS_ROUTER_SNAPSHOT_GREY_CAP 64
typedef struct {
    double meta[ABS_OUT_LEN];
    int grey_distinct_count;
    int grey_total_events;
    int grey_rows[ABS_ROUTER_SNAPSHOT_GREY_CAP];
    double last_orth_eta;
    int core_rank_interval[2];
    int core_qr_rank;
    unsigned long long formation_guard_counters[3];
} ABSRouterSnapshot;

void abs_router_snapshot_internal(const double *A, const double *b, const double *xt,
                                  int m, int n, int sp, int qv, int alpha,
                                  unsigned long long seed, int full,
                                  ABSRouterSnapshot *snapshot);
#endif
