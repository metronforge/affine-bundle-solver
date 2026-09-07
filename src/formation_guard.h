/*
 * formation_guard.h -- Formation-provenance checker interface.
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
#ifndef AFFINE_BUNDLE_FORMATION_GUARD_H
#define AFFINE_BUNDLE_FORMATION_GUARD_H

/* Strict/outward helpers are compiled without fast-math. */
double fg_up_mul_add(double acc, double a, double b);
double fg_up_add(double a, double b);
double fg_row_norm_upper_from_max(double maxabs, int n);
double fg_sketch_formation_eps(double term_norm_sum_up, int term_count, int n);
double fg_core_normalized_eps(double raw_eps, double raw_maxabs,
                              double divisor, int n);

/* Certified source-rank lower bound from an a-posteriori QR/provenance witness.
   QRCP selects the proposal rows, but the proof uses only checked residual,
   checked Q orthogonality, and source-formation budgets. */
int fg_qr_rank_lower_bound(const double *core, const double *core_eps,
                           int rows, int n, int candidate_rank,
                           const int *pivot_rows, const double *R_upper,
                           int rstride, const double *Q_rows);

/* Fast decision form for a single proposed rank.  Returns 1 only when the same
   a-posteriori provenance inequality certifies exactly proposed_rank. */
int fg_qr_rank_certifies(const double *core, const double *core_eps,
                         int rows, int n, int proposed_rank,
                         const int *pivot_rows, const double *R_upper,
                         int rstride, const double *Q_rows);

#endif
