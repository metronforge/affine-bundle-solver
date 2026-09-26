# Task-5 v3.7 final report

## 1. Terminal verdict

`QUALIFIED_WITH_RECONSTRUCTED_CONTROLS`

The SIGSEGV root cause was established, L-v3.7 was reconstructed and
semantically validated, the unchanged candidate completed the sole registered
qualification, and every registered gate passed. This verdict does not amend
v3.6 and does not authorize or claim a canonical 27-slot result.

## 2. Exact identities

- origin/main: `bb6c30d03191a92695b16d21581bfea6dce9942e`
- origin/main tree: `e621eef836c2e6edd633c03d657cc582e0e04344`
- candidate: `dd30ef900ff7f48d4fe97e79aae94b7e64c48741`
- candidate tree: `a89ce2def1fc1b2ef4644cc4d17f13c533b099b7`
- candidate parent: `bb6c30d03191a92695b16d21581bfea6dce9942e`
- candidate title: `perf: accelerate strict unique-row verification`
- harness branch: `perf/task5-v3.7-control-reconstruction`
- preregistered qualification head: `dd200678718a3fe48a40d5f89ca4887401dd8958`
- committed qualification-evidence head: `73de62f0d6dc82caadf0c8a6a899e992df5dc864`
- committed qualification-evidence tree: `10497e44837810e4b9f4d53d756f854768a4e514`

The final report/inventory wrapper commit is reported in the user-facing handoff
because a commit cannot contain its own SHA.

## 3. v3.6 preservation

The authoritative v3.6 campaign remains unchanged at
`/home/viktor/task5-v36-isolated-blas/task5-v36-isolated-blas/campaign-v3.6`.
Its verdict remains `CANDIDATE_NOT_QUALIFIED`; all 81 retained checksum entries
pass, and its `SHA256SUMS` hash is
`a51b4c6e90ed76a43af5b99badae93a29610540cd22bebbb698c4755c44a0fa0`.
No v3.6 observation was imported into v3.7.

## 4–5. Exact SIGSEGV cause and native localization

The v3.6 legacy worker initialized SciPy OpenBLAS 0.3.28 with one thread, then
raised that DSO to four through threadpoolctl. On V31-026's 192x192 `gelsd`
path, a newly activated SciPy OpenBLAS worker faulted in
`dgemm_itcopy_HASWELL`. The main thread stack was
`scipy_dgemm_ → scipy_dgebrd_ → scipy_dgelsd_ →
f2py_rout.flapack_dgelsd`. The solver combined API had not started.

Independent corroboration was a solver-free minimal process: one-to-four
thread mutation reproduced exit 139, while one-to-one completed. Initializing
SciPy OpenBLAS at four completed both without the solver and with the legacy
solver loaded. Thus the candidate, solver API, system OpenBLAS, and mixed symbol
interposition are not necessary causes. The precise unobservable third-party
internal invariant is bounded to the upward pool mutation interface.

## 6–7. Reconstruction and semantic equivalence

L-v3.7 is a newly rebuilt legacy-equivalent baseline from exact source commit
`f66cd87a7b198497cc53d63b2bb04b85c3e64f53`, tree
`4173cef889e0f1ec3ef60bc8aeadad26937a1711`. It is not described as the
original frozen v3.6 binary. The only protocol correction is:

- bootstrap the shared OpenBLAS setting at the maximum role budget (four);
- retain SciPy OpenBLAS at four using direct DSO-specific control;
- lower inactive system OpenBLAS to one using direct DSO-specific control.

No solver source, numerical algorithm, input, tolerance, workload boundary, or
candidate behavior changed. Original and reconstructed legacy controls agree in
all meaningful fields on six safe cases spanning small wide/square/tall,
scaled-edge, bounded-large wide, and bounded-large tall workloads. L/M/A agree
on targeted V31-026. Ten additional isolated L-v3.7 V31-026 processes complete
with full workload and router count one. Therefore legacy-equivalent semantics
are defensible; byte identity is neither claimed nor required.

## 8. Build, ABI, loader, affinity, and threads

- compiler/linker: GCC 15.2.0 / GNU ld 2.46
- generator/flags: Unix Makefiles, system BLAS, `-march=native`, strict kernels
  `-O2 -frounding-math -fno-fast-math`
- ABI: ELF64 little-endian x86-64, LP64 Fortran integers
- public header SHA-256 across L/M/A:
  `2172d6584e9f3c4518a0d7478ddc70fa8c02a5ea78bf9105d57f24265fa8595b`
- exported symbol-set SHA-256 across L/M/A:
  `7116ee323800282ee0bfe6fb977f05725087898460624e478454e1aa92829048`
- SciPy OpenBLAS 0.3.28 hash: `3e739a2435af49d2d938749f316aa338c65f41c9ae6615406e7cf83feb662f46`
- system OpenBLAS 0.3.32 hash: `be2e7d119279836105e0361be92c78dbcd8a6e7357e74339bdbb32a5195ee35e`
- affinity: CPUs `[1,3,6,8]`; active budget four
- L: SciPy OpenBLAS 4; system OpenBLAS, MKL, libiomp, libgomp 1
- M/A: system OpenBLAS 4; libgomp 1; SciPy/MKL/libiomp absent
- dynamic OpenMP/MKL teams disabled; Python hash seed zero

## 9. Four-cycle PDCA result

Exactly four cycles are recorded in `PDCA.md`:

1. Cycle 1 reproduced exit 139 and localized the fault to SciPy `dgelsd`'s
   OpenBLAS worker before the solver call.
2. Cycle 2 established the one-to-four mutation as causal with negative and
   falsification controls, then made the minimal test-first bootstrap repair.
3. Cycle 3 rebuilt and validated immutable controls, passed semantic/stability,
   ABI, BLAS, ENOMEM, and sanitizer gates, then pushed preregistration before
   candidate timing.
4. Cycle 4 completed the single 288-process qualification and independent
   review, then sealed all artifacts without rerunning performance.

## 10. Correctness, sanitizer, stability, ABI, and router matrix

| Gate | Result |
|---|---|
| Harness suite | 75 passed, 4 registered skips |
| Rebuilt L system-BLAS CTest | 22/22 passed |
| Rebuilt L SciPy-OpenBLAS CTest | 22/22 passed |
| Valid native ASan/UBSan partition | 8/8 passed |
| ENOMEM fixture | passed separately in normal build; invalid under ASan `RLIMIT_AS`, not counted there |
| Safe original/reconstructed comparisons | 6/6 meaningful-equal |
| Target V31-026 L/M/A | complete and meaningful-equal |
| Fresh L-v3.7 V31-026 stability | 10/10 complete |
| Public header/export ABI | identical |
| Candidate meaningful equality | 93/93 L/A and 93/93 M/A eligible pairs |
| Candidate router invariant | 96/96 processes, including warmups, exactly one |
| Candidate identity | exact unchanged commit/tree/binary |

The unchanged candidate's full v3.6 correctness matrix remains checksum-valid;
v3.7 adds fresh target, meaningful-field, router, runtime, and resource checks.

## 11. Qualification completeness

The committed schedule contains 288 unique observations: nine retained/excluded
warmups and 279 eligible processes. All 288 returned zero; no record is missing,
duplicated, excluded, imported, or selectively rerun. Every arm has exactly 31
eligible observations per V31-025/026/027 slot. Raw protocol digest
`c36b8649b89a755b36aa4839d3cf0d21a34b827c9c9a1b8be494a7a0e44e6d06`
matches the retained protocol object.

## 12–14. Timing results and registered performance gates

Ratios are candidate/reference. Intervals are paired-log two-sided 95%
intervals; the V31-025 upper bound is one-sided 95%.

| Slot | L/A API ratio (95% CI) | L/A E2E ratio (95% CI) | L/A E2E speedup | M/A API ratio (95% CI) | M/A E2E ratio (95% CI) |
|---|---:|---:|---:|---:|---:|
| V31-025 | 0.988744 (0.903874–1.038596) | 0.798953 (0.767463–0.893583) | 1.251639x | 0.986479 (0.896591–1.007523) | 0.986490 (0.896752–1.007730) |
| V31-026 | 0.228215 (0.223189–0.233712) | 0.215781 (0.208193–0.223216) | 4.634333x | 0.205951 (0.205874–0.216736) | 0.206065 (0.205980–0.216826) |
| V31-027 | 0.505920 (0.460909–0.508364) | 0.495622 (0.450453–0.499200) | 2.017665x | 0.678996 (0.664247–0.705093) | 0.679018 (0.664278–0.705143) |

Direct three-slot L/A E2E geometric mean: **2.270414x**, aggregate bootstrap
95% interval **2.142973–2.325095x**. The registered 1.5x point gate passes.

V31-025 M/A API one-sided upper ratio: **1.005952**, passing the `<=1.03`
non-regression gate. No M/A E2E median regresses on any slot.

## 15. RSS, thermal, order, and variance

Candidate RSS ratios versus the larger relevant control are 0.993, 0.999, and
1.009 for V31-025/026/027, below 1.10. All 288 processes record eligible
thermal state, zero throttle changes, fixed affinity, and matching thread
policy; maximum recorded temperature is 59.05 C.

V31-025 individual-process API CV is high (L 0.586, M 0.550, A 1.058). The
largest order-stratified log-ratio difference is 0.096465. These retained
observations do not reverse a gate: V31-025 M/A API order strata are both about
0.978, affected-path strata remain improvements, and both L/A V31-025 E2E
strata remain faster. No post-observation threshold or exclusion was added.

## 16. Independent review

The fresh-context reviewer independently regenerated the schedule, verified
every identity and runtime record, recalculated all 12 100,000-resample
comparisons exactly, and matched the aggregate and audit arithmetic. Its only
initial blocking finding was that raw/analysis artifacts had not yet been
tracked and no v3.7 `SHA256SUMS` existed. Those closure artifacts are now
committed, inventoried, verified, and pushed; no performance rerun was needed.
No Critical or Important scientific finding remains.

## 17. Evidence paths and inventory

Campaign root:
`/home/viktor/task5-v37-control-reconstruction/task5-v37-control-reconstruction/campaign-v3.7`

Key files are `ROOT-CAUSE.md`, `CONTROL-IDENTITIES.json`, `manifest.json`,
`schedule.json`, `PROTOCOL.md`, `SEMANTIC-EQUIVALENCE.md`, `PDCA.md`,
`timings/qualification.json`, `analysis/qualification.json`,
`analysis/audit.json`, `INDEPENDENT-REVIEW.md`, `COMMANDS.md`, and this report.
`SHA256SUMS` inventories all campaign evidence plus the external candidate
safety bundle and exact L/M/A binaries.

Candidate safety bundle:
`/home/viktor/task5-v37-candidate-dd30ef9.bundle`, SHA-256
`40b9193f5d048d3bcc80c0efb0409a11ad49ebc2b72d0a3bb53acd66c09bf2e0`.

## 18. Branch push status

The authorized analysis/evidence branch is pushed to origin. The candidate
branch was not pushed. The final remote head is reported in the handoff after
the report/inventory commit is pushed and reconciled.

## 19. Integration boundary confirmation

No solver PR was opened; no merge or direct main write occurred; no canonical
27-slot campaign was started; no history was rewritten or force-pushed; no
branch, worktree, bundle, patch, evidence, or stash was deleted or modified.
The preserved V3 workspace and all historical campaigns remain intact.

## 20. Single recommended next action

Authorize a separate integration task to use exact candidate `dd30ef9` and this
sealed v3.7 evidence for the solver-PR/27-slot decision; do not reinterpret or
append to v3.6.

`QUALIFIED_WITH_RECONSTRUCTED_CONTROLS`
