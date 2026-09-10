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

int bs_generate_unique_witness(const double *A, const double *b, int m, int n,
                               BSUniqueWitness *w);
int bs_generate_infinite_witness(const double *A, const double *b, int m, int n,
                                 BSInfiniteWitness *w);
int bs_generate_inconsistent_witness(const double *A, const double *b, int m, int n,
                                     BSInconsistentWitness *w);

/* Runs the fast router and, independently of its choice, attempts all three
   post-hoc proof-object types.  The eta_unique/eta_infinite/eta_inconsistent
   fields form the primary router-independent nearby-status profile.
   certified_status/eta_status remain a compatibility projection onto the
   router-selected type and are populated only after independent acceptance. */
int bsolve_certified_api(const double *A, const double *b, const double *xt,
                         int m, int n, int sp, int qv, int alpha,
                         unsigned long long seed, int full,
                         BSCertifiedResult *out);

#ifdef __cplusplus
}
#endif
#endif
