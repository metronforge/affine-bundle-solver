# Binary SDK qualification implementation plan

**Goal:** qualify installed shared SDK archives, without release publication.
**Spec:** user task B1–B14 and its numerical/ABI boundary.
**Design:** dedicated manual/reusable workflow; three native builders and one
exact-byte x86 forward consumer. Install via CMake, audit platform binaries,
add provenance/licenses/dependency contract/checksums, then archive. Clean-room
consumers operate only on extracted archives and compare the existing 78-pair
semantic corpus plus a small policy/streaming API JSON fixture with source builds.
**Execution:** inline, autonomous per user; canonical checkout, no new worktree.
Routine skill approval pauses are superseded by the user's execution instruction.

## Checkpoint A — complete before qualification work

Previous main 046ce400d1e3faec211f1bc0df6d977ac3d673c9 fast-forwarded six commits
to fafc159b8e02c18c6ed82e21b658e78a4f25a317. Both worktrees clean; no stash.
Historical experiment refs outside main preserved, not included in integration.
Main run 36629568879: all 19 jobs successful, including verification gate.
Only then created release/binary-qualification from that exact main.

## Constraints

- No solver/public-header/policy/version/tag/Release Please/publication changes.
- Ubuntu22/GCC11/glibc2.35 x86; Ubuntu24/GCC13/glibc2.39 ARM; macOS15/AppleClang
  ARM/OpenBLAS/libomp. Empty ABS_ARCH_FLAGS, native runners, no runtime bundling.
- Archives from CMake install, not build-tree copies; no private headers.
- Every archive binds exact clean source commit/tree and library hashes.
- Archive checksum outside archive; internal checksum manifest excludes itself.
- No binary archives in Git. Retain compact metadata/audit/semantic evidence.
- Own loader paths relocatable; external Homebrew paths documented, not rewritten.

## Review focus

1. Malformed/checksum-mismatched archives must fail before consumption.
2. Source/build/staging paths or wrong ELF/Mach-O architecture must fail audit.
3. External consumers must resolve own DSOs only inside extracted SDK.
4. Missing BLAS/OpenMP must fail clearly without destructive system edits.
5. Forward job must consume builder archive bytes, never rebuild solver.

## Task 1 — installed archive and binary audit

- [ ] tests/test_binary_sdk.py: failing cases for ELF version ordering/floor,
      forbidden RPATH/machine, checksum mismatch, unsafe archive paths.
- [ ] tools/inspect_binary_sdk.py: readelf/file/otool/strings audits with raw
      structured evidence, no build/staging paths or GLIBCXX, glibc floor check.
- [ ] tools/package_binary_sdk.py: clean source identity, cmake --install,
      exact SDK inventory, metadata/dependencies/licenses, checksums/tar/verify.
- [ ] Run helper unit tests, actual local installation/audit/archive and negative
      controls; register tests in CTest, run full suite, commit checkpoint.

## Task 2 — archive consumers and semantics

- [ ] tests/binary_sdk_smoke.c: literal policy/stream expectations and JSON.
- [ ] tools/test_binary_sdk.sh: verify/extract archive into fresh workspace,
      external C/C++/diagnostic/pkg-config consumers, exact resolution checks,
      existing snapshot and new API snapshot compared with source output.
- [ ] tools/check_missing_sdk_dependency.py: patch disposable DSO copies only
      to require absent BLAS/OpenMP names; loader must fail, original hashes fixed.
- [ ] Test local archive path with build and staging prefixes unavailable,
      retain failure diagnostics and commit checkpoint.

## Task 3 — native qualification CI

- [ ] .github/workflows/binary-qualification.yml: workflow_dispatch/workflow_call,
      three native builders/full tests/property/FP, staging/inspection/archive,
      builder consumers, ordinary Actions artifacts, x86 Ubuntu24 forward test,
      explicit semantic aggregation and required qualification gate.
- [ ] Existing registered ci.yml gets a manual opt-in reusable-workflow call
      only; avoids requiring an unmerged new workflow on default branch to dispatch.
      Ordinary push CI does not build SDK archives.
- [ ] Run actual Actions; diagnose and correct genuine packaging defects without
      weakening tests. Full source matrix must also remain green.

## Task 4 — review/evidence/handoff

- [ ] Independent review; fix material findings with negative tests.
- [ ] reports/binary-release/qualification-report.md: exact identities, qualified
      platform contracts, highest glibc requirements, Homebrew paths, SHA256s,
      consumer/semantic/FP results and limitations; compact evidence in Git.
- [ ] Audit release.yml, publish-release.yml, build_release_candidate.sh, package
      version, tags, public headers and solver sources unchanged.
- [ ] Push final branch; obtain green source and binary qualification Actions;
      clean worktree, no merge or release. Report final HEAD and exact artifact IDs.
