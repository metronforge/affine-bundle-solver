/* Recompile the same router source with a test-only hook, not installed. */
#include <affine_bundle/certified_api.h>
#include "router_diag_snapshot.h"
#include <stdio.h>

static _Thread_local unsigned long long executions;
static int force_failure;
int abs_test_router_execution_hook(void) { ++executions; return force_failure; }
void abs_test_grey_capacity_fixture(ABSRouterSnapshot *snapshot);

int main(void)
{
    const double A[]={1,0,0,1}, b[]={2,3};
    BSCertifiedResult old;
    BSCombinedCertifiedResult combined;
    ABSRouterSnapshot fixture;
    if (bsolve_certified_diag_api(A,b,NULL,2,2,1,2,2,3,0,&combined) ||
        executions != 1) {
        fprintf(stderr,"combined call performed %llu router executions\n",executions);
        return 1;
    }
    if (bsolve_certified_api(A,b,NULL,2,2,1,2,2,3,0,&old) || executions != 2) {
        fputs("legacy router execution count changed\n",stderr);
        return 1;
    }
    if (!bsolve_certified_diag_api(NULL,b,NULL,2,2,1,2,2,3,0,&combined) ||
        executions != 2) {
        fputs("invalid call executed router\n",stderr);
        return 1;
    }
    force_failure=1;
    if (bsolve_certified_diag_api(A,b,NULL,2,2,1,2,2,3,0,&combined) != 2 ||
        executions != 3 ||
        combined.router_meta[ABS_OUT_STATUS] != ABS_STATUS_FAIL ||
        combined.certified.fast_status != ABS_STATUS_FAIL ||
        combined.grey_distinct_count != 0 || combined.grey_total_events != 0 ||
        combined.core_rank_interval[0] != -1 || combined.core_rank_interval[1] != -1 ||
        combined.core_qr_rank != -1 ||
        combined.formation_guard_counters[0] != 0 ||
        combined.formation_guard_counters[1] != 0 ||
        combined.formation_guard_counters[2] != 0 ||
        !(combined.certified.accepted_status_mask & 1)) {
        fputs("router failure did not return initialized diagnostic result\n",stderr);
        return 1;
    }
    force_failure=0;
    abs_test_grey_capacity_fixture(&fixture);
    if (fixture.grey_distinct_count != ABS_ROUTER_SNAPSHOT_GREY_CAP ||
        fixture.grey_total_events != 72 || fixture.grey_rows[0] != 7 ||
        fixture.grey_rows[1] != 0 || fixture.grey_rows[63] != 63) {
        fprintf(stderr,"grey capacity fixture failed: distinct=%d total=%d last=%d\n",
                fixture.grey_distinct_count,fixture.grey_total_events,fixture.grey_rows[63]);
        return 1;
    }
    puts("one router execution and grey capacity: PASS");
    return 0;
}
