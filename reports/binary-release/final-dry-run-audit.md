# Final binary-release dry-run audit

Date: 2026-09-30.  This is a non-publishing audit.

## Integration and CI

`main` was fast-forwarded, without a merge commit or squash, from
`8b7e0738a383746adec3f848eef5e544000fd8e5` to
`f6a910ec1ca72d80183dbc507e2d4acabea98e30`.  The GitHub comparison reported
9 ahead and 0 behind; `git merge-base --is-ancestor` succeeded.

The ordinary push run was [36692717844](https://github.com/metronforge/affine-bundle-solver/actions/runs/36692717844), success, for exactly that SHA. It ran the normal build matrix and publication tests; release-only producers were intentionally skipped because the manifest version did not change. The exact-SHA, non-publishing dispatch qualification run was [36695591850](https://github.com/metronforge/affine-bundle-solver/actions/runs/36695591850), success. It enabled `binary_qualification=true` and `release_candidate_dry_run=true`; it exercised the three SDK qualifications, source/research candidate, aggregate candidate, and verification gate. `publish-release` only accepts `workflow_run.event == 'push'` ([publish-release.yml](../../.github/workflows/publish-release.yml#L18-L22)), so this dispatch could not publish.

No tag, GitHub Release, draft release, version change, or Release Please PR merge was made. The normal push publisher classified the commit as ordinary and stopped before candidate download or release creation ([publish-release.yml](../../.github/workflows/publish-release.yml#L37-L48)).

## Frozen state

The manifest, CMake project, and CITATION version are all `0.4.4`
([.release-please-manifest.json](../../.release-please-manifest.json),
[CMakeLists.txt](../../CMakeLists.txt#L3-L4), [CITATION.cff](../../CITATION.cff#L35)).
The latest release/tag remains immutable `v0.4.4` (2026-09-13); no draft and no
open Release Please PR existed at audit time.

## Trigger and identity contract

`release-context` selects a candidate only for a changed manifest version, or a
manual dry run ([ci.yml](../../.github/workflows/ci.yml#L31-L48)); the reusable
qualification receives that version only when selected ([ci.yml](../../.github/workflows/ci.yml#L60-L65)). A genuine Release Please release commit changes the manifest, so it produces source/research plus binary candidates, then aggregate verification ([ci.yml](../../.github/workflows/ci.yml#L814-L922)). The publisher is triggered by completed successful `build-and-test` push runs on `main`, checks out `workflow_run.head_sha`, and downloads `release-candidate` using the exact `workflow_run.id` ([publish-release.yml](../../.github/workflows/publish-release.yml#L3-L58)). There is no latest-run, branch-head, or rebuild fallback.

For synthetic `X.Y.Z`, `python3 tools/release_assets.py names X.Y.Z` produced exactly:

1. `affine-bundle-solver-vX.Y.Z.tar.gz`
2. `affine-bundle-solver-vX.Y.Z-research.tar.gz`
3. `affine-bundle-solver-vX.Y.Z-linux-x86_64.tar.gz`
4. `affine-bundle-solver-vX.Y.Z-linux-arm64.tar.gz`
5. `affine-bundle-solver-vX.Y.Z-macos-arm64.tar.gz`
6. `SHA256SUMS.txt`

The common constructor is [release_assets.py](../../tools/release_assets.py#L36-L40), used by aggregation and publisher. Candidate verification requires exactly those five archives plus checksum file, canonical checksum order, and three matching `BUILD-INFO.json` identities ([release_assets.py](../../tools/release_assets.py#L75-L115)). `BUILD-INFO` requires repository, source commit, version, tag and platform; filenames alone do not suffice.

## Byte flow, checksums, and publication semantics

The SDK producer packages release-mode names only after manifest/CMake/CITATION/SHA identity validation ([package_binary_sdk.py](../../tools/package_binary_sdk.py#L66-L72)); the qualification uploads those exact archive bytes. Aggregation verifies producer inventories then `copyfile`s source and SDK archives, writes and verifies a five-entry checksum manifest ([release_assets.py](../../tools/release_assets.py#L128-L146)). The publisher only downloads, validates, hashes, uploads, downloads again and compares bytes ([publish-release.yml](../../.github/workflows/publish-release.yml#L50-L67), [publish-release.yml](../../.github/workflows/publish-release.yml#L100-L147)); it has no CMake, compiler, packager, tar-creation, or candidate-build step.

Existing assets are downloaded and byte-compared; absent assets alone are uploaded; differing bytes fail ([publish-release.yml](../../.github/workflows/publish-release.yml#L107-L121), [release_assets.py](../../tools/release_assets.py#L117-L125)). There is no clobber/delete/re-upload. A release is created as a draft targeting `VERIFIED_SHA`, rejects a different existing target, re-verifies remote checksums and bytes, publishes only after that, then requires `immutable == true` ([publish-release.yml](../../.github/workflows/publish-release.yml#L69-L98), [publish-release.yml](../../.github/workflows/publish-release.yml#L123-L147)).

## Regression and negative controls

Local deterministic controls passed: `test_release_assets.py` 12 tests,
`test_binary_sdk.py` 4, and `test_source_identity.py` 3. They reject wrong
version/SHA/tag/platform/repository BUILD-INFO, missing or extra archives,
corrupt or duplicate/unsafe checksum entries, unsafe tar aliases, wrong
manifest/CMake/CITATION identity, and differing pre-existing bytes
([test_release_assets.py](../../tests/test_release_assets.py#L43-L149)). The source/research producer makes deterministic archives and manifests
([build_release_candidate.sh](../../tools/build_release_candidate.sh#L50-L107)); CI extracts and verifies both from clean directories ([ci.yml](../../.github/workflows/ci.yml#L841-L868)).

## Dependencies, permissions and actions

The documented qualified contracts are x86-64/Ubuntu 22.04/glibc 2.35 with
external LP64 BLAS/LAPACK and libgomp; ARMv8-A/Ubuntu 24.04/glibc 2.39 with the
same external runtimes; and Apple Silicon/macOS 15 with external Homebrew
OpenBLAS and libomp, with Accelerate unsupported ([binary-sdk.md](../../docs/binary-sdk.md#L21-L42)). These are tested baselines, not broader claims.

Workflow defaults use `contents: read`; only the publisher job has `actions: read`
and `contents: write` ([ci.yml](../../.github/workflows/ci.yml#L27-L29),
[publish-release.yml](../../.github/workflows/publish-release.yml#L12-L25)). Release-path actions are SHA pinned: checkout, setup-python, download-artifact, and upload-artifact. Release Please is also SHA pinned ([release.yml](../../.github/workflows/release.yml#L44-L49)).

## Verdict

**READY for the next normal Release Please release.** The remaining limitation is
inherent: the next release has not been published, so GitHub's final immutable
asset state is proved by fail-closed workflow logic and dry-run candidates rather
than an actual new release. No release operation was performed in this audit.
