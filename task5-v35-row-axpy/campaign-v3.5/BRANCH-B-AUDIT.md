# Branch B publication audit

Result: **READY** for Viktor to consider authorizing a later PR.

- Corrected immutable head: `b8d22717b1cb9a67fe6dd60cf0c8162cbed3d7c2`; tree `1c686f76a86632ce3b526cffe85857a047309414`.
- `BIBTEX=bibtex ./build_paper.sh` produced a 27-page PDF. The final TeX pass has zero unresolved citation/reference warnings and zero overfull boxes; earlier-pass warnings remain in the raw multipass log and are not misreported as final-pass failures.
- All eight manuscript claims reproduced. The performance inventory and artifact audit both passed, and publication readiness is `true`.
- `paper.tex` SHA-256 is `3377160de6dd996896e3f63098c642bf3b0f2851b2bd59c2f1552f5e51bf743b`, exactly matching the registry. The built `paper.pdf` SHA-256 is `381dec8dc246bc2a8e5075f42fd3e269bcad9bce5e0d0932c5d9cde2a1685af9`.
- The packed-LU paragraph now accurately distinguishes validated properties from triangularity imposed by representation.
- The `eta_inc` digits are expressly reference-platform observations; portable tests check their demonstrated machine-scale bounds, not build-dependent trailing digits.
- Factor reuse text describes only merged production behavior: shared unique/infinite least-squares work and the merged reusable tall QRCP. Branch B contains no `unique_row_pass` and does not claim the unmerged Branch A optimization.
- The FP-contraction prose is true for Branch B itself because it contains the flag commit and the corrected fail-closed gate.
- Added threshold constants match current source policy and the named public-header path exists.
- Manuscript-facing prose contains no Task-5, Ralph, campaign, v3.x, Branch A/B, or Viktor workflow labels. Authorship is unchanged; publication-facing statements remain technical and neutral.
- Tracked generated PBT result files changed during the audit and were explicitly restored. The worktree is clean.
