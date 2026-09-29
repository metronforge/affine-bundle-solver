# Build Matrix Phase 2 — compiler/runtime/provider envelope

## Integration and execution identity

Canonical repository: `/projects/affine-bundle-solver`.
Previous main: `a668660bd49b7b2f015293ac84d00efbc424a8a3`.
Phase 1 integrated by fast-forward, without squash or a changed tree:
`046ce400d1e3faec211f1bc0df6d977ac3d673c9`, all 16 Conventional Commits.
Both existing worktrees were clean; no stash or uncommitted local source was
present. Historical divergent branches outside the integration path were left
untouched, including local-only refs. No branch or worktree was deleted.

Mandatory Checkpoint A: [main run 36625749601](https://github.com/metronforge/affine-bundle-solver/actions/runs/36625749601)
passed all 15 jobs on that exact SHA, including the cross-platform comparison.
Only after completion was `ci/build-matrix-phase2` created from that SHA.
The run metadata is retained in `phase2-evidence/checkpoint-a-main.json`.

Phase 2 implementation/review-fix SHA:
`01071607d170b7fb31e48ab74ea3e53c07286897`.
The final documentation/evidence commit follows this revision; its exact HEAD
is in the handoff and `git rev-parse ci/build-matrix-phase2` (not a self-referential
hash embedded in this report). Phase 2 is pushed, not merged.

## Envelope model and CI cost

Four new required jobs, not a Cartesian product:

| Runner / userspace | Compiler | Numerical provider | Scope |
|---|---|---|---|
| ubuntu-22.04, Ubuntu 22.04.5 | GCC 11.4.0 | reference BLAS/LAPACK 3.10.0 | full portability contract |
| ubuntu-22.04, Ubuntu 22.04.5 | Clang 14.0.0 | reference BLAS/LAPACK 3.10.0 | full portability contract |
| ubuntu-24.04, Ubuntu 24.04.5 | GCC 13.3.0 | pthread OpenBLAS 0.3.26 | full portability contract |
| ubuntu-24.04, Ubuntu 24.04.5 | Clang 18.1.3 | reference BLAS/LAPACK 3.12.0 | full portability contract |

The existing GCC 13 CMake/reference job additionally runs both complete property
batteries and emits its own certificate snapshot. Its compiler is now explicitly
selected/asserted so the artifact cannot silently misidentify a changed default.
The original x86 GCC portable/native and Clang deep jobs retain sanitizers,
publication/manuscript/performance inventory, BLAS/native comparisons and
release-candidate behavior. No deep job is replicated into the version matrix.
All ARM64/macOS jobs remain required. Total: 19 required workflow jobs.

Every new job configures with `ABS_ARCH_FLAGS=''`, builds, runs full applicable
CTest and both full property batteries, verifies runtime fenv and no contraction,
installs into a clean prefix, relocates it, hides the original build, and executes
external C/C++ CMake plus C pkg-config consumers without loader environment paths.
No job is continue-on-error. Only text/JSON evidence is newly uploaded.

## Observed userspace, compilers and runtimes

| Evidence | Ubuntu 22.04 x86_64 | Ubuntu 24.04 x86_64 | Ubuntu 24.04 ARM64 | macOS ARM64 |
|---|---|---|---|---|
| Image | 20260920.303.1 | 20260920.314.1 | 20260920.129.1 | 20260907.0337.1 |
| OS | 22.04.5 LTS | 24.04.5 LTS | 24.04 LTS | 15.7.9, build 24G830 |
| Kernel | 6.8.0-1064-azure | 6.17.0-1022-azure | 6.17.0-1022-azure | Darwin 24.6.0 |
| libc | glibc 2.35-0ubuntu3.15 | glibc 2.39-0ubuntu8.9 | glibc 2.39 | libSystem |
| GCC | 11.4.0 | 13.3.0 | 13.3.0 | not selected |
| Clang | 14.0.0 | 18.1.3 | 18.1.3 | Apple 17.0.0, clang-1700.0.13.5 |
| GCC OpenMP | libgomp 12.3.0 | libgomp 14.2.0 | libgomp 14.2.0 | — |
| Clang OpenMP | libomp 14.0.0 | libomp 18.1.3 | libomp 18.1.3 | Homebrew libomp 23.1.0 |
| libatomic | 12.3.0 | 14.2.0 | package recorded | not required |
| CMake | 3.31.6 | 3.31.6 | 3.31.6 | 4.4.3 |
| Inspection | GNU objdump 2.38 | GNU objdump 2.42 | GNU objdump 2.42 | Apple LLVM objdump 17 |

The oldest **actually tested source-build userspace** is Ubuntu 22.04.5 / glibc
2.35, not an inferred minimum from symbol tables. There is no claim of cross-distro
binary compatibility, a minimum kernel, or testing every compiler patch release.
No second ARM/Apple compiler generation was added: the Linux x86 representatives
give distinct front-end/version evidence without redundant platform multiplication.

## Compiler-compatibility audit

| Assumption | Evidence / disposition |
|---|---|
| OpenMP max reduction on double | Clang x86 emits generic atomic runtime calls; GCC and ARM paths differ. Full native/parallel/fenv tests run in every CMake configuration. Fixed missing runtime discovery, below. |
| `-frounding-math`, `-ffp-contract=off` | Identical strict flags retained; disassembly and dynamic tests pass on both generations, including FMA-capable x86 inspection and ARM scalar/SIMD forms. |
| Fast-math nonfinite handling | Phase 1 volatile bit-observation fix retained. Existing invalid/overflow tests and explicit nonfinite boundary tests run; no compiler-specific policy workaround. |
| AArch64 FPCR | Existing user-mode probe and subnormal/rounding negative controls retained; unsupported architectures still fail closed. |
| atomics/libatomic | `find_library(atomic)` missed Ubuntu's runtime-only location for Clang. Search now includes compiler implicit link directories and `libatomic.so.1`; all callers already used the variable. |
| C11 features | Existing C11 source/public headers compile under selected generations; CMake uses their default C dialect and build.sh retains its explicit language configuration. C/C++ external consumers pass. No claim about pre-GCC11/pre-Clang14. |
| warnings | Existing warning checks and compiler flags retained. Build logs preserve warnings (including existing Apple fast-router warnings); no warnings/tests suppressed for old compilers. |
| linker/RPATH | Same `$ORIGIN`/`@loader_path` installation contract; relocated consumers run with source/build unavailable. libatomic repair is link-only, not arithmetic. |
| BLAS ABI | Existing configure-time 15-symbol LP64 check plus complete semantic/certificate execution retained. Provider names alone do not earn support. |

## BLAS independence and semantic equality

Supported implementations: Ubuntu reference BLAS/LAPACK 3.10.0 and 3.12.0;
Ubuntu pthread OpenBLAS 0.3.26; the existing SciPy OpenBLAS path; macOS Homebrew
OpenBLAS 0.3.34. All use the solver's supported LP64 ABI. Reference jobs use
explicit distribution reference-library paths; the provider checker resolves
`ldd` files, rejects missing/mixed/wrong identities and records SHA-256 hashes.
Unit controls reject OpenBLAS mislabeled as reference, the reverse, mixed and
incomplete dependencies. This prevents alternatives symlinks manufacturing
spurious provider independence.

Accelerate remains **unsupported**, not reclassified by Phase 2: Phase 1 proved
that all routine symbols linked but an unchanged rank-deficient certificate mask
was 6 rather than 7 (unique generator code 6). OpenBLAS passed the same fixture.
No threshold was adjusted. Other providers, ILP64 and static BLAS are unverified.

Nine required snapshot participants: existing x86 GCC portable/SciPy,
Ubuntu24 GCC13/reference, Ubuntu22 GCC11/reference, Ubuntu22 Clang14/reference,
Ubuntu24 GCC13/OpenBLAS, Ubuntu24 Clang18/reference, ARM GCC, ARM Clang, Apple
Clang/OpenBLAS. Explicit filenames make a missing participant fail the aggregate.
The separate BLAS job additionally compares reference against SciPy OpenBLAS
with the same certificate-aware snapshot code, alongside its original battery.

Schema/equality definition stays in `tests/compare_builds.py`: status,
classification, certainty, rank and interval, certified status/rank/interval,
accepted-status mask, generation and verifier outcomes. Corpus: 39 deterministic
exact integer/dyadic cases × two seeds = **78 pairs**, including Phase 1's 15
extreme scales and their negative counterparts. Hashes bind exact stored inputs.
No residual, timing, last bit or contract-permitted fallback-route bit is an
equality key. Any disagreement among supported participants blocks CI.

## Range and rounding regression

- Private witness norm: all 2,098 exact binary powers from -1074 through 1023,
  in all four rounding modes; the Phase 1 range repair remains effective.
- Public strict verification: both signs of every power plus minimum-subnormal
  neighbors, largest subnormal/DBL_MIN/next normal, DBL_MAX and its predecessor.
- Exact compatible systems with zero rows accept infinite witnesses with zero
  radius; exact zero-row contradictions accept inconsistent witnesses with the
  correct sign. Invalid null vectors and zero contradictions are rejected.
- Nonzero cancelling products reach interval evaluation before rejection;
  assertions check caller-mode restoration on that error path too.
- Test-only compilation of the actual verifier intentionally leaks upward
  rounding on restoration; the same interval-rejection assertion must fail.
- Nearest-mode operational fixtures pin immediately adjacent stored values at
  the default compatibility threshold (both signs), dyadic rank neighborhoods
  and quality-gate brackets. No tolerance is widened. The source-row quality
  witness is x=1, not the least-squares minimizer; its delta/(2+delta) backward
  error analytically brackets the default threshold between exponents -46/-45.

Strict verifier coverage includes FE_TONEAREST, FE_DOWNWARD, FE_UPWARD and
FE_TOWARDZERO. Operational fixtures run in nearest mode; this is not a new
promise that the fast router is rounding-mode invariant.
The public range/rounding executable passes **219,070 assertions per platform**;
the private norm test additionally covers 8,392 exponent/mode combinations.

Decision differences: none in the required corpus. Diagnostic-only differences
are deliberately excluded from equality but finiteness/sign/zero conditions are
checked where mathematically required. The unchanged exploratory property battery
reports 155–157 known representation-loss cases across environments after very
large affine translations; those transform the stored binary64 problem itself.
They are retained with their existing category, not newly accepted by wider
tolerances. No hard property or range-robustness failures remain.

## Defects and review corrections

One new build portability defect: Ubuntu Clang 14 and 18 CMake builds failed with
undefined `__atomic_load` / `__atomic_compare_exchange`. All affected targets
already named ABS_ATOMIC_LIBRARY, but find_library returned NOTFOUND. Extending
discovery to runtime SONAME and compiler implicit directories fixed both actual
Actions jobs. No solver source or mathematics changed.

Independent review found two test/evidence gaps: early rejection fixtures had
not executed rounding-changing arithmetic, and the reference GCC13 artifact
relied on ambient compiler defaults. Both are repaired and revalidated; no minor
findings were deferred. The final report and actual final run were explicitly
left as mandatory completion work, not waived by review.

Public API/ABI changed: **no**. Numerical policies/thresholds/defaults changed:
**no**. Solver algorithms changed: **no**. New numerical defects: **none found**.

## Evidence history and results

- `36626595900`, source `3a474e2`: first envelope; both GCC representatives passed,
  both x86 Clang builds exposed missing libatomic. Failure logs retained.
- `36627025489`, source `1ba318f`: all 19 jobs passed after runtime discovery fix.
- `36627216544`, source `bc24fbd`: all 19 jobs passed with expanded range tests
  and 78-pair semantic snapshots; complete portability/version evidence retained.
- Review-fixed implementation: [run 36627551475](https://github.com/metronforge/affine-bundle-solver/actions/runs/36627551475),
  source `01071607d170b7fb31e48ab74ea3e53c07286897`; retained in its own evidence directory.

The review-fixed run completed **all 19 jobs successfully**, including all nine
snapshot participants and the final verification gate. Downloaded snapshots also
compare successfully locally: nine participants, 78 pairs. The final documentation-
inclusive HEAD is rerun and its exact run URL is supplied in the completion handoff.

Each new-version/ARM Linux job runs 47 CTests; macOS runs 46 (the Linux resource
fixture keeps its scope; portable allocation-failure coverage remains). Each
macOS run also retains the pre-existing Python resource fixture's explicit
Linux-only skip; it is not counted as exercised Linux resource behavior. Each
full property battery runs 8,335 equivalence checks without hard failures and
2,271 certificate checks without failures. Runtime control/subnormal and strict
contraction gates, relocated install/C/C++/pkg-config consumers and cross-version/
provider snapshots pass. Local full CTest: 47/47; both local full batteries pass.
Local loader environment was cleared to avoid an inherited trailing empty
LD_LIBRARY_PATH entry selecting stale root-level research DSOs.

Raw logs/JSON, source commit/tree, clean-state identity, compile commands,
package/libc/compiler versions, dependency resolution and DSO hashes live in
`phase2-evidence/<run>/`. Earlier failed runs are historical evidence, never
silently combined with final evidence. No scientific performance campaign ran.

## Future binary-release contract — analysis only

| Question | Recommendation and limit |
|---|---|
| CPU | x86-64 baseline (v1/SSE2), no AVX/FMA requirement in solver release code; AArch64 baseline ARMv8-A. Empty architecture flags here; packaging must explicitly audit ISA and test baseline hardware/emulation. External BLAS dispatch is its provider's responsibility. |
| Linux libc | Candidate x86 floor Ubuntu22.04/glibc2.35; build there, then test actual archives on newer userspaces. ARM64 floor currently Ubuntu24.04/glibc2.39, **not** inferred to be 2.35. No cross-distro binary guarantee yet. |
| Shared/static | Shared solver libraries with relative runtime lookup; no static support claim. |
| BLAS | External LP64 distribution BLAS/LAPACK, reference or tested OpenBLAS. Declare dependencies; do not bundle. Keep SciPy wheel linkage as research/source path, not the portable binary dependency contract. |
| OpenMP | Prefer GCC/libgomp on Linux to minimize runtime variants; declare libgomp and any required atomic runtime. Clang source builds retain libomp plus libatomic where required. |
| macOS | ARM64 only, deployment baseline macOS15 unless an older deployment target is independently qualified. Apple Clang, external Homebrew OpenBLAS/libomp; audit install names and dependency paths before packaging. No Accelerate, Intel or universal binary. |
| Dynamic dependencies | Linux libc/libm, selected BLAS/LAPACK, OpenMP and possibly libatomic; provider transitive libgfortran/libquadmath/libgcc/pthread dependencies must be inventoried. macOS libSystem plus OpenBLAS/libomp and provider transitive dependencies. C++ consumers add their standard library; solver ABI stays C. |
| Archive contents | Three shared solver libraries, public headers, exported CMake targets/config/version, pkg-config file, C/C++ examples, license/notices, checksums, source/tree/toolchain/dependency provenance and support constraints. No BLAS payload. |
| Names | For example `affine-bundle-solver-vVERSION-linux-x86_64-glibc2.35.tar.gz`, distinct `linux-aarch64-glibc2.39` and `macos15-arm64`; record compiler/provider in manifest. These are proposed names, not created artifacts. |

Readiness: **READY to begin a separate binary-release qualification milestone**,
not ready to claim portable prebuilt releases today. That next milestone must
validate actual extracted artifacts, exported dependency/ISA/symbol floors,
cross-userspace execution, macOS install/deployment names, licenses and checksums.
Those are next-milestone gates, not outstanding source-envelope failures.

Remaining unsupported: Windows/MSVC/MinGW/clang-cl, macOS Intel/universal,
Accelerate, static linking/bundled BLAS, untested compiler versions/providers,
all-distribution binary portability, AVX-specific releases. No release was
created, no binary archive published, and publish-release.yml is unchanged.

Lifecycle risk: Ubuntu22 hosted-runner deprecation is announced. Preserve its
userspace test in a container on a supported host before retirement, or explicitly
raise the floor; never silently relabel a newer glibc as the tested baseline.
[Runner inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2204-Readme.md),
[Ubuntu22 lifecycle](https://documentation.ubuntu.com/release-notes/22.04/).

## Preservation

All useful implementation and diagnostic source is on the named Git branch.
No new worktree or alternative source tree; the existing unrelated baseline
worktree was not changed. Local build output remains in `build-phase1/`; scratch
executables/logs are `/tmp/abs-phase2-*`, with no unique modified source there.
Durable evidence and this report are committed here. No branches were deleted.
Final branch SHA, commit list, clean-tree check and final Actions run are in the
completion handoff. Phase 2 is not merged automatically.

Implementation commits (diagnostic history is not squashed):

```text
80df3d9 docs: plan compiler and runtime support envelope
3a474e2 ci: verify compiler generations and linux userspace envelope
1ba318f build: discover clang atomic runtime outside gcc development paths
bc24fbd test: harden range rounding and cross-blas certificate coverage
0107160 test: pin reference compiler and verify interval rejection restoration
```

A documentation/evidence checkpoint follows. No separate support-matrix JSON
was added: it would duplicate the executable YAML matrix without an existing
packaging consumer. Future packaging should consume a validated manifest when
that consumer exists.
