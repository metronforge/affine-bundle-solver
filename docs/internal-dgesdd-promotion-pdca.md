# Internal DGESDD Compact-VT Promotion PDCA

## Verdict

**ACCEPTED_WITH_LIMITATION.** The corrected compact-DGESDD private core state
preserves the bounded semantic, strict-verification, and memory-safety gates.
The complete sanitizer battery remains environment-limited by ASan FakeStack
virtual-memory exhaustion, so it is not claimed as a full sanitizer PASS.

## Hypothesis and scope

The hypothesis was that the recovered compact-VT DGESDD core can replace the
clean DGESVD core without changing public solver semantics, classification,
certificates, or published numerical policy, while reducing SVD-state storage
and avoiding a material bounded runtime regression.

Base: `1e32be797d4ff021dacfffdec742851a9985b516` (`origin/main`).  This is a
descendant of clean Task-5 source `51fcae58490c038f604067835223daa4132bc0fe`.
The closed branch `fix/task5-certified-router-corrections` at
`bc04e80232e52a119115106d0d30a914c1eb3b15` was inspected only and was not a
parent of this branch.

Allowed changes frozen before source editing:

- add the private 14-argument `dgesdd_` LAPACK declaration and SciPy-prefix
  mapping;
- use JOBZ=`S`, `minmn=min(M,N)`, `U[M,minmn]`, `VT[minmn,N]`, `LDU=M`, and
  `LDVT=minmn` in `core_svd_state`;
- query/execute DGESDD with `WORK`, `IWORK=8*minmn`, checked counts, and
  deterministic cleanup;
- read both VT occurrences as `VT[l + (size_t)j * LDVT]`;
- add private-state and public semantic controls plus this report.

No public header, ABI, threshold, router-policy, certificate, oracle, or
`xt=NULL` harness change is included.

## Immutable inputs and comparison

All ZIPs passed `unzip -t` and retain their original hashes:

- `task5-corrected-evidence-20260922.zip`:
  `183594b3ee3e37193f0dcbfd39d120985586fde5ff9eb60d6e802076c6f40b0d`
- `vtstride-pdca-audit-20260921.zip`:
  `ac3e7b207bd8f8d164d26b974d59e8d94b23976b3f1895531670075af40a67a9`
- `task5-resume2-running-code.zip`:
  `3deae34f88def34e783a2bd2401612db2e3f893a8d8b9548694dcad54d7d9bca`

Diagnostic extraction was separate under `/tmp/dgesdd-pdca-diagnostic-20260925`.
Core source SHA-256 values were clean `51fcae`:
`76533f1a350c6a1d883f05c581762e69899fdc718a46ee8fd5e914955fd9ffdc`,
recovered dirty DGESDD:
`764823829e515e4db8e51cefb6eb69db1b6a0ecf4fd5c19d6f502caf3819fa9b`, and
preserved corrected DGESDD:
`6c76cef902199c7ee9f7232dfd0329cc1fb09a5a272ea39f92f5c90186376b09`.

The complete dirty-patch classification was: required driver conversion
(DGESDD declaration/call), compact layout (`VT`, `LDVT`, JOBZ=S), workspace
and failure handling (`IWORK`, query, cleanup), and the two known LDVT reads;
all changes to public headers, `bsolver.c`, certificate code, build scripts,
result JSON, and other dirty-source paths were unrelated and excluded.

## Checks

- The original normal portable system-OpenBLAS build passed **19/19** CTests.
  After review remediation, a fresh portable system-OpenBLAS build passed
  **20/20**. This includes compiler/link contract, directed-rounding, MXCSR,
  strict verifier, router/certificate agreement, and the new native-core test.
  A fresh SciPy-prefixed OpenBLAS build passed **4/4** focused DGESDD and
  link-contract CTests, including the native core path.
- `tests/test_dgesdd_compact_vt.py` first failed on clean DGESVD and then
  passed after conversion. `tests/test_dgesdd_candidate_semantics.py` passed
  wide, square, tall, zero-rank, full-rank, rank-deficient, inconsistent,
  decisive and near-threshold spectra, accepted-proof finiteness, and repeated
  deterministic public results. The new `tests/test_dgesdd_core_state.c`
  calls the actual private SVD state on wide, square, tall, rank-zero,
  rank-deficient, and near-threshold cores; it checks both minimum-norm `x`
  and the sign/rotation-invariant row-space projector from `Q`. Against the
  preserved dirty DGESDD source, the wide case produces an ASan
  heap-buffer-overflow at its first compact-VT read; against the corrected
  source all six core cases pass.
- `tests/compare_builds.py` compared unchanged DGESVD and candidate on 15
  cases × 2 seeds: all semantic fields agreed and maximum residual delta was
  `0.000e+00`.
- The original 12-case × 3-seed certified-API differential claim is withdrawn:
  loading both certified DSOs in one Python process aliases the first router
  dependency by SONAME, so it did not compare two implementations. Its zero
  delta must not be used as promotion evidence. The replacement
  `tests/compare_dgesdd_certified.py` launches one process per build, verifies
  the mapped router DSO and distinct binary hashes, then compares 36 records
  across all 20 certified fields, all non-timing router-meta fields, return
  codes, and deterministic diagnostics. Integer fields and nonfinite sentinels
  compare exactly; finite fields use explicit `1e-12` absolute/relative bounds.
  Result: **0 differences**, with raw records in
  `docs/internal-dgesdd-differential-results.json`. Each worker makes two
  router calls per record: one inside certified mode and one explicit router
  call; the latter agrees with the certified fast fields. N138 was not run.
- `git diff --check` passed. Public include files were unchanged.

## Sanitizers

ASan/UBSan configured and built only after preloading the system ASan runtime:
the normal post-link MXCSR probe otherwise loads the instrumented library
before ASan. Focused compact-DGESDD semantic controls passed under ASan/UBSan
with no sanitizer diagnostic (`detect_leaks=0`). The remediation's fresh
sanitizer build passed **3/3** focused DGESDD CTests, including the native
wide/square/tall core. Leak checking against the Python/Numpy host reports
host-process allocations. Full sanitizer CTest is **not PASS**: the prior run
completed 17/18 tests; `test_stream_storage` failed because ASan could not
allocate an 11,636,736-byte FakeStack virtual region. This is the known
virtual-memory/FakeStack environment limitation, not a candidate assertion
failure. A complete sanitizer suite was not rerun in remediation.

## Bounded A/B timing and memory

The original timing table is withdrawn: raw repetitions and a proved SVD
execution path were not retained. The replacement calls `core_svd_state`
directly, using the same test harness and compiler flags for both sources,
strict formation-guard objects from otherwise identical portable system-BLAS
builds, and object-symbol checks proving DGESVD versus DGESDD. OpenBLAS,
OpenMP, MKL, and BLIS were fixed at one thread. There was one warm-up and five
measured repetitions per core, alternating AB/BA order. Values below are
median seconds ± MAD; all raw samples, commands, and per-process peak RSS
appear in `docs/internal-dgesdd-timing-results.json`.

| Core | DGESVD | DGESDD | ratio | VT storage (baseline → candidate) |
| --- | ---: | ---: | ---: | --- |
| wide 64×128 | 0.003700 ± 0.000319 | 0.001794 ± 0.000006 | 0.485 | 131,072 B → 65,536 B |
| square 128×128 | 0.014943 ± 0.000091 | 0.006743 ± 0.000525 | 0.451 | 131,072 B → 131,072 B |
| tall 128×64 | 0.002312 ± 0.000056 | 0.001791 ± 0.000145 | 0.775 | 32,768 B → 32,768 B |
| wide 128×512 | 0.043239 ± 0.000981 | 0.012844 ± 0.000254 | 0.297 | 2,097,152 B → 524,288 B |

Per-process peak RSS was 13,612 KiB in both variants for these small runs and
is diagnostic only; allocation accounting is the meaningful isolated
state-memory result. For the measured wide 128×512 core the VT buffer saves
1,572,864 B (75%); this is a calculation for actual SVD core dimensions,
not an inference from public problem shape. Square and tall VT storage is
unchanged. These bounded direct-core timings show no regression and are not
publication benchmarks or evidence for whole-router speedup.

## Manuscript consistency

The local article manuscript `paper.tex` calls the small-core SVD an internal
rank-aware route (§6), and explicitly treats QRCP/SVD outputs as proposals
subject to source-rank provenance rather than proof objects. The change swaps
only that SVD driver and its private storage/layout; it does not alter the
paper's declared rank band (`1e-13` dependence, `1e-9` growth, `1e-14` local
arbiter), fast-status/interval semantics, minimum-norm construction, or the
independently checked nearby-status certificates. The manuscript's 29-case
timing/classification package is tied to source commit `67eef1f...` and a
named laptop, so these new direct-core measurements neither update nor
validate its published timing tables. No manuscript or immutable result was
changed; any future paper performance claim for this branch needs a separate
matched publication benchmark.

## Deviations and closure

Neither N138 nor the requested 177-case campaign was rerun. No archive or
manuscript file was modified; nothing was pushed, merged, or submitted as a
pull request. Limitations are incomplete full-suite sanitizer coverage,
machine-scoped direct-core rather than whole-router timing, and no new
publication benchmark.

## Finalization record

- Branch: `perf/dgesdd-compact-vt-candidate`.
- Base: `1e32be797d4ff021dacfffdec742851a9985b516` (`origin/main`).
- Reviewed candidate HEAD: `d08d5476bbc3519090a177fef389bba356d977a4`.
- Remediated implementation/test HEAD before this evidence-report commit:
  `0cdd358be40505e2a7a043b4dfc6d7dc9c1787f9`.
- Complete commit list through that implementation/test HEAD (this report
  commit cannot contain its own Git hash):
  - `317ab3f test: add compact VT differential controls`
  - `120c616 perf: use corrected compact DGESDD core state`
  - `e975812 docs: record DGESDD promotion PDCA`
  - `a521bd9 docs: fix PDCA report formatting`
  - `74a46ad test: register compact VT contract control`
  - `d08d547 docs: finalize DGESDD promotion record`
  - `f1ef7d8 test: prove compact DGESDD path and isolated differential`
  - `b7df8cd test: compare router integer diagnostics exactly`
  - `0cdd358 test: make differential evidence deterministic`
- Final net changed files: `CMakeLists.txt`, this report,
  `docs/internal-dgesdd-differential-results.json`,
  `docs/internal-dgesdd-timing-results.json`, `src/blas_symbols.h`,
  `src/bsolver_core.c`, `tests/compare_dgesdd_certified.py`,
  `tests/measure_dgesdd_core.py`, `tests/test_dgesdd_candidate_semantics.py`,
  `tests/test_dgesdd_compact_vt.py`, and `tests/test_dgesdd_core_state.c`.
- Final corrected `src/bsolver_core.c` SHA-256:
  `c02e398fea8408f74e4213ced2576e195490870b62eb5a246f2e00293a53bb5d`.
- Raw differential/timing artifact SHA-256 values:
  `89ca7de7799bcdbd98da02d71b942191b6276b1a9b46ed6c91aa576922cd97d6`
  and `fe031246e422b8bd4c21db90ae3099ec70d34248e1c30365856cff4568421018`.
- Sanitizer status: focused DGESDD ASan/UBSan **PASS**; full sanitizer suite
  **INCOMPLETE** due to the recorded ASan FakeStack virtual-memory limit.
- No N138 diagnostic and no 177-case campaign rerun was performed. Nothing
  was pushed, merged, or submitted as a pull request.
