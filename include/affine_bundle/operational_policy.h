#ifndef BS_OPERATIONAL_POLICY_H
#define BS_OPERATIONAL_POLICY_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Size is the accessible caller allocation, at least sizeof(V1). Future appended
   bytes are ignored/preserved, never read/written by V1. Offsets are immutable.
   Incompatible layouts require a new named type. Helpers write only V1 bytes
   and initialize struct_size; callers allocating extensions may then enlarge it. */
typedef struct {
    size_t struct_size;
    double dependence_threshold, growth_threshold;
    double compatibility_tolerance, quality_threshold;
} BSOperationalPolicyV1;

typedef enum {
    BS_EXACT_SOURCE_UNKNOWN=0, BS_EXACT_SOURCE_UNIQUE=1,
    BS_EXACT_SOURCE_INFINITE=2, BS_EXACT_SOURCE_INCONSISTENT=3
} BSExactSourceStatus;
typedef enum {
    BS_EXACT_VERIFY_NOT_VERIFIED=0, BS_EXACT_VERIFY_EXACT_RATIONAL=1,
    BS_EXACT_VERIFY_INTERVAL_PROOF=2, BS_EXACT_VERIFY_ANALYTIC_PROOF=3,
    BS_EXACT_VERIFY_EXTERNAL_PROOF=4
} BSExactSourceVerification;
enum { BS_POLICY_OK=0, BS_POLICY_INVALID_ARGUMENT=1, BS_POLICY_SOLVER_FAILED=2 };

typedef struct {
    size_t struct_size;
    BSOperationalPolicyV1 policy_used;
    int operational_status, operational_certainty;
    BSExactSourceStatus exact_source_status;
    BSExactSourceVerification exact_source_verification;
    /* Same positions as ABS_OUT_*; elapsed time is not an equivalence field. */
    double router_meta[11];
    int grey_distinct_count, grey_total_events, grey_rows[64];
    double last_orth_eta;
    int core_rank_interval[2], core_qr_rank;
    unsigned long long formation_guard_counters[3];
} BSOperationalResultV1;

void bs_default_operational_policy(BSOperationalPolicyV1 *policy);
int bs_validate_operational_policy(const BSOperationalPolicyV1 *policy);
void bs_init_operational_result(BSOperationalResultV1 *out);

/* All four thresholds finite and positive, <=1, dependence < growth.
   NULL policy, insufficient sizes, invalid input: INVALID_ARGUMENT; no solve.
   A valid-sized result is cleared to operational FAIL/NONE, exact UNKNOWN.
   Undersized results are left untouched. Default uses legacy routing; custom
   policies use normalized source QRCP and the stated rowwise compatibility rule.
   Neither route establishes exact-source status. No policy global/setter exists. */
int bsolve_router_policy_api(const double *A,const double *b,const double *xt,
    int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,
    const BSOperationalPolicyV1 *policy,BSOperationalResultV1 *out);
#ifdef __cplusplus
}
#endif
#endif
