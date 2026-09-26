# Task-5 v3.5 independent host qualification

## Terminal verdict

`MEASUREMENT_PROTOCOL_UNRELIABLE`

The frozen A/A calibration failed before qualification. Consequently, this report makes no Branch A performance-qualification claim and contains no official L/M/F/A or dense post-gating dataset. Branch A passed the correctness, ABI, sanitizer, and available portability checks, but Viktor should not authorize its PR on this evidence. Branch B is independently **READY** for Viktor to consider authorizing a later PR.

## Immutable identities

| Role | Branch/commit | Tree |
|---|---|---|
| origin/main and M | `1621d104a27eef3b12ec291384cac5f517da79f4` | `86dd1f677664160e40de72c0121e72fa5e54a83b` |
| L solver | `f66cd87a7b198497cc53d63b2bb04b85c3e64f53` | `4173cef889e0f1ec3ef60bc8aeadad26937a1711` |
| F flag-only | `ad8b8bea07feefdbb81fd791459816c5f118c053` | `aba3faaa4dc58585b70da16a9d8464ac24daa00c` |
| requested A | `0b9f9cf5a8d223801e2f17c08013f4a0936c632c` | `d085526dd951839963b654f5965bc87a24b77eba` |
| corrected A | `perf/task5-v3.5-row-axpy-verifier` at `69728e36e1fd2532503c0fdf2735d02c3322ad94` | `7bc54dc7c39352d2eeb52ac791ccd3967d9567a3` |
| requested B | `6d8a4651ffd25f187dd2d5cbe3a527e03d559b08` | `863747a36a5cb9edacc42d7a64f53b0a018131fc` |
| corrected B | `fix/manuscript-implementation-drift` at `b8d22717b1cb9a67fe6dd60cf0c8162cbed3d7c2` | `1c686f76a86632ce3b526cffe85857a047309414` |
| v3.4 comparison | `5409f2a0ce35e6471b158b92e32eb3af91f68cf6` | `f93452c2c4f4735b57b6643f2640de835a973535` |
| harness base | `65a73e4f8d9efe152d8870ddf8026627791f20fb` | `7d24f4a0fe848df4c0b6ee30aa48e4a2cb2d958e` |

The harness branch is `perf/task5-v3.5-row-axpy-validation`; its immutable preregistration commit is `292e1b3`. The final evidence commit is the branch tip containing this report. No PR exists for A or B. Main remained at `1621d104`; nothing was merged, force-pushed, tagged, released, or published.

The requested heads contained blocking test-infrastructure defects. As authorized, each was corrected test-first and fast-forward pushed before timing: A added `27a9f53f410df05a32c93f3092b4ad8eaecd71e2` and `69728e36e1fd2532503c0fdf2735d02c3322ad94`; B added `38fccf12403ccce46da060b6c1b145bf567452d7` and `b8d22717b1cb9a67fe6dd60cf0c8162cbed3d7c2`. No old-head performance data existed to retain or mix.

## Host and tools

Linux 7.0.0-34-generic x86_64 ran on an Intel Core Ultra 9 185H with 22 logical CPUs. Fixed P-core affinity was `1,3,6,8`; governor was `powersave`, turbo was enabled, and no thermal-zone temperature sensor was exposed. GCC was 15.2.0, CMake 4.2.3, Python 3.13.5, NumPy 2.3.1, SciPy 1.16.1, and GNU objdump 2.46. Clang was unavailable and is a skip, not a pass.

The solver linked system OpenBLAS. The Python runner also mapped MKL 2023.1, SciPy-bundled OpenBLAS, libiomp5, and libgomp. The complete paths are in every raw timing record.

## Cycle 1: correctness, portability, and sanitizer validity

Available build and workflow gates passed under GCC portable and native modes. A passed 31/31 CTests in each of system-native, system-portable, and SciPy-OpenBLAS builds; B passed 30/30 in each. Installed C/C++ consumers passed. M/A public headers and exported symbols were identical.

Valid ASan/UBSan executions passed the three native partitions for M and A; B's corresponding partitions passed too. A contaminated preload attempt is retained and expressly classified invalid. Clean runtime ordering, an uncontaminated directory, and a test-only FakeStack prewarm made the address-space-limited ENOMEM execution valid. Reentrancy, failure injection, and Python sanitizer semantics passed.

The exact-library harness passed 45/45. The frozen-row verifier differential compared 1,968 calls, 31,160 rows, and 1,502,768 entries with zero semantic failures. Its 228 differences were only signed-zero endpoint signs, which `fabs` makes contract-equivalent. Strict PBT output was byte-identical between M and A: 8,335 equivalence checks with exactly 154 registered pre-existing representation cases and no hard/new failure, plus 2,271 certificate-equivariance checks with zero failure.

The corrected FP gate fails closed for missing objdump, empty disassembly, missing target symbol, zero relevant instructions, unsupported architecture, and fused-operation mnemonics. A deliberately contracted fixture failed; normal builds printed `fp-contraction check: PASSED`.

## Cycle 2: review and effect separation

The new row pass preserves increasing-`k` term order per accumulator, removes only structural zeros, brackets the same scale/subtraction in the same directed modes, and differs only in contract-equivalent zero signs. Its `restrict` inputs do not overlap at call sites (`acc=evec`, `e=elo` or `ehi`). It has no static mutable state. Allocation count/order and ENOMEM behavior are unchanged. No Critical or Important finding remains.

Compared with v3.4, A is a different and stronger transformation: v3.4 evaluates each packed-LU column interval separately and still changes rounding mode per entry, whereas A performs two contiguous row-wide passes and changes mode twice per selected row. A's argument is supported by the frozen differential and fail-closed contraction check. The two candidates were not combined.

Five-pair diagnostic ratio-of-medians speedups (not qualification data):

| Slot | M→F API / E2E | F→A API / E2E | M→A API / E2E |
|---|---:|---:|---:|
| V31-025 | 1.035 / 1.002 | 0.992 / 1.013 | 1.026 / 1.015 |
| V31-026 | 1.038 / 1.193 | 2.248 / 1.597 | 2.333 / 1.906 |
| V31-027 | 1.014 / 1.001 | 1.148 / 1.107 | 1.164 / 1.109 |

This attributes the clear affected-path acceleration to the verifier algorithm, not primarily to the FP flag. The small sample and wide intervals do not qualify the branch.

## Cycle 3: frozen protocol and A/A decision

The complete protocol, seeds, order, affinity, analysis, exclusions, and gates were committed as `292e1b3` before timing. Synthetic equality, 2% regression, 4% regression, and clear-improvement tests passed. No observation was excluded or selectively rerun.

| Slot | Metric | M2/M1 point | One-sided 95% upper | Outcome |
|---|---|---:|---:|---|
| V31-025 | API | 0.988691 | 0.996433 | point/upper pass |
| V31-025 | end-to-end | 0.999589 | 1.004476 | point/upper pass |
| V31-026 | API | 0.995304 | 1.027933 | point/upper pass |
| V31-026 | end-to-end | 0.996767 | 1.018140 | point/upper pass |
| V31-027 | API | 1.023995 | 1.043563 | **upper fails** |
| V31-027 | end-to-end | 1.020223 | 1.046280 | **upper fails** |

All point estimates were near one and library fingerprints matched, but the preregistered upper bound and order-effect gates failed. A/A is therefore not reliable enough to adjudicate the 3% V31-025 margin.

The diagnostic thread matrix explains why future protocol work is warranted. On pinned CPUs with OMP=4, switching OpenBLAS from one to four threads changed API medians from 28/88/51 ms to 106/128/130 ms across the three slots. Pinned/unpinned behavior also diverged. These observations cannot rescue or alter the failed frozen decision.

## Cycle 4: qualification stop and Branch B

Because A/A failed, the official L/M/F/A run was not started. Therefore:

- direct contemporaneous L/A slot speedups and geometric mean: **not collected; no official claim permitted**;
- V31-025 M/A non-inferiority: **not tested; no qualification decision permitted**;
- official RSS/thermal/router/semantic gates: **not tested**;
- dense secondary: **not run**, because it was registered to occur only after official gating data were sealed.

Branch B is **READY**. `BIBTEX=bibtex ./build_paper.sh` produced 27 pages; the final pass had no unresolved references/citations or new overfull boxes. All eight claims reproduced, performance inventory and artifact audit passed, and publication readiness was true. Registry hash `3377160de6dd996896e3f63098c642bf3b0f2851b2bd59c2f1552f5e51bf743b` exactly matches `paper.tex`. B does not claim A's unmerged optimization; its flag, packed representation, factor-reuse, constants, path, and platform-variability statements match the code. No internal campaign labels appear in manuscript prose. Generated PBT artifacts were restored and the worktree is clean.

## Recommendations to Viktor

1. Authorize a PR for Branch A: **NO**. Correctness evidence is strong, but the required independent performance qualification is prohibited by failed A/A calibration.
2. Authorize a PR for Branch B: **YES**. It passed its independent correctness and publication-readiness audit.
3. Change benchmark thread configuration: **YES**. Before a new preregistered A qualification, isolate the Python/SciPy and solver BLAS runtimes and select one fixed configuration through calibration; this host's mandated all-four setting showed large mixed-runtime sensitivity. This is a recommendation for a future protocol, not a post-hoc reinterpretation of v3.5.

## Evidence locations

Campaign root: `/projects/research-assistant/task5-v35-host-qualification/task5-v35-row-axpy/campaign-v3.5`

- `manifest.json`, `PROTOCOL.md`, `COMMANDS.md`, and `ENVIRONMENT.json`: immutable identities and preregistration.
- `CORRECTNESS-MATRIX.md`, `INDEPENDENT-REVIEW.md`, `BRANCH-B-AUDIT.md`, and `MEASUREMENT-DECISION.md`: human-readable decisions.
- `evidence/cycle-01/`: raw build, test, sanitizer, ABI, consumer, and property logs.
- `timings/effect-diagnostic.json`: raw non-official M/F/A data.
- `timings/aa-calibration.json`: raw A/A observations.
- `timings/thread-matrix/`: raw thread/affinity diagnostics.
- `analysis/`: frozen A/A decision, diagnostic effect separation, and thread/library summary.
- `evidence/cycle-04/`: Branch B claim and publication-audit outputs.
- `PDCA.md`: the exactly four-cycle Ralph ledger.
- `SHA256SUMS`: complete retained evidence inventory.

Historical campaign evidence, the preserved V3 workspace, and the original dirty solver workspace were not altered. No stash was modified or dropped. No official ratios from different campaigns were multiplied, and no merge, PR, main push, history rewrite, release, or publication action occurred.
