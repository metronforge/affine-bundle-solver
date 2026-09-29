# Qualified binary release publication

## Integration and source identity

Canonical repository: `/projects/affine-bundle-solver`.
Previous main: `fafc159b8e02c18c6ed82e21b658e78a4f25a317`.
Qualification was fast-forwarded without squashing or deleting branches to
`8b7e0738a383746adec3f848eef5e544000fd8e5`, the publication branch base.
The exact-main push run [36637506054](https://github.com/metronforge/affine-bundle-solver/actions/runs/36637506054)
passed. The inherited qualification job was opt-in, so the full workflow was
also dispatched with qualification enabled: [36637627164](https://github.com/metronforge/affine-bundle-solver/actions/runs/36637627164),
**24 jobs, all successful**, including all three SDK builders, exact x86 forward
consumption, and the packaged semantic qualification gate. Publication work
started only after that checkpoint.

Implementation branch: `release/binary-publication`. Final validation identity
and run are recorded in the validation section below; the final documentation
commit is identified by the branch's Git history (a commit cannot embed its own SHA).

## Architecture before and after

Before: Release Please maintained the version PR; successful push CI generated
and verified source/research archives on version changes. The workflow-run
publisher downloaded those bytes, targeted the exact verified commit, attached
without overwrite, downloaded and checked them, and enforced immutable publication.

After: that source/research producer and its internal manifests, paper claims,
clean extraction and source rebuild checks remain intact. A shared context job
validates version agreement and detects release commits. Those commits also run
the existing reusable native SDK qualification workflow in release mode.

`package_binary_sdk.py` remains the only SDK packager. Qualification mode keeps
`qual-<sha>` identity. Release mode requires the input version to agree with
Release Please, CMake and CITATION, and source HEAD to equal `GITHUB_SHA`.
It records version/tag alongside all existing compiler/runtime/build provenance.
No tag is needed to build a candidate.

Builders remain Ubuntu 22.04/GCC 11/glibc 2.35/x86-64; Ubuntu 24.04 ARM/GCC 13/
glibc 2.39/ARMv8-A; and macOS 15/Apple Clang/Apple Silicon/deployment target 15.0.
All use empty architecture flags and shared solver libraries. Linux uses external
reference LP64 BLAS/LAPACK and libgomp; macOS uses external Homebrew OpenBLAS and
libomp, never Accelerate. No runtime is bundled.

## Exact-byte qualification and aggregation

Each builder installs and audits the SDK, packages once, verifies its outer and
internal SHA256 inventory, makes the original build/staging prefixes unavailable,
and consumes a clean extraction with CMake, C++, pkg-config, semantic and
certificate consumers. ABI, dependency resolution, forbidden-path checks and
missing-dependency negative controls are retained. Ubuntu 24.04 downloads and
consumes the exact Ubuntu 22.04 SDK artifact without rebuilding the solver.
The gate compares all four packaged semantic and policy/stream snapshots.

The final aggregation job requires successful source verification and the full
reusable binary workflow, including the forward consumer and semantic gate.
It downloads explicit artifact names from the same run, validates each producer's
inventory and hashes and each binary's release identity, then copies the bytes.
Only the combined checksum manifest is newly generated. It contains exactly five
entries in stable source/research/linux-x86_64/linux-arm64/macos-arm64 order.
The `release-candidate` Actions artifact has exactly those five `.tar.gz` files
plus `SHA256SUMS.txt`. Source/research `MANIFEST.sha256` verification is unchanged.

## Promotion and failure behavior

The publisher still requires a successful `build-and-test` push on `main` and a
release-version change. It checks out `workflow_run.head_sha` and downloads
`release-candidate` using that exact `workflow_run.id`. There is no compilation,
packaging, qualification execution, renaming, or archive modification here.

Shared pure validation rejects missing, unexpected, nonregular or duplicate
assets/checksum entries, malformed names/versions, incorrect hashes and unsafe
binary tar members. Binary `BUILD-INFO.json` must match repository, version, tag,
source SHA and platform even if outer checksums were recomputed.
Existing assets are downloaded and compared byte-for-byte, never overwritten;
different bytes fail closed. After attachment, all assets are downloaded into a
fresh directory, the exact inventory/checksums/binary identities are verified,
and every downloaded file including the checksum manifest is compared to the
candidate. Only then may the draft be published; immutability is checked again.
Existing wrong-target or mutable published releases remain failures.

An ordinary commit does not produce or publish a candidate. The explicit
`release_candidate_dry_run` dispatch builds real archives using the unchanged
project version and actual commit identity; it does not mutate Release Please.
The publisher's push/main guard excludes all dispatch runs.

## Validation

In progress: full non-publishing run on implementation commit `5237be434af84c77ef0ccfafe0ee676b55d1a9b1`:
[36638644221](https://github.com/metronforge/affine-bundle-solver/actions/runs/36638644221).

Local deterministic validation covers names/order, five-entry checksums,
corruption, missing/extra assets, duplicate/traversal manifest entries,
manifest/CMake/CITATION disagreement, wrong source SHA, incorrect internal
BUILD-INFO identity, existing identical/different bytes, exact aggregation,
qualification/release mode distinction, and ordinary/dry-run detection.
Workflow YAML and embedded Bash syntax pass; actionlint 1.7.7 passes.

## Limitations and user contract

See [binary installation documentation](../../docs/binary-sdk.md) for dependencies.
The tested floors are not universal distribution guarantees; the previously
qualified GLIBC 2.29 maximum solver symbol is not a supported minimum-userspace
claim. Actions artifact retention is seven days for the combined candidate and
30 days for SDK/evidence artifacts, matching the existing retention choices.
Promotion needs the successful run's retained candidate; expired candidates
cannot be reconstructed by the publisher.

No actual release/tag/version bump is used to validate this work. GitHub's actual
upload/publish/immutability API path is preserved and reviewed, not exercised
against a dummy public release. No additional platform, public API/ABI,
algorithm, numerical threshold, certificate semantic or policy default changes.
The implementation branch is intentionally not merged automatically.
