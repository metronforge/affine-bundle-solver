# Portable binary SDK qualification

## Scope and result

This is binary **qualification**, not publication.  No GitHub Release, tag,
package-version change, Release Please change, bundled BLAS/OpenMP runtime, or
Windows artifact was created.

Qualification source commit: `ec2298606a8c5509741660b12c56cac47fe71ceb`
(`136edebd3c36bbb8478abd690d32cfdc6213696c` tree).

Final qualification run: [36635852198](https://github.com/metronforge/affine-bundle-solver/actions/runs/36635852198), **success**.
It completed the required source verification gate and the binary qualification
gate: three native builders, exact x86 archive forward consumption, and the
cross-platform package semantic comparison.

Archives are ordinary Actions artifacts retained for 30 days; they are not
repository blobs or release assets.  Compact retained evidence is in
[`qualification-evidence/`](qualification-evidence/).

## Qualified SDKs

| Target | Builder and compiler | CPU / userspace floor actually tested | External runtime contract | Result |
| --- | --- | --- | --- | --- |
| Linux x86_64 | Ubuntu 22.04.5, GCC 11.4 | x86-64 baseline, glibc 2.35 | `libblas3`, `liblapack3`, `libgomp1` | QUALIFIED |
| Linux ARM64 | Ubuntu 24.04, GCC 13.3 | ARMv8-A, glibc 2.39 | `libblas3`, `liblapack3`, `libgomp1` | QUALIFIED |
| macOS ARM64 | macOS 15, Apple Clang 17 | Apple Silicon, deployment target 15.0 | Homebrew `openblas`, `libomp` | QUALIFIED |

Linux uses the validated reference LP64 BLAS/LAPACK provider, not OpenBLAS.
The x86 archive built on Ubuntu 22.04 was checksum-verified and consumed,
without rebuilding the solver, on Ubuntu 24.04 / glibc 2.39.

### Artifact checksums

```text
296bdfdc5728a116adefd19cd070511c8d5070780290b971695388bbf8920dc3  affine-bundle-solver-qual-ec2298606a8c-linux-x86_64.tar.gz
2a19985ca31e58e329eb518c009d8a9dfcf21c127d1e535e9bd5d4c83a39c3db  affine-bundle-solver-qual-ec2298606a8c-linux-arm64.tar.gz
3772d847d841fd4a23a9b0c9f6b17b53d58f8b542f609bc786661e9c1080b815  affine-bundle-solver-qual-ec2298606a8c-macos-arm64.tar.gz
```

## ABI, loader, and dependency evidence

- Linux x86_64: ELF x86-64; three shared libraries use `SONAME`, `$ORIGIN`
  RUNPATH, reference `libblas.so.3`/`liblapack.so.3`, and `libgomp.so.1`.
  Highest solver GLIBC requirement is **2.29**, below the 2.35 builder floor.
- Linux ARM64: ELF AArch64; the same relative-loader and external dependency
  model.  Highest solver GLIBC requirement is **2.29**, below the tested 2.39
  floor.  This is not a claim of ARM64 compatibility with glibc 2.35.
- macOS ARM64: all three dylibs are arm64, use `@rpath` IDs and
  `@loader_path` rpaths, and have deployment target 15.0.  The intentionally
  external load names are `/opt/homebrew/opt/openblas/lib/libopenblas.0.dylib`
  and `/opt/homebrew/opt/libomp/lib/libomp.dylib`; no build or staging path is
  present.

For every target, disposable copies with a required BLAS or OpenMP name
replaced by an absent path failed to load.  The original SDK hashes remained
unchanged.  This confirms missing dependencies fail visibly rather than being
silently satisfied from an unrelated solver copy.

## Tests and semantic contract

Each native builder ran configure, build, rounding/runtime FP probes, strict
no-contraction inspection, full applicable CTest, both property batteries,
install, archive audit, and clean archive consumers.  CTest was 48/48 on both
Linux targets and 47/47 on macOS (the platform-applicable suite).

The clean archive checks built and ran C, C++, certified-diagnostic, and
pkg-config consumers using only the extracted prefix and declared external
dependencies.  The compact SDK corpus exercised UNIQUE, INFINITE,
INCONSISTENT, rank-deficient, wide/tall/zero-row, extreme-scale,
certificate-verification, operational-policy, and streaming behavior.

`compare_builds.py` reported semantic snapshot agreement for all four archive
participants (Linux x86 builder, Linux ARM64, macOS ARM64, and x86 forward
consumer): 78 fixed corpus case/seed pairs.  The policy/stream JSON was also
identical: status UNIQUE/rank 2/mask 7 and final stream status INCONSISTENT/
rank 2.  No last-bit residual or timing equality was required.

## Packaging changes and remaining boundary

The qualification workflow installs with CMake, adds only LICENSE, NOTICE,
BUILD-INFO, dependency instructions, and checksums, then packages that prefix.
It rejects leaked paths, wrong architecture, unexpected runtime paths,
GLIBC/GLIBCXX violations, missing external dependencies, and x86 VEX/AVX in
the portable solver libraries.  A Linux archive linked to OpenBLAS is now
explicitly rejected by this reference-BLAS qualification path, preventing an
incorrect dependency declaration.

Public API/ABI changed: **no**.  Numerical semantics, thresholds, policies,
and solver algorithms changed: **no**.

## Future publication recommendation

**Ready to attach platform binaries to a future GitHub release: YES**, for
these three qualified targets provided the release contract states the exact
external dependencies above.  Recommended format is a per-platform `.tar.gz`
SDK built from the CMake install prefix; keep solver libraries shared and keep
BLAS/OpenMP external.  Do not claim universal Linux compatibility: the tested
x86 source-binary floor is Ubuntu 22.04/glibc 2.35, and ARM64 has only been
tested on Ubuntu 24.04/glibc 2.39.  macOS requires Apple Silicon/macOS 15 and
the explicit Homebrew OpenBLAS/libomp installation names.

Unsupported or not implied: Windows, macOS Intel, universal binaries, static
solver/BLAS/OpenMP linkage, Accelerate, arbitrary Linux distributions or
compiler versions, and binary compatibility below the stated tested floors.
