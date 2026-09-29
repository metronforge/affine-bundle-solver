# Build Matrix Phase 2 Implementation Plan

> **For agentic workers:** Execute inline using superpowers:executing-plans.

**Goal:** Evidence-backed source-build compiler/runtime/BLAS support envelope,
without binary publication or numerical policy changes.
**Architecture:** Four representative version/provider jobs supplement Phase 1.
All produce the existing semantic snapshot and execute the full portable contract.
**Tech Stack:** GitHub Actions, CMake, C11, Python, Ubuntu packages, OpenMP, LP64 BLAS.
**Spec:** User task “Integrate Build Matrix Phase 1, then establish compiler/BLAS
support envelope”, Checkpoints A and B1–B9, retained in the conversation.

## Checkpoint A (completed before any Phase 2 work)

Clean canonical repository and clean existing baseline worktree; no stash.
Historical branches retained, including local-only refs. No divergence between
main and Phase 1: `0 16`. Fast-forward from
`a668660bd49b7b2f015293ac84d00efbc424a8a3` to
`046ce400d1e3faec211f1bc0df6d977ac3d673c9`; all 16 commits preserved.
Local CTest 44/44 passed. Main push run **36625749601** completed successfully,
all 15 jobs including cross-platform comparison and verification gate.
Only then created `ci/build-matrix-phase2` from that exact main SHA.

## Global Constraints

- Work in `/projects/affine-bundle-solver` on the named branch; no cleanup.
- No threshold, classification/rank/acceptance policy, ABI or algorithm changes.
- `ABS_ARCH_FLAGS=''` in new jobs; no new release artifacts, Windows or Intel Mac.
- GCC 11/reference and Clang 14/reference on Ubuntu 22.04; GCC 13/OpenBLAS
  and Clang 18/reference on Ubuntu 24.04. Retain all Phase 1 jobs.
- Explicit reference BLAS paths avoid alternatives silently selecting OpenBLAS.
- Every selected version: full CTest, runtime/structural FP, full properties,
  install/relocation/external C/C++/pkg-config consumers and semantic snapshot.
- Real Actions evidence is authoritative; no continue-on-error.
- User autonomous execution overrides routine skill approval pauses; preserve
  canonical checkout instead of creating a convenience worktree.

## Review Focus

1. Provider alternatives may select the same DSO: assert resolved paths and hashes.
2. Old/current compiler executables may be aliases: assert selected major version.
3. Near-threshold exact stored inputs differ from mathematical transforms: separate
   representation changes from semantic disagreement, never widen tolerances.
4. Round modes may be left changed on error paths: exercise public verification
   acceptance/rejection plus preservation in all four modes.
5. Missing snapshot participants must fail, not silently reduce comparison coverage.

### Task 1: Version-envelope CI and runtime provenance

**Files:** `.github/workflows/ci.yml`, `tools/record_portability_build.py`,
`tools/check_blas_provider.py`, `tests/test_blas_provider.py`.
**Interfaces:** existing `--snapshot DIR --output FILE`, `--compare-snapshots FILE...`;
provider checker consumes build directory and expected reference/openblas, returns
nonzero for wrong/missing provider; provenance emits libc/OS/package/dependency data.

- [ ] Add failing tests for wrong/missing provider identity using resolved ELF DSOs.
- [ ] Implement minimal fail-closed provider checker and test it against real builds.
- [ ] Add four version jobs; assert actual compiler major; record distro, libc,
      kernel, runtime and BLAS versions and actual resolved dependencies.
- [ ] Extend existing system job with full properties and snapshot, and aggregate
      explicit required participants without repeating deep publication jobs.
- [ ] Validate workflow structure, run full local CTest, commit and run Actions.
Expected: all required jobs green; wrong-provider checker returns nonzero.

### Task 2: Range/rounding and cross-provider regression

**Files:** `tests/test_row_norm_range.c`, new `tests/test_range_rounding.c`,
`CMakeLists.txt`, `tests/compare_builds.py`, existing BLAS comparison job.
**Interfaces:** native tests return nonzero on contract breach; snapshot schema stays
unchanged and corpus hash binds added deterministic positive/negative scale cases.

- [ ] Extend norm test over all exact binary powers and neighbors of zero, minimum
      normal and maximum finite, with both signs and all rounding modes.
- [ ] Add public verifier tests with analytic acceptance/rejection expectations for
      compatibility/quality neighborhoods, zero rows and near-rank fixtures;
      assert rounding preservation and classify diagnostic-only changes separately.
- [ ] Prove negative controls fail without modifying production code in place.
- [ ] Extend snapshot corpus and existing BLAS job to compare certificate fields
      and Phase 1 extreme cases through the same serialized comparator.
- [ ] Run full local CTest/properties; commit; validate all Actions participants.
Expected: exact contracts pass, negative controls fail, snapshots agree.

### Task 3: Evidence, policy and release-readiness report

**Files:** `docs/build-matrix.md`, `reports/build-matrix/phase2-report.md`,
`reports/build-matrix/phase2-evidence/`.
**Interfaces:** consumes actual Actions artifacts and task results, no new runtime API.

- [ ] Download text/JSON evidence and retain source/run identities and any failures.
- [ ] Document compiler sensitivity audit, observed generations/providers/libc,
      rejected configurations, lifecycle limits and analysis-only packaging contract.
- [ ] Fresh whole-branch review; fix material findings with regressions.
- [ ] Commit documents, push, run final exact HEAD Actions, verify clean tree.
Expected: completely green final run; no public API/policy/release workflow changes;
all valuable source/evidence committed, Phase 2 not merged.

## Completion ledger

Task 1: implemented in 3a474e2; full local CTest 45/45. Actual CI exposed a
Clang libatomic search gap, corrected in 1ba318f; run 36627025489 all 19 green.
Task 2: implemented in bc24fbd; local CTest 47/47 and both full batteries pass;
run 36627216544 all 19 green, nine snapshots agree on 78 pairs.
Task 3: review fixes in 0107160; run 36627551475 all 19 green. Raw evidence and
support policy retained; final documentation-inclusive SHA/run reported in handoff.

Review: no Critical/Minor; two Important coverage/identity findings corrected.
Interval rejection now changes rounding before rejecting; the deliberate verifier
mutation fails its restoration assertion. Reference job explicitly selects GCC13.
No production numerical source, API or policy changed. No release/Phase2 merge.

Rulings: continue inline in canonical repo per user autonomy; correct new quality
fixture's assumed least-squares witness to actual source-row witness (analytic
delta/(2+delta), no tolerance widening); final documentation and CI remain required
despite review deferring those unfinished items. No findings silently waived.
