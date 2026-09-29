# Task 9 implementation plan and ABI contract

Approved scope: separate operational policy, exact source evidence, and nearby
certificates. No new application cases or historical evidence rewrites.

1. Add failing C API regression tests for policy/result initialization, size
   validation, future suffix preservation, invalid values, default equivalence,
   custom/default isolation and concurrent calls.
2. Add operational_policy.h with size-prefixed BSOperationalPolicyV1,
   BSOperationalResultV1, exact-source and verification enums. Minimum accepted
   size is the complete V1 prefix; larger buffers preserve/ignore unknown suffixes.
   Helpers initialize V1 sizes. Null policy and undersized results are errors.
3. Preserve the default fast router unchanged. Explicit custom policies use the
   existing normalized source-QRCP backend. Pass immutable policy values locally;
   no global or TLS policy. This avoids changing hidden compressed-proposal
   tolerances to pretend they implement arbitrary D/G. Custom routing may cost
   more; default routing has only a constant-size validation/dispatch overhead.
4. Add BSCombinedSemanticResultV1 and one-router combined policy API. Reuse the
   existing independent three-certificate completion, untouched proof semantics.
   Production exact fields always UNKNOWN / NOT_VERIFIED. Invalid policy clears
   valid-size results to FAIL/NONE with no accepted nearby mask.
5. Document defaults D=1e-13, G=1e-9, compatibility=2e-10, quality=1e-14;
   finite positive values required, D<G<=1, compatibility and quality <=1.
   Source rank uses mu>G and mu>=D; compatibility uses the existing source-row
   formula; quality affects UNIQUE witness retention only. Internal proposal and
   proof arithmetic guards are not researcher-adjustable certificate criteria.
6. Add abs-apps additive semantic reporting and a small fixed-input sweep utility.
   Freeze compatibility choices [2e-10,1e-12,1e-14,1e-16] before execution.
   Attach exact evidence only after exact A/b hash binding to retained adjudication.
7. Validate legacy/default field equivalence on focused tests and the 36 existing
   Task8 materialized inputs; measure bounded default overhead. Run current fast
   regression, strict FP probes and relevant concurrency tests; full abs-apps pytest.
8. Align headers, API docs and manuscript. Keep nearby theorem and frozen oracle.
9. Commit, push branches, verify CI, merge and push both mains. Preserve branches.

Review focus: undersized/oversized caller buffers; fast-math NaN validation;
policy-to-proof isolation; source QRCP versus default dispatch; concurrent caller
diagnostics; exact-evidence input identity. No general exact solver is introduced.
