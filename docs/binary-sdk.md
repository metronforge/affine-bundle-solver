# Installing a binary SDK

The next normal Release Please release after the binary publication pipeline is
merged will attach three portable shared-library SDKs alongside the existing
source and research archives. Older releases may contain only the latter.
Find assets on the [GitHub Releases page](https://github.com/metronforge/affine-bundle-solver/releases).

For release `vX.Y.Z`, choose one of:

- `affine-bundle-solver-vX.Y.Z-linux-x86_64.tar.gz`
- `affine-bundle-solver-vX.Y.Z-linux-arm64.tar.gz`
- `affine-bundle-solver-vX.Y.Z-macos-arm64.tar.gz`

Download `SHA256SUMS.txt` from the same release and verify the selected archive
before extracting it. The manifest covers five archives, in source, research,
Linux x86_64, Linux ARM64, macOS ARM64 order. If all five are downloaded, run
`sha256sum -c SHA256SUMS.txt` (macOS: `shasum -a 256 -c SHA256SUMS.txt`).
For a single SDK, select its exact filename's line from the manifest and check
that line; do not ignore a failed hash for the file you downloaded.

## External dependencies and tested baselines

| SDK | Native builder | CPU and tested userspace | Required external runtimes |
| --- | --- | --- | --- |
| Linux x86_64 | Ubuntu 22.04, GCC 11 | x86-64 baseline; glibc 2.35; the same archive is also consumed on Ubuntu 24.04 | Compatible LP64 reference/system BLAS/LAPACK and libgomp |
| Linux ARM64 | Ubuntu 24.04 ARM, GCC 13 | ARMv8-A; tested userspace floor glibc 2.39 | Compatible LP64 reference/system BLAS/LAPACK and libgomp |
| macOS ARM64 | macOS 15, Apple Clang | Apple Silicon; macOS 15 deployment/qualification baseline | Homebrew OpenBLAS and libomp |

On the tested Ubuntu systems: `sudo apt-get install libblas3 liblapack3 libgomp1`.
The package manager supplies their transitive dependencies, including Fortran
runtime libraries where applicable. ILP64 BLAS is incompatible with this SDK.

On macOS: `brew install openblas libomp`. The binaries use external install names
`/opt/homebrew/opt/openblas/lib/libopenblas.0.dylib` and
`/opt/homebrew/opt/libomp/lib/libomp.dylib`. Accelerate is unsupported.

No BLAS or OpenMP runtime is bundled. These are tested baselines, not guarantees
for every distribution or older userspace. The initial qualified Linux solver
libraries required no GLIBC symbol newer than 2.29; that observation does not
establish compatibility below the tested floors above. Every release is audited
against its platform floor. Inspect its `BUILD-INFO.json` and `DEPENDENCIES.md`
for the actual build and dependency versions.

## Using the extracted prefix

The archive contains public headers in `include/affine_bundle`, three shared
solver libraries in `lib`, CMake package metadata under
`lib/cmake/affine-bundle-solver`, and pkg-config metadata under `lib/pkgconfig`.
It includes `LICENSE`, `NOTICE`, `BUILD-INFO.json`, `DEPENDENCIES.md`, and an
internal `SHA256SUMS.txt`. It excludes private headers, implementation source,
build trees, research materials, and CI evidence.

Set `CMAKE_PREFIX_PATH` to the absolute extracted prefix, then use
`find_package(affine-bundle-solver CONFIG REQUIRED)` and the exported targets
as described in [the build documentation](../README.md#build).
For pkg-config, set `PKG_CONFIG_PATH` to `<prefix>/lib/pkgconfig` and query
`pkg-config --cflags --libs affine-bundle-solver`. Applications must make the
SDK's `lib` directory available to their loader, for example with an application
rpath. Keep the SDK layout intact; its libraries locate one another relatively.

## Provenance and publication

`BUILD-INFO.json` records the release version, tag, exact source commit, platform,
compiler and runtime versions, CPU baseline and build options. All SDKs are built
with `ABS_ARCH_FLAGS=''` without native tuning. CI qualifies the packaged bytes
through clean C/C++/CMake/pkg-config consumers, certificate and semantic tests,
ABI/dependency inspection, and dependency-negative controls before aggregation.

Publication downloads the candidate from the exact successful CI run, verifies
all checksums and binary identities, uploads without overwriting differing
assets, downloads everything again and compares bytes, then publishes and checks
GitHub immutability. Publication never rebuilds or repackages an archive.
