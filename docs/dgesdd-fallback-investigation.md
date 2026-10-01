# DGESDD fallback allocation-failure investigation

## Canonical-base finding

The reported defect exists on canonical base `8a46829983be468f4b1f93c570f413fcecbfc17f`, although the observed failure is a null write after cleanup rather than a heap use-after-free.

`run_unique_and_infinite_profiles` first calls `infinite_witness_prepare`. If either witness allocation fails, that helper calls `bs_infinite_witness_free`, which frees any partial allocation and clears both `w->x` and `w->z`. The caller retained the nonzero generator code but nevertheless entered the generic QRCP/DGESDD fallback block. `smallest_right_vector_dgesdd` then completed its own allocations and passed the cleared `w->z` to `smallest_subspace_vector`, which wrote through null.

ASan/UBSan reproduced the defect deterministically:

```text
runtime error: store to null pointer of type 'double'
smallest_subspace_vector -> smallest_right_vector_dgesdd
-> infinite_witness_set_dgesdd -> run_unique_and_infinite_profiles
```

The fix records whether the reusable infinite witness was prepared successfully and permits QRCP-to-DGESDD fallback only in that state. Generator allocation failure now skips fallback, cleans up safely, and the new candidate-certification API reports `BS_CERTIFY_ALLOCATION_FAILURE` with a fail-closed initialized result.

## Deterministic coverage

`test_candidate_certification_alloc` forces QRCP verification rejection so the real DGESDD fallback executes, counts 24 allocation sites across candidate-certificate setup, and fails each site in turn. Every injected failure must return an execution allocation error with an empty nearby mask, infinite bounds, and UNKNOWN / NOT_VERIFIED exact-source fields. The no-failure control proves that QRCP rejection, DGESDD attempt, and DGESDD verification were all reached.

The sweep covers allocation failure before witness setup, partial witness initialization, QRCP setup, DGESDD setup/workspace, inconsistent-profile setup, cleanup, and repeated calls. It runs as a native process under the repository's combined ASan/UBSan instrumentation.
