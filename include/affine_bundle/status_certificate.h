/*
 * status_certificate.h -- Proof-object types and verifier interface.
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
#ifndef STATUS_CERTIFICATE_H
#define STATUS_CERTIFICATE_H

#ifdef __cplusplus
extern "C" {
#endif

enum {
    BS_STATUS_UNIQUE = 1,
    BS_STATUS_INFINITE = 2,
    BS_STATUS_INCONSISTENT = 3,
    BS_STATUS_UNRESOLVED = 4
};

typedef struct {
    int m, n;
    int *idx;          /* n distinct source-row indices */
    double *scale;     /* n positive row scales */
    int *perm;         /* bijection: source-block row -> L/U row */
    double *packed_lu; /* row-major: strict lower L, diagonal/upper U */
    double *x;         /* n-vector */
} BSUniqueWitness;

typedef struct {
    int n;
    double *x;
    double *z;
} BSInfiniteWitness;

typedef struct {
    int m;
    double *y;
    int pivot_row;
} BSInconsistentWitness;

void bs_unique_witness_free(BSUniqueWitness *w);
void bs_infinite_witness_free(BSInfiniteWitness *w);
void bs_inconsistent_witness_free(BSInconsistentWitness *w);

/* The radius is verifier-owned.  Return 0 only when the object is accepted. */
int bs_verify_unique(const double *A, const double *b, int m, int n,
                     const BSUniqueWitness *w, double *eta_status_up);
int bs_verify_infinite(const double *A, const double *b, int m, int n,
                       const BSInfiniteWitness *w, double *eta_status_up);
/* ytb_lo/hi bound a positive power-of-two normalization of y^T b;
   their sign, not their absolute scale, is the certified diagnostic. */
int bs_verify_inconsistent(const double *A, const double *b, int m, int n,
                           const BSInconsistentWitness *w,
                           double *ytb_lo, double *ytb_hi,
                           double *eta_status_up);

#ifdef __cplusplus
}
#endif
#endif
