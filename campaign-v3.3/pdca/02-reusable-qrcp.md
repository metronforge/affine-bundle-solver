# PDCA 2 — implement reusable QRCP

## PLAN

Hypothesis: one private owned QRCP state can reproduce every witness and meaningful diagnostic while reducing the V31-027 target domain to one actual factorization. Acceptance required the RED call-count test to become green, exact baseline/candidate snapshots, deterministic cleanup at every owned allocation failure, no full Q, no scan-time matrix copy, and no API/ABI change.

## DO

`BSLeftNullQRCP` now owns a column-major copy of normalized `An`, its in-place DGEQP3 result, Householder `tau`, `jpvt`, QR and Q-application workspaces, the DGELSY rank metadata, and one scratch vector. Initialization performs one workspace query and one actual DGEQP3. Projection uses DORMQR with Q^T then Q; each completion direction resets the scratch basis vector and applies the same implicit Q. Cleanup is idempotent and invocation-local.

The allocation-failure test was first RED because no QRCP-specific hooks were reached, then GREEN after all six owned allocations were injectable and cleanly released.

## CHECK

The exact V31-027 target domain fell from 258 DGEQP3 entries to 2 (one query, one execution); complete combined-call count fell from 262 to 6. The original hash is retained. The native call-count fixture is GREEN at 2; 27 native tests pass. Thirty-one harness tests pass, including exact baseline/candidate public witness and combined-result snapshots for 12 cases, each repeated twice. All compared status, rank, solution, residual, witness, pivot/permutation, certificate, router, and diagnostic fields are exactly equal under NaN/Infinity-safe serialization.

## ACT

Accept. The smallest valid internal optimization is implemented. Cycle 3 owns broad safety, sanitizer, cross-BLAS/compiler, reentrancy, installed-consumer, and independent-review gates before any PR or performance run.
