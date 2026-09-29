# Numerical-semantics build matrix

Phase 1 verifies semantic portability, not identical floating-point bits.
Support is conditional on the required `build-and-test` verification gate being
green for the revision being used. The initial validation record is in
[the Phase 1 report](../reports/build-matrix/phase1-report.md).

## Tier 1 — verified on every required CI run

| Target | GitHub runner | Compiler / mode | Solver BLAS/LAPACK | OpenMP |
|---|---|---|---|---|
| Linux x86_64 | `ubuntu-24.04` | GCC portable | SciPy OpenBLAS; system provider in CMake jobs | libgomp |
| Linux x86_64 | `ubuntu-24.04` | GCC native | SciPy OpenBLAS | libgomp |
| Linux x86_64 | `ubuntu-24.04` | Clang portable | SciPy OpenBLAS | libomp |
| Linux ARM64 | `ubuntu-24.04-arm` | GCC portable | system BLAS/LAPACK | libgomp |
| Linux ARM64 | `ubuntu-24.04-arm` | Clang portable | system BLAS/LAPACK | libomp |
| macOS ARM64 | `macos-15` | Apple Clang portable | Homebrew OpenBLAS, LP64 Fortran ABI | Homebrew libomp |

All ARM jobs assert the actual runner architecture and configure
`-DABS_ARCH_FLAGS=''`. No ARM tuning or native binaries are published. Exact
compiler, OS image, library dependencies, source tree and binary hashes are
recorded in each run's `portability-evidence-*` artifact. Platform support does
not freeze rolling GitHub runner versions.

## Required coverage

The original x86 suite retains GCC portable/native and Clang, SciPy/system BLAS
independence, native/portable comparison, ASan/UBSan, all manuscript/research
and performance-claim checks, regressions, property batteries and installation.
Reference-machine publication and timing evidence remains on x86; it is not a
portability test.

Each ARM job runs configure, build, all applicable CTests, both full strict
property batteries, FP runtime and contraction gates, clean-prefix installation,
and C/C++ CMake plus C pkg-config consumers outside the repository. Installation
is relocated and the build tree made unavailable before consumer execution.
No loader-path environment variables are required. Linux uses `$ORIGIN`;
macOS uses `@loader_path` and CMake's native install names.

The Linux `/proc`/`RLIMIT_AS` stream-allocation tests retain their original OS
scope. Every platform also runs `test_stream_alloc_failure`, which intercepts
the production growth allocator in a test-only translation unit and verifies
unchanged counters/rank after ENOMEM and successful retry. This covers the
semantic requirement on macOS without pretending its resource limits behave
like Linux's. No installed library contains this interception.

System BLAS selection must link all 15 solver entry points at configure time.
Actual CTest/property/certificate execution then tests those routines and their
LP64 integer calling convention. Accelerate linked every required symbol, but
failed the existing exact-rank-deficient certificate-profile fixture: unique
witness generation returned 6 and the accepted-status mask was 6 rather than 7.
On the same AppleClang runner, OpenBLAS passed that unchanged fixture. The
failure occurs when the selected normalized rows yield a zero pivot in the
solver's strict LU witness packer; symbol availability alone is insufficient.
Phase 1 therefore explicitly selects OpenBLAS. There is no silent provider
fallback and Accelerate is not a supported matrix configuration.

## Floating-point contracts

Strict kernels use `-O2 -frounding-math -fno-fast-math -ffp-contract=off`.
Only router compilation uses fast math; router linking must not. The historical
`mxcsr_probe` test name is retained for evidence continuity. Its implementation
now inspects all MXCSR control bits on x86 (excluding exception status), or all
FPCR bits on AArch64. Unknown architectures fail at compilation.

The runtime probe requires both libraries to load, checks control state after
each load, and tests input and output subnormal multiplication and directed
rounding at every stage. Negative controls deliberately change rounding and
flushing from shared-library constructors. FPCR is readable from user mode;
baseline Arm FZ covers input and output flushing, while x86 has separate FTZ
and DAZ. All FPCR bits are compared, including implemented FIZ/AH extensions.
The state is per-thread; library constructors can corrupt the loading thread
and the initial state inherited by future workers. Existing worker-fenv tests
exercise OpenMP behavior separately.

The contraction checker inspects only the three strict translation units,
including the verifier's OpenMP compilation. It uses GNU `objdump` on Linux and
Xcode `llvm-objdump` on macOS, checks expected symbols and nonempty disassembly,
and rejects scalar, SIMD, alternating/negated and extended ARM fused forms,
including suffixed Mach-O mnemonics. x86 uses an FMA-capable inspection target
to avoid a vacuous portable-target pass; AArch64 already has FMA. No inspection
objects are distributed. Tests cover deliberate contraction, missing tools,
missing symbols, empty disassembly and unknown architectures.

## Semantic snapshots

`tests/compare_builds.py` supplies the same router equality key for local
BLAS/native comparisons and cross-runner artifacts: status, certainty, rank,
rank interval and classification. The cross-platform corpus consists of exact
integer/dyadic tall, square, wide, rank-deficient, inconsistent, zero and
rank-boundary systems, plus 15 extreme binary scalings, under two seeds (48
case/seed pairs). It hashes the exact inputs and adds
certified status, rank interval, accepted-status mask and proof generation /
verification outcomes. Missing or malformed evidence fails closed.

Residuals, timing, diagnostic magnitudes and low floating-point bits are not
equality keys. The router's fallback-route bit is not compared: the existing
comparison contract permits route differences as long as the semantic result
agrees. Status/undecidable and certificate failure outcomes remain compared.
The aggregate job requires artifacts from x86 GCC portable, ARM GCC, ARM Clang
and Apple Clang. Any disagreement blocks the verification gate. No platform
uses `continue-on-error`.

## Building locally

Linux (install system BLAS/LAPACK and the compiler's OpenMP runtime first):

```sh
cmake -S . -B build -DABS_BLAS=system -DABS_ARCH_FLAGS=''
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

macOS ARM64, using Apple Clang and Homebrew libomp:

```sh
brew install libomp openblas pkgconf
omp=$(brew --prefix libomp)
CC=clang cmake -S . -B build -DABS_BLAS=system -DBLA_VENDOR=OpenBLAS \
  -DCMAKE_PREFIX_PATH="$(brew --prefix openblas)" \
  -DABS_ARCH_FLAGS='' '-DOpenMP_C_FLAGS=-Xpreprocessor -fopenmp' \
  -DOpenMP_C_INCLUDE_DIR="$omp/include" -DOpenMP_C_LIB_NAMES=omp \
  -DOpenMP_omp_LIBRARY="$omp/lib/libomp.dylib"
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

`build.sh`, SciPy-wheel discovery, research benchmark scripts and release tooling
remain the Linux manuscript path. CMake is the portable build interface.

Two separately documented portability repairs preserve the intended contracts:
[fast-math non-finite validation](../reports/build-matrix/apple-clang-nonfinite.md)
and [witness normalization range](../reports/build-matrix/binary64-long-double.md).
No numerical policy or threshold was retuned.

Windows: not yet supported/verified by this matrix. macOS Intel: not part of
Phase 1. Binary release availability is not implied by build support. No
Windows, universal-binary, packaging or release-publication changes are included.
