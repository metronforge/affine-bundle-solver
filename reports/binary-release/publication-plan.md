# Binary publication implementation plan

> Execute inline with test-driven validation; user task is the binding specification.

Goal: qualify exact release-commit SDK bytes and promote them through the existing immutable pipeline.
Architecture: retain source/research tooling; add shared pure release validation, release mode in the existing SDK packager, a same-run aggregate, and promotion-only publisher validation.
Tech stack: Python standard library, Bash, GitHub Actions.

## Constraints and checkpoint

Base: 8b7e0738a383746adec3f848eef5e544000fd8e5.
Previous main: fafc159b8e02c18c6ed82e21b658e78a4f25a317.
Exact-main run 36637627164: success, 24 jobs, all five binary qualification jobs successful.
Push run 36637506054 also successful. Qualification was explicitly dispatched because the inherited workflow makes it opt-in.
No solver/API changes, version changes, tags, releases, branch deletion or automatic implementation merge.
Work in canonical /projects/affine-bundle-solver on release/binary-publication; no extra worktree needed.

## Tasks

- [ ] 1. Add tests and tools/release_assets.py: expected archive names in source/research/x86/ARM/macOS order; strict version and commit identity; complete inventory and checksums; binary BUILD-INFO validation; exact existing-asset comparison; aggregation from verified producer inventories. Run unittest failures then passing suite.
- [ ] 2. Extend tools/package_binary_sdk.py with explicit qualification/release modes using shared identity validation. Release requires manifest/CMake/CITATION agreement and HEAD == GITHUB_SHA; retain all existing packaging/auditing. Test mode/name/identity boundaries.
- [ ] 3. Add CI release context and non-publishing dry-run input; feed version into reusable binary qualification; retain source/research producer; aggregate only after source verification and full binary gate including forward consumption. Add publication validation tests as required CI.
- [ ] 4. Extend publisher with shared pure validation, six-asset no-overwrite handling, complete remote revalidation and candidate comparison. Keep workflow_run push/main guard, exact run ID, exact SHA target and immutable enforcement.
- [ ] 5. Document installation dependencies and publication evidence. Run full candidate dry-run CI on branch, review, fix failures with regression tests, commit evidence, then validate final HEAD. Do not merge.

## Review focus

Reject malformed/duplicate/traversal checksum entries; reject extra remote assets; reject binary identity despite valid recomputed outer checksums; prevent dry-run/ordinary pushes from publishing; prevent aggregation when any qualification fails.

## Execution ledger

Planning: user supplied detailed architecture and explicitly requested autonomous execution; proceed without additional design approvals. Existing canonical named branch is used per repository safety preference.

Diagnostic milestone: first dry-run 36638644221 failed source extraction rebuild
because build.sh's provenance block unconditionally required .git. Both original
archive manifests had passed. Add manifest-covered SOURCE-PROVENANCE.json and
source_identity.py; retain Git behavior in checkouts and detect modified archived
files. No compiler commands, solver semantics or paper assertions change.
