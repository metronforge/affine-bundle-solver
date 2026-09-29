# Phase 1 implementation plan

Base: `a668660bd49b7b2f015293ac84d00efbc424a8a3` in
`/projects/affine-bundle-solver`, clean `main`; implementation branch
`ci/build-matrix-phase1`. The user's Phase 1 specification is the design brief.

## Design and constraints

Keep the deep Linux x86_64 workflow intact. Add three required portability
entries and a semantic artifact comparison to its verification gate. Use CMake
with empty architecture flags, system BLAS/LAPACK (test Accelerate first on
macOS), imported OpenMP targets, native shared library paths and install RPATHs.
Never change numerical policies, algorithms, public headers or release workflows.

## Tasks

- [ ] Runtime FP probe: preserve MXCSR checks, inspect AArch64 FPCR, check input
  and output subnormals and directed rounding before/after each library load.
  Add constructor-based negative tests, including a missing certified library.
- [ ] Structural FP gate: retain the ARM fused instruction coverage, support
  LLVM/Mach-O disassembly and symbol spelling, retain fail-closed regressions.
- [ ] Portable CMake and test tooling: OpenMP usage requirements, install RPATH,
  shared-library discovery; replace linker wrapping with test-only source
  interception and add portable stream allocation-failure coverage. Keep Linux
  RLIMIT_AS tests as additional OS-specific evidence.
- [ ] Semantic snapshots in `tests/compare_builds.py`: share the existing
  semantic key, add deterministic exact dyadic corpus plus certified outcomes,
  reject missing/duplicate/schema-mismatched artifacts and any disagreement.
- [ ] CI: build, full CTest, strict property batteries, install, external C/C++
  and pkg-config consumers; collect environment/provenance and semantic JSON.
  Compare x86 GCC portable against both ARM Linux compilers and Apple Clang.
- [ ] Run local full CTest and property batteries, commit logical checkpoints,
  push and dispatch actual Actions; diagnose failures without weakening gates.
- [ ] Record run evidence and support status in `docs/build-matrix.md` and
  `reports/build-matrix/phase1-report.md`; commit and leave a clean branch.

## Original audit

Portable as-is: strict compiler flags; fenv rounding probe; public C ABI;
Fortran LP64 BLAS symbol indirection; CMake exported targets; most C/Python
semantic fixtures; ARM fused-mnemonic list (but not its tool invocation).

Linux-specific: build.sh/SciPy wheel discovery, .so names, $ORIGIN, ldd,
GNU linker --wrap in QRCP test, /proc plus RLIMIT_AS stream fault tests,
sanitizer LD_PRELOAD, research/provenance scripts and binary release tooling.

x86-specific: MXCSR register guard; contraction checker deliberately adds
x86-64-v3 to exercise FMA; historical native/performance evidence.

Requires ARM equivalent: FPCR load-time control-state inspection with actual
input/output subnormal arithmetic and rounding checks. Requires macOS equivalent:
OpenMP flags/include paths, @loader_path, .dylib, Mach-O disassembly, portable
test interception, installed executable dependency inspection.

Out of scope: Windows, Intel macOS, packaging/releases, SIMD tuning, benchmark
claims, retuning numerical thresholds. Linux manuscript and performance checks
remain on their existing x86 jobs; build.sh remains the Linux research path.

## Review focus

Reject a vacuous disassembly, library-load failure, altered rounding or flushing
mode, incomplete snapshot, wrong runner architecture, and consumer dependencies
that accidentally resolve from a source/build tree. Test native Accelerate
symbols and actual solver semantics before considering another BLAS provider.
