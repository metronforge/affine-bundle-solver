# Build matrix Phase 1 report

## Identity and acceptance

Canonical repository: `/projects/affine-bundle-solver`.
Branch: `ci/build-matrix-phase1`.
Exact frozen base: `a668660bd49b7b2f015293ac84d00efbc424a8a3`.
The starting tree was clean on `main`; the named branch was created before edits.

Validated implementation: `a3f21df34a8f2310a832635c765198bd95357cd8`.
The final handoff HEAD also includes the diagnostic-parser fix and this
documentation/evidence checkpoint. Its exact SHA is reported in the handoff;
it is recoverable with `git rev-parse ci/build-matrix-phase1`. Embedding this
report commit's own hash in its contents would be self-referential.

Authoritative verification:
[Actions run 36623329644](https://github.com/metronforge/affine-bundle-solver/actions/runs/36623329644).
Earlier full green evidence, including the expanded 48-pair semantic corpus:
[run 36622975539](https://github.com/metronforge/affine-bundle-solver/actions/runs/36622975539),
source `c32fa9d836c26fdd4487870d4d7674a2384056da`.
The authoritative run completed successfully: all 15 jobs, including the
verification gate, passed. Phase 1's implemented matrix is verified.

## Original portability audit

| Category | Baseline finding | Disposition |
|---|---|---|
| Portable as-is | Strict `-O2 -frounding-math -fno-fast-math -ffp-contract=off`, rounding probe, public C ABI, LP64 BLAS symbol indirection, exported CMake targets, most semantic fixtures | Preserved |
| Linux-specific | `build.sh` and CMake SciPy discovery assume Linux wheels/`.so`; research/sanitizer scripts use ELF, `LD_PRELOAD`, `sha256sum` | Retained Linux research path; CMake system-provider path is portable |
| Linux-specific | `$ORIGIN`, `ldd`, Python `.so` names | CMake-native library suffix plus centralized Python paths; `@loader_path` and `otool` on macOS |
| Linux-specific | GNU `--wrap` in reusable QRCP test | Test-only source interception, same counters and matrix/pivot assertions on every OS |
| Linux-specific | `/proc/self/statm` plus `RLIMIT_AS` stream failure tests | Retained on Linux; additional production-allocator interception test on every platform verifies ENOMEM atomicity/retry |
| x86-specific | MXCSR inspection skipped elsewhere | Preserve historical test/target name; inspect AArch64 FPCR and fail closed on unknown architectures |
| Requires ARM equivalent | Runtime control-state/subnormal hazards | Compare full FPCR, input/output subnormal operations and rounding before/after each DSO load |
| Requires macOS equivalent | Hard-coded `-fopenmp`, GNU disassembly invocation and ELF symbol spelling, Bash empty arrays, `/bin/true`, Darwin `rusage` visibility | Imported OpenMP requirements; Xcode llvm-objdump; prefixed symbols and suffixed ARM mnemonics; portable shell handling; test-local Darwin feature macro |
| Requires macOS diagnosis | BLAS routine/symbol compatibility, binary64 `long double`, compiler recognition of finiteness bit tests | Tested Accelerate; selected OpenBLAS after a diagnosed semantic failure; two isolated portable fixes documented below |
| Out of scope | Windows, Intel macOS, packages, universal binaries, release publication, SIMD/performance optimization | No changes |

The original audit/implementation plan is retained in `phase1-plan.md`.

## Final required matrix

| Platform | Runner | Compiler | Router architecture flags | Solver BLAS/LAPACK | OpenMP |
|---|---|---|---|---|---|
| Linux x86_64 | ubuntu-24.04 | GCC 13.3.0 | empty / portable | SciPy OpenBLAS, plus existing system comparison | libgomp |
| Linux x86_64 | ubuntu-24.04 | GCC 13.3.0 | `-march=native` | SciPy OpenBLAS | libgomp |
| Linux x86_64 | ubuntu-24.04 | Clang 18.1.3 | empty / portable | SciPy OpenBLAS | libomp |
| Linux ARM64 | ubuntu-24.04-arm | GCC 13.3.0 | `ABS_ARCH_FLAGS=''` | Ubuntu reference BLAS/LAPACK 3.12.0 | libgomp 14.2.0 |
| Linux ARM64 | ubuntu-24.04-arm | Clang 18.1.3 | `ABS_ARCH_FLAGS=''` | Ubuntu reference BLAS/LAPACK 3.12.0 | libomp 18.1.3 |
| macOS ARM64 | macos-15 | Apple Clang 17.0.0 (clang-1700.0.13.5), Xcode 16.4 | `ABS_ARCH_FLAGS=''` | Homebrew OpenBLAS 0.3.34 (LP64) | Homebrew libomp 23.1.0 |

Observed ARM runner images: Ubuntu `ubuntu24-arm64`, image
`20260920.129.1`, kernel `6.17.0-1022-azure`; macOS `macos15`, image
`20260907.0337.1`, macOS 15.7.9 build 24G830, Darwin 24.6.0. Each job checks
`RUNNER_ARCH=ARM64` and `uname -m`. Exact per-run identities, compiler output,
configuration, compile commands, DSO dependencies, source/tree and DSO hashes
are in the provenance JSON and environment text artifacts. These are observed
versions, not promises about future rolling runner images.

## Verification results

The original deep x86 workflow remains intact: GCC portable/native, Clang,
system/SciPy BLAS independence, portable/native semantic comparison,
ASan/UBSan (three partitions), installation/consumption, full property batteries,
certified API/regressions, manuscript claims and performance-artifact checks.
The existing release-candidate job detects an ordinary commit and creates no
release package. Release/publish/manuscript/nightly workflow files are unchanged.

| Required check | Linux ARM GCC | Linux ARM Clang | macOS ARM Apple Clang |
|---|---|---|---|
| Configure/build | PASS | PASS | PASS |
| Runtime FP environment / rounding | PASS, FPCR 0x0 preserved | PASS, FPCR 0x0 preserved | PASS, FPCR 0x0 preserved |
| Strict contraction / negative controls | PASS | PASS | PASS |
| Full applicable CTest | 44 registered, PASS | 44 registered, PASS | 43 registered, PASS |
| Full equivalence battery | 8,335 checks, no hard failures | 8,335 checks, no hard failures | 8,335 checks, no hard failures |
| Full certificate battery | 2,271 checks, zero failures | 2,271 checks, zero failures | 2,271 checks, zero failures |
| Install, relocate, external C/C++ CMake and C pkg-config consumers | PASS | PASS | PASS |
| Shared-library resolution with original build unavailable | PASS | PASS | PASS |

macOS excludes the Linux-native RLIMIT_AS fixture; its pre-existing Python
RLIMIT_AS fixture explicitly reports its Linux-only scope. The additional
portable allocator-failure test passes on all three entries. No semantic test
is removed to accommodate a platform. The native full-range row-norm regression
checks four rounding modes and the new certificate regression checks 15 scales.

Runtime probes preserve x86 MXCSR FTZ/DAZ and all other control bits, compare
every FPCR bit on ARM, require both libraries to load, and exercise actual
subnormal input/output multiplication and directed rounding before/after each
load. Deliberate flushing/rounding constructors and a missing library are
rejected. Unsupported register architectures fail at compilation. FP state is
thread-local; existing OpenMP worker-fenv tests separately verify worker behavior.

Contraction inspection uses GNU objdump 2.42 on the Ubuntu ARM jobs and Apple
LLVM objdump 17.0.0 from Xcode on macOS. All three strict translation units are
inspected with OpenMP compile/include requirements; expected symbols and
nonempty instruction listings are mandatory. No prohibited fused instructions
were found. Scalar/vector, negated, alternating, extended and suffixed ARM
instruction forms have negative controls. x86 inspection retains its
FMA-capable target rather than passing vacuously on a non-FMA baseline.

## Cross-platform semantics

PASS: all four required artifacts agree on 24 fixed cases × two seeds = 48
case/seed pairs, including 15 extreme binary scalings. The comparison also
passed locally after downloading the independently produced artifacts.

The single comparison implementation is `tests/compare_builds.py`. Local
BLAS/native comparison and serialized snapshots use the same router semantic
key: status, certainty, rank, rank interval and classification. Snapshots also
compare certified status/rank/rank interval, accepted-status mask and generation/
verification outcomes. Exact integer/dyadic inputs are hashed. Missing, duplicate,
wrong-schema or incomplete evidence fails closed. Residuals, wall time, low bits
and route-only fallback diagnostics are not equality keys. Undecidable status
and failed proof outcomes are compared. No threshold was adjusted for agreement.

## Portability fixes and rejected configurations

1. Architecture-aware runtime FP probe; stricter missing-library and control-state
   checks preserve/strengthen the x86 behavior.
2. Native library discovery, macOS install RPATH, OpenMP target propagation,
   test interception and portable shell/disassembly handling.
3. Accelerate diagnosis: all 15 required routine symbols link, but the unchanged
   rank-deficient status-profile fixture returns mask 6 instead of 7. Unique
   generation returns code 6 from strict LU packing of the QRCP-selected,
   normalized source rows. A controlled same-run OpenBLAS build passes the
   unchanged fixture. Therefore macOS selects the smallest additional numerical
   dependency, Homebrew OpenBLAS; no bundled/static BLAS and no silent fallback.
4. Apple Clang folds an ordinary bit-based finiteness check under fast math.
   Volatile integer observation restores NaN/infinity/overflow rejection. See
   [isolated diagnosis and regression](apple-clang-nonfinite.md).
5. Apple ARM64 `long double` lacks extended exponent range. A power-of-two
   fallback restores witness row norms after square overflow/underflow, including
   finite saturation under directed rounding. See
   [isolated range fix](binary64-long-double.md). Ordinary representable arithmetic
   is unchanged; the broken range path now uses scaled arithmetic.

Public API/ABI changed: **no**. Thresholds, rank/classification policy, certificate
acceptance semantics and operational defaults changed: **no**. Observable buggy
macOS validation/range outcomes were repaired; this is not a claim that literally
every internal arithmetic operation is unchanged. Existing Linux semantics and
the expanded cross-platform corpus remain equal.

Accelerate is **not supported by Phase 1** despite link compatibility. Windows,
MSVC/MinGW/clang-cl, Intel macOS and universal binaries are unverified/out of scope.
No binary releases or packaging systems were added. Build support does not imply
binary release availability. No branch was merged and no release was created.

## Evidence and diagnostic history

`evidence/` retains downloaded text/JSON artifacts with their producing run IDs.
Earlier artifacts are historical/pre-fix evidence, never silently combined with
the final source identity:

- `36621071958`, source `178837a`: original x86 and ARM Linux passes; Darwin
  resource-field compilation failure, plus discovery of pipeline exit masking.
- `36621288617`, source `1353272`: Darwin OpenMP header requirement failure.
- `36621453691`, source `f0c80a5`: runtime build works; Bash 3.2 array handling,
  non-finite/overflow and Accelerate profile failures exposed.
- `36621966466`, source `46babd6`: isolated compiler bit-check reproducer and
  same-run Accelerate/OpenBLAS comparison; OpenBLAS fixes the profile fixture,
  neither provider fixes the compiler's finiteness checks.
- `36622306536`, source `99295ad`: first complete green workflow, but detailed
  property evidence exposes six additional macOS extreme-range findings.
- `36622975539`, source `c32fa9d`: range findings resolved; expanded 48-pair
  snapshot, full portability matrix and original deep x86 checks green.
- `36623329644`, source `a3f21df`: additionally verifies the private row norm
  through the full binary64 range in every rounding mode.

No retained scientific/performance campaign was run or mixed across revisions.
New artifacts contain logs, semantic JSON and provenance; no ARM binaries are
published. The original x86 workflow's existing temporary library artifacts and
release-publication behavior remain unchanged.

## Local verification and remaining limits

Development machine: Linux x86_64, GCC 15.2.0, CMake 4.2.3, Python 3.13.5,
NumPy 2.3.1 / SciPy 1.16.1, system OpenBLAS. Full local CTest passed 44/44;
both full property batteries passed; relocated CMake C/C++ and pkg-config
consumers passed. Baseline/pre-fix and repaired snapshots agree for the original
18-pair corpus. GitHub Actions, with pinned CI Python dependencies, is the
authority for ARM64/macOS and the required x86 configurations.

Remaining limits: these are rolling runner/compiler/provider versions, not every
possible build environment. The unchanged exploratory representation-loss
properties report 155 Linux and 156 macOS cases after very large affine
translations; those transformations change stored binary64 inputs. They are
not hard property failures or corpus disagreements. The six macOS range findings
were fixed rather than left under that exploratory exemption. Apple fast-router
NaN/fast-math compiler warnings remain visible; runtime input and diagnostics
regressions are required. No performance claim is made about portability fixes.

Phase 2 recommendation: broaden compiler/BLAS version coverage, stress range
and rounding transitions, and qualify any additional OS as a separate strict-FP
milestone before considering binary packaging. Revisit Accelerate certificate
availability separately; do not tune thresholds to make it pass.

## Preservation

All source changes are committed on the named branch with Conventional Commits;
the diagnostic history is retained. No worktree or alternative source repository
was created. Local build outputs are in `build-phase1/`; local scratch results
use `/tmp/abs-phase1-*`. The external-consumer test copies unchanged committed
consumer fixtures into its disposable test directory. No valuable modified source
exists only there. Durable report/evidence files live under `reports/build-matrix/`.
The final handoff verifies a clean worktree and lists the final commit SHA.

Implementation/diagnostic commits (full SHAs remain in Git):

```text
8a3499f test: verify architecture-aware floating point environment
87163dc build: make numerical test and install tooling portable
178837a ci: require arm64 builds and cross-platform semantic agreement
1353272 fix: expose darwin resource fields and propagate portability failures
f0c80a5 test: inspect strict openmp compilation in contraction gate
28e63c4 test: reject suffixed arm vector contraction mnemonics
0e87c6b test: diagnose macos contracts and support system bash arrays
46babd6 test: isolate macos blas provider contract failures
48664e3 fix: preserve nonfinite bit checks under apple clang fast math
8942212 test: use portable shell builtin in contraction controls
99295ad build: select tested openblas provider on macos arm64
d940dee fix: preserve witness norm range with binary64 long double
c32fa9d test: compare extreme-scale semantics across platform snapshots
a3f21df test: cover witness norm range under every rounding mode
1a02dc9 test: parse diagnostic bit patterns without aliasing assumptions
```

The final documentation/evidence commit follows this list without squashing it.

Technical references: [Arm FPCR](https://developer.arm.com/documentation/ddi0601/latest/AArch64-Registers/FPCR--Floating-point-Control-Register),
[Apple LAPACK routines](https://developer.apple.com/documentation/accelerate/lapack-functions),
[Darwin resource header](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/resource.h).
