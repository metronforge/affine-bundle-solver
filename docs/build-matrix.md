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
rank-boundary systems, plus 15 extreme binary scalings of both signs, under two seeds (78
case/seed pairs). It hashes the exact inputs and adds
certified status, rank interval, accepted-status mask and proof generation /
verification outcomes. Missing or malformed evidence fails closed.

Residuals, timing, diagnostic magnitudes and low floating-point bits are not
equality keys. The router's fallback-route bit is not compared: the existing
comparison contract permits route differences as long as the semantic result
agrees. Status/undecidable and certificate failure outcomes remain compared.
The aggregate job requires artifacts from x86 GCC portable, ARM GCC, ARM Clang,
Apple Clang, and the five version/provider representatives below (nine total).
Any disagreement blocks the verification gate. No platform
uses `continue-on-error`.

## Supported toolchain/runtime envelope

The platform table above and this compiler/provider envelope answer different
questions. These are **tested combinations**, not a promise that every compiler
between the endpoints or every compiler/provider cross-product works. The
[Phase 2 report](../reports/build-matrix/phase2-report.md) records exact source,
runner, package versions, diagnostic history and verification evidence.

| Representative | Tested compiler | BLAS/LAPACK | OpenMP | libc |
|---|---|---|---|---|
| Ubuntu 22.04.5 x86_64 | GCC 11.4.0 | reference 3.10.0 | libgomp 12.3 | glibc 2.35 |
| Ubuntu 22.04.5 x86_64 | Clang 14.0.0 | reference 3.10.0 | libomp 14.0 | glibc 2.35 |
| Ubuntu 24.04.5 x86_64 | GCC 13.3.0 | reference 3.12.0 | libgomp 14.2 | glibc 2.39 |
| Ubuntu 24.04.5 x86_64 | GCC 13.3.0 | OpenBLAS 0.3.26, pthread | libgomp 14.2 | glibc 2.39 |
| Ubuntu 24.04.5 x86_64 | Clang 18.1.3 | reference 3.12.0 | libomp 18.1 | glibc 2.39 |
| Ubuntu 24.04 ARM64 | GCC 13.3 / Clang 18.1.3 | reference 3.12.0 | libgomp 14.2 / libomp 18.1 | glibc 2.39 |
| macOS 15.7.9 ARM64 | Apple Clang 17.0.0, Xcode 16.4 | OpenBLAS 0.3.34 | libomp 23.1 | Darwin libSystem |

The existing x86 GCC/Clang SciPy OpenBLAS and GCC-native deep jobs remain
required too. New representatives use empty architecture flags, distribution
compiler packages, full applicable CTest, structural/runtime FP checks, both
full property batteries, installed C/C++ consumers, and semantic snapshots.
The four new version jobs additionally test relocation and executable pkg-config
consumption with the original build unavailable. Reference and OpenBLAS identity
is checked against resolved dependency files and hashes, not symlink labels.

**Tested source-build baseline:** Ubuntu 22.04.5 / glibc 2.35 on x86_64,
with the compilers above and CMake 3.31.6 as installed on the runner. This is
neither the oldest theoretically buildable environment nor a binary compatibility
guarantee. ARM64's tested Linux baseline remains Ubuntu 24.04 / glibc 2.39.
Observed kernel and runtime versions are retained independently: a userspace
baseline is not a minimum kernel claim.

The Ubuntu 22.04 hosted runner is in its deprecation window; migrate that
userspace check to a maintained container host before runner retirement, or
explicitly raise the tested floor. Do not silently substitute Ubuntu 24.04.
See the [runner inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2204-Readme.md)
and [Ubuntu lifecycle](https://documentation.ubuntu.com/release-notes/22.04/).

Range regressions cover every binary64 power of two, both signs, minimum
subnormal neighbors, both sides of DBL_MIN, DBL_MAX neighbors, zero rows,
rank-threshold neighborhoods, adjacent stored compatibility values and quality
gate brackets. Strict verification exercises all four standard rounding modes,
including restoration after interval rejection. A deliberately mutated verifier
must fail the same restoration assertions. Operational threshold fixtures run
in nearest rounding; this does not extend the fast-router rounding contract.

Not implied: prebuilt binary compatibility, static linking, all Linux
distributions, all compiler minor versions, Windows, macOS Intel, Accelerate,
or AVX-specific binaries. Accelerate remains explicitly unsupported for its
unresolved certificate-profile disagreement. No BLAS is bundled. Build support
does not imply binary release availability.

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
