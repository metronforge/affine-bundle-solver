# Three semantic layers and per-call sensitivity

Operational status is a finite-precision classification under policy_used.
Exact-source status describes the exact binary-rational stored A,b and always
remains UNKNOWN / NOT_VERIFIED in production floating-point calls. The nearby
mask and eta profile independently certify existence of nearby exact systems.
Etas are upper bounds, not probabilities, confidence, votes or an argmin classifier.

BSOperationalPolicyV1 begins with size_t struct_size, then doubles named
dependence_threshold, growth_threshold, compatibility_tolerance, quality_threshold.
The canonical default helper returns 1e-13, 1e-9, 2e-10, 1e-14 respectively.
Validation requires finite positive values <=1 and dependence < growth; nothing
is clamped. Null policy is invalid. No global, TLS or environment policy exists.

```c
#include <affine_bundle/certified_api.h>
BSOperationalPolicyV1 policy = {0};
bs_default_operational_policy(&policy);
policy.compatibility_tolerance = 1e-14; /* diagnostic choice */
BSCombinedSemanticResultV1 result;
bs_init_combined_semantic_result(&result);
int rc = bsolve_certified_policy_api(A,b,NULL,m,n,1,2,2,17,0,&policy,&result);
/* Read result.operational.operational_status, operational_certainty, policy_used.
   result.operational.exact_source_status remains BS_EXACT_SOURCE_UNKNOWN.
   result.nearby_status_mask and eta_* describe nearby systems. */
```

bsolve_router_policy_api returns BSOperationalResultV1 without certificates.
bsolve_certified_policy_api returns BSCombinedSemanticResultV1, executes the router
once, and independently attempts all three proof types. certificate_profile
contains the ABI-frozen legacy nearby profile, codes and compatibility projection.
Existing API symbols, structs and enum values are unchanged. abs_thresholds and
abs_quality_threshold still query DEFAULT after any custom call.

## ABI and errors

Every new caller-allocated result also begins with struct_size. Helpers initialize
the known V1 size and prefix. An accessible allocation of at least sizeof(V1) is
required; undersized outputs are rejected without writes. Larger allocations are
accepted: unknown suffix bytes are ignored/preserved and the caller's outer output
size is retained. Embedded policy_used has the known V1 size. Callers using extended
allocations may enlarge struct_size after the initializer; never claim more bytes
than are accessible. Existing field offsets are immutable; an incompatible future
layout needs a different named version. No hidden ABI/version state is used.

Return 0 means success, 1 invalid size/policy/input, 2 router backend/resource
failure. On invalid policy/input a valid-sized result is cleared to operational
FAIL/NONE, exact UNKNOWN/NOT_VERIFIED, and empty nearby mask. Helpers themselves
require a V1-sized allocation, including when initially zeroed.

## Operational rules and routing

Exact DEFAULT values dispatch to the legacy fast router. Custom policies use the
existing normalized source-QRCP backend: mu>G counts toward rank_lo; mu>=D toward
rank_hi. An open interval or failed formation proof refuses a point rank. Closed
rank uses the selected-row witness and the source-row gate
`|a_i*x-b_i| <= tc*(|b_i|+||a_i||*(1+||x||))`; zero rows retain the absolute tc test.
Quality only controls UNIQUE witness retention: maximum rowwise error with
denominator `|b_i|+||a_i||*||x||` above quality produces UNDECIDABLE. It is not a
general exactness tolerance or a certificate acceptance threshold.

Custom routing deliberately avoids interpreting fixed compressed-proposal guards
as arbitrary D/G. A change from DEFAULT can change the route, witness, certainty,
diagnostics and status. Sweeps are operational sensitivity studies, not monotonicity
claims or pure scalar-threshold experiments. Custom source QRCP may cost more;
DEFAULT retains its fast path. Policy values are passed locally. Existing TLS
diagnostic storage is not policy state. No policy enters certificate generation
or strict verification; the theorem and eta/mask meanings remain fixed.

## Independent exact evidence

Separate enums name BS_EXACT_SOURCE_UNKNOWN/UNIQUE/INFINITE/INCONSISTENT and
BS_EXACT_VERIFY_NOT_VERIFIED/EXACT_RATIONAL/INTERVAL_PROOF/ANALYTIC_PROOF/EXTERNAL_PROOF.
The stronger levels support independent reporting; no proof-import mechanism is
implemented and the solver emits none of them. There is no CONTRACT_ORACLE_VERIFIED
level. Contract-oracle results remain separate policy assessments.

Task8A reporting can show operational INFINITE under DEFAULT, exact INCONSISTENT /
EXACT_RATIONAL from retained adjudication, contract_oracle_status INCONSISTENT, and
nearby INFINITE accepted, simultaneously. Input hashes bind independent evidence.
Original TRUE_CONTRACT_DISAGREEMENT records remain historical. A fixed sweep of
DEFAULT and compatibility 1e-12, 1e-14, 1e-16 changes operational interpretation,
not source mathematics or certificate soundness.
