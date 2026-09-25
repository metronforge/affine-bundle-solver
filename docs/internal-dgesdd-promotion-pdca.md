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

- Normal portable system-OpenBLAS build succeeded; complete CTest: **18/18**.
  This includes compiler/link contract, directed-rounding, MXCSR, strict
  verifier, router/certificate agreement, and focused controls.
- `tests/test_dgesdd_compact_vt.py` first failed on clean DGESVD and then
  passed after conversion. `tests/test_dgesdd_candidate_semantics.py` passed
  wide, square, tall, zero-rank, full-rank, rank-deficient, inconsistent,
  decisive and near-threshold spectra, accepted-proof finiteness, and repeated
  deterministic public results. Rank-deficient reconstruction is generated as
  `b=A*x`; public residual/status controls verify that identity.
- `tests/compare_builds.py` compared unchanged DGESVD and candidate on 15
  cases × 2 seeds: all semantic fields agreed and maximum residual delta was
  `0.000e+00`.
- An additional certified-API differential compared all 20 exported result
  fields on 12 cases × 3 seeds (wide/square/tall, UNIQUE/INFINITE/
  INCONSISTENT/UNDECIDABLE, zero, rank-deficient, and gaps 0, 1e-14, 1e-11,
  1e-6). Integer semantics/return codes were exact; finite fields had maximum
  absolute delta `0.000e+00`; only matching documented NaN sentinels were
  treated as equal. N138 was not materialized because its external historical
  harness is explicitly out of scope; no campaign was run.
- `git diff --check` passed. Public include files were unchanged.

## Sanitizers

ASan/UBSan configured and built only after preloading the system ASan runtime:
the normal post-link MXCSR probe otherwise loads the instrumented library
before ASan. Focused compact-DGESDD semantic controls passed under ASan/UBSan
with no sanitizer diagnostic (`detect_leaks=0`). Leak checking against the
Python/Numpy host reports host-process allocations. Full sanitizer CTest is
**not PASS**: 17/18 tests completed, and `test_stream_storage` failed because
ASan could not allocate an 11,636,736-byte FakeStack virtual region. This is
the known virtual-memory/FakeStack environment limitation, not a candidate
test assertion failure.

## Bounded A/B timing and memory

System OpenBLAS and OpenMP were both fixed at one thread. Identical portable
builds used one warm-up, alternating baseline/candidate order, five measured
repetitions per case; reported values are median seconds with MAD.

| Core | DGESVD | DGESDD | ratio | VT storage (baseline → candidate) |
| --- | ---: | ---: | ---: | --- |
| wide 128×512 | 0.010118 ± 0.000351 | 0.010219 ± 0.000398 | 1.010 | 2,097,152 B → 524,288 B |
| square 256×256 | 0.001348 ± 0.000022 | 0.001387 ± 0.000035 | 1.029 | 524,288 B → 524,288 B |
| tall 1024×128 | 0.000443 ± 0.000011 | 0.000448 ± 0.000015 | 1.012 | 131,072 B → 131,072 B |
| large tall 2048×256 | 0.001531 ± 0.000025 | 0.001507 ± 0.000014 | 0.985 | 524,288 B → 524,288 B |

Combined-process peak RSS was 113,244 KiB and is diagnostic only; allocation
accounting is the meaningful isolated state-memory result. The wide core
saves 1,572,864 B (75%); square and tall compact VT shape equals the baseline
shape. The small timing deltas show no material bounded regression.

## Deviations and closure

The requested 177-case campaign was **not rerun**. No archive was modified;
nothing was pushed, merged, or submitted as a pull request. The sole
limitation is incomplete full-suite sanitizer coverage described above.
