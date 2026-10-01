/*
 * certified_api.h -- Public audit API: certified status profile and rank interval.
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
#ifndef CERTIFIED_API_H
#define CERTIFIED_API_H
#include "status_certificate.h"
#include "router.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int fast_status;
    int fast_certainty;
    int rank_estimate;
    int rank_lo;
    int rank_hi;

    /* NOT part of the eta profile below, despite the name.  This is a copy of
       the fast router's out[ABS_OUT_BERR]: the backward error of the router's
       own solution witness, produced by the UNTRUSTED layer, NaN outside a
       deterministic UNIQUE.  It is not a distance to a nearby exact system and
       carries none of the guarantees the eta_* fields carry. */
    double eta_x;

    /* Backward-compatible projection onto the fast router's proposed type.
       These fields are conveniences, not the primary certified semantics. */
    int certified_status; /* 0 if the router-selected proof object was not accepted */
    double eta_status;
    int generator_code;
    int verifier_code;

    /* Router-independent nearby-status profile.  A finite eta_* means that
       the corresponding proof object was independently accepted.  Each
       value is an upper bound for existence of a nearby exact system of that
       type; it is NOT a confidence score and argmin(eta_*) is not certified
       to be the exact status of the source data. */
    int accepted_status_mask; /* bit 0 unique, bit 1 infinite, bit 2 inconsistent */
    double eta_unique;
    double eta_infinite;
    double eta_inconsistent;
    int unique_generator_code;
    int unique_verifier_code;
    int infinite_generator_code;
    int infinite_verifier_code;
    int inconsistent_generator_code;
    int inconsistent_verifier_code;
} BSCertifiedResult;

#define BS_CERTIFIED_DIAG_GREY_CAP 64

#include "operational_policy.h"

/* Additive ABI: initialize using bs_init_combined_semantic_result, or supply
   struct_size >= sizeof(V1). Only the V1 prefix is written; suffix bytes survive.
   certificate_profile is the frozen legacy nearby profile/projection, NOT exact
   source evidence. Exact-source fields live in operational and remain UNKNOWN. */
typedef struct {
    size_t struct_size;
    BSOperationalResultV1 operational;
    int nearby_status_mask;
    double eta_unique, eta_infinite, eta_inconsistent;
    BSCertifiedResult certificate_profile;
} BSCombinedSemanticResultV1;
void bs_init_combined_semantic_result(BSCombinedSemanticResultV1 *out);
int bsolve_certified_policy_api(const double *A,const double *b,const double *xt,
    int m,int n,int sp,int qv,int alpha,unsigned long long seed,int full,
    const BSOperationalPolicyV1 *policy,BSCombinedSemanticResultV1 *out);

/* Standalone nearby-system evidence for one caller-supplied candidate x.
   These fields retain the existing eta-profile meaning: they bound nearby
   exact systems and do not classify the exact stored A,b. */
typedef struct {
    size_t struct_size;
    int nearby_status_mask;
    double eta_unique, eta_infinite, eta_inconsistent;
    int unique_generator_code, unique_verifier_code;
    int infinite_generator_code, infinite_verifier_code;
    int inconsistent_generator_code, inconsistent_verifier_code;
    BSExactSourceStatus exact_source_status;
    BSExactSourceVerification exact_source_verification;
} BSCertificateResultV1;

enum {
    BS_CERTIFY_OK = 0,
    BS_CERTIFY_INVALID_ARGUMENT = 1,
    BS_CERTIFY_ALLOCATION_FAILURE = 2,
    BS_CERTIFY_NUMERICAL_FAILURE = 3
};

void bs_init_certificate_result(BSCertificateResultV1 *out);

/* Attempts the established nearby-system profiles using caller-owned finite
   x for candidate-dependent witnesses.  It never invokes the router and
   never solves to reconstruct x.  Successful execution can still yield an
   empty nearby_status_mask; that is evidence not established, not an API
   execution error. */
int bs_certify_candidate(const double *A, const double *b, const double *x,
                         int m, int n, BSCertificateResultV1 *out);

/* One router result plus its same-invocation diagnostics and the independent
   three-profile certificate audit.  Unused grey_rows entries are zero.
   formation_guard_counters are per-invocation deltas: checks, escalations,
   source-QRCP calls.  No global counter reset is required. */
typedef struct {
    BSCertifiedResult certified;
    double router_meta[ABS_OUT_LEN];
    int grey_distinct_count;
    int grey_total_events;
    int grey_rows[BS_CERTIFIED_DIAG_GREY_CAP];
    double last_orth_eta;
    int core_rank_interval[2];
    int core_qr_rank;
    unsigned long long formation_guard_counters[3];
} BSCombinedCertifiedResult;

int bs_generate_unique_witness(const double *A, const double *b, int m, int n,
                               BSUniqueWitness *w);
int bs_generate_infinite_witness(const double *A, const double *b, int m, int n,
                                 BSInfiniteWitness *w);
int bs_generate_inconsistent_witness(const double *A, const double *b, int m, int n,
                                     BSInconsistentWitness *w);

/* Router status is operational. Neither it nor nearby proof acceptance establishes
   exact source status; certified_status is a legacy projection, not a source proof.
   Runs the fast router and, independently of its choice, attempts all three
   post-hoc proof-object types.  The eta_unique/eta_infinite/eta_inconsistent
   fields form the primary router-independent nearby-status profile.
   certified_status/eta_status remain a compatibility projection onto the
   router-selected type and are populated only after independent acceptance. */
int bsolve_certified_api(const double *A, const double *b, const double *xt,
                         int m, int n, int sp, int qv, int alpha,
                         unsigned long long seed, int full,
                         BSCertifiedResult *out);

/* Executes the router exactly once, snapshots all router fields before the
   three independent certificate attempts, and returns both results. xt may
   be NULL; it affects only router_meta[ABS_OUT_RELX]. The per-call snapshot
   uses the router's existing thread-local diagnostics and introduces no new
   mutable global state or process-global reset requirement. It does not
   change the library-wide concurrency contract: callers must still avoid
   concurrently sharing mutable input/output storage.

   Returns 0 on completion, 1 for invalid arguments, or 2 when the router
   reports ABS_STATUS_FAIL (for example, a resource failure). On return 1, a
   non-NULL out is zero-initialized and no router call occurs. On return 2,
   the router snapshot and attempted certificate profiles remain available.
   Positive dimensions and non-NULL A/b/out
   are required; sp, qv, alpha must be positive and their workspace extents
   representable. Zero dimensions are rejected without invoking the router.
   A and b must be finite. A
   router resource failure is reported in router_meta as ABS_STATUS_FAIL;
   independent certificate attempts retain their existing field semantics. */
int bsolve_certified_diag_api(const double *A, const double *b, const double *xt,
                              int m, int n, int sp, int qv, int alpha,
                              unsigned long long seed, int full,
                              BSCombinedCertifiedResult *out);

#ifdef __cplusplus
}
#endif
#endif
