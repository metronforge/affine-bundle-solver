# API Regression Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor and exercise the 36 available `abs-apps` Task 8 systems as an attributed, self-contained regression baseline before solving and certification APIs are separated.

**Architecture:** A frozen fixture manifest owns discovery, identity, attribution, oracle metadata, and selected expected fields. A Python runner binds the current combined APIs, distinguishes mathematical oracles from behavioral snapshots, and emits exact processed-ID/count evidence. Required CI runs the 36-case baseline and a controlled negative; a separate workflow runs the broader qualification matrix and records resources.

**Tech Stack:** C11 shared libraries, Python 3.12, `ctypes`, NumPy NPZ, JSON, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-30-api-regression-baseline-design.md`

## Global Constraints

- Freeze source provenance to `abs-apps` `ae9b662d7f5755418aa80f31ade1fffcbefebafd` and solver base `2741af01f0c0116347dbc81b21998f538690dcea`.
- Import exactly `T8-001` through `T8-032` and `T8-036` through `T8-039`; never synthesize missing `T8-033` through `T8-035`.
- The dimension partition must be derived from arrays and equal 26 square, 8 tall, and 2 wide systems.
- Selection depends only on dimension/shape coverage, not prior statuses or results.
- Preserve RASG BSD-2-Clause and SuiteSparse CC-BY-4.0 attribution and object authorship.
- Do not edit `abs-apps`, historical solver results, thresholds, verifier rules, public API, or ABI.
- Keep exact-source class, operational outcome, and nearby-certificate guarantees separate.
- Treat timing and semantically absent or unjustified fields as `dont_care`.
- A zero-case, partial, skipped, duplicate, missing, hash-mismatched, or crashed run must fail.
- All commits use Conventional Commits.

## Review Focus

- A valid manifest with an omitted NPZ must fail before execution, with the missing ID named (Task 1).
- A same-shape replacement NPZ must fail the file and canonical-array hashes (Task 1).
- Wide and tall arrays must pass correct row-major dimensions to `ctypes`, not be transposed (Task 2).
- The 36-case discrete contract must be identical at one and two BLAS threads;
  floating diagnostics must satisfy `atol=1e-12` or `rtol=1e-10`. T8-038
  `eta_inconsistent` must be bit-for-bit invariant and verifier-accepted after
  replacing the unstable full-row-rank residual witness (Task 2).
- An operational status that differs from the exact class must remain a passing, explicitly separated observation when policy semantics justify it (Task 3).
- A controlled wrong expected field must make the runner fail while preserving all on-disk fixtures and expectations (Task 5).

---

### Task 1: Frozen fixtures, identity, and attribution

**Files:**
- Create: `tests/fixtures/api-regression/inputs/T8-001.npz` through `T8-032.npz`, `T8-036.npz` through `T8-039.npz`
- Create: `tests/fixtures/api-regression/manifest.json`
- Create: `tests/fixtures/api-regression/THIRD_PARTY_NOTICES.md`
- Create: `tests/api_regression_corpus.py`
- Create: `tests/test_api_regression_corpus.py`

**Interfaces:**
- Produces: `load_manifest(root: Path) -> dict`, `discover_cases(root: Path, manifest: dict) -> list[FixtureCase]`, `canonical_float64_sha256(array: np.ndarray) -> str`, and immutable `FixtureCase(case_id, path, A, b, metadata)` records.
- Consumes: the 36 exact NPZ files and Task 8 metadata from the frozen `abs-apps` SHA.

- [ ] **Step 1: Write failing corpus identity tests**

Add `unittest` cases named `test_discovers_exact_expected_ids`, `test_shape_partition`, `test_missing_fixture_fails_with_id`, `test_same_shape_replacement_fails_hash`, `test_duplicate_manifest_id_fails`, and `test_nonfinite_or_wrong_dtype_fails`. Assert the exact 36-ID set and `(square, tall, wide) == (26, 8, 2)`.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -m unittest tests/test_api_regression_corpus.py -v`

Expected: import/file failure because `api_regression_corpus.py` and fixtures do not exist.

- [ ] **Step 3: Import exact binary fixtures and write attribution**

Mechanically copy the 36 NPZ files from the frozen `abs-apps` paths. Write `THIRD_PARTY_NOTICES.md` with the RASG copyright and BSD-2-Clause text, the four SuiteSparse object credits and CC-BY-4.0 link, both collection citations/DOIs, and the `abs-apps` generated-case credit. Do not copy SDSS artifacts because their three cases were not materialized.

- [ ] **Step 4: Generate the initial manifest**

For every entry record `case_id`, relative path, shape, NPZ SHA-256, canonical little-endian contiguous `A_sha256` and `b_sha256`, frozen repository SHA/path, source category, upstream object/revision/hash where applicable, transformation, and attribution key. Reject any source ID outside the exact 36-ID set.

- [ ] **Step 5: Implement strict corpus discovery**

Implement the Task 1 interfaces in `tests/api_regression_corpus.py`. Load with `allow_pickle=False`; require two arrays named `A` and `b`, binary64 dtype, `A.ndim == 2`, `b.shape == (m,)`, finite values, exact manifest/file set agreement, unique IDs, and all three hashes.

- [ ] **Step 6: Run corpus tests and confirm GREEN**

Run: `python -m unittest tests/test_api_regression_corpus.py -v`

Expected: all identity, missing-file, replacement, duplicate, dtype/finiteness, and shape tests pass; summary reports 36 IDs and 26/8/2 shapes.

- [ ] **Step 7: Commit fixture identity milestone**

```bash
git add tests/fixtures/api-regression tests/api_regression_corpus.py tests/test_api_regression_corpus.py
git commit -m "test: add attributed API regression fixtures"
```

### Task 2: Current API binding and complete execution accounting

**Files:**
- Create: `tests/api_regression_binding.py`
- Create: `tests/api_regression_runner.py`
- Create: `tests/test_api_regression_runner.py`
- Modify: `tests/fixtures/api-regression/manifest.json`

**Interfaces:**
- Consumes: `FixtureCase` and strict discovery from Task 1; current public structs/functions from `certified_api.h` and `operational_policy.h`.
- Produces: `PolicyValues`, `OperationalObservation`, `CertificateObservation`, `CombinedObservation`, `call_combined(case, policy, mode) -> CombinedObservation`, and `run_corpus(config) -> RunSummary` with discovered/executed IDs and per-case observations.

- [ ] **Step 1: Write failing ABI and accounting tests**

Add tests `test_default_combined_call_matches_public_layout`, `test_tall_and_wide_dimensions_are_not_transposed`, `test_run_summary_executes_all_discovered_ids`, `test_no_solution_vector_is_reported_as_exposed`, `test_partial_execution_fails`, and `test_semantically_absent_fields_are_not_compared_as_numbers`.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -m unittest tests/test_api_regression_runner.py -v`

Expected: import failure for the missing binding/runner.

- [ ] **Step 3: Implement versioned `ctypes` layouts**

Mirror `BSOperationalPolicyV1`, `BSOperationalResultV1`, `BSCertifiedResult`, and `BSCombinedSemanticResultV1` exactly. Bind `bs_default_operational_policy`, `bsolve_certified_policy_api`, and the legacy diagnostic API. Preserve row-major contiguous arrays and use `xt=None`, `sp=1`, `qv=2`, `alpha=2`, a frozen seed, and `full=0`.

- [ ] **Step 4: Implement observation normalization**

Normalize enums to named values, preserve NaN as semantic absence, omit elapsed time from equality, mark `x` as `not_exposed_by_current_api`, and keep operational, exact-source, and certificate namespaces separate. Capture return code, status/certainty/rank interval, residual/relative-reference/backward-error fields, mask/etas, generator/verifier codes, and exact verification level.

- [ ] **Step 5: Implement complete-run accounting**

`run_corpus` must compare discovered IDs, attempted IDs, completed IDs, and expected IDs; any mismatch raises a diagnostic containing the missing/extra IDs. Update manifest behavioral expectations only from a separate explicit `--record` mode that refuses a dirty tree or wrong source SHA.

- [ ] **Step 6: Record fresh current-main observations**

Run the runner against the worktree build, record stable fields only, and classify every recorded field as `invariant`, `behavior`, or `dont_care`. Never write timing to expectations.

- [ ] **Step 7: Run runner tests and the 36-case baseline**

Run: `python -m unittest tests/test_api_regression_runner.py -v`

Run: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ABS_CERT_UNIQUE_THREADS=1 python tests/api_regression_runner.py --expect-count 36`

Expected: tests pass and runner reports `discovered=36 attempted=36 completed=36` with the exact ID set.

- [ ] **Step 8: Commit API execution milestone**

Before committing, run `tests/test_certificate_thread_determinism.py`. The
pre-fix T8-038 result (`2.026...` at one thread versus `2.106...` at two)
must fail; the generator fix and full 36-case cross-thread AC must pass without
changing verifier rules or thresholds.

```bash
git add tests/api_regression_binding.py tests/api_regression_runner.py tests/test_api_regression_runner.py tests/fixtures/api-regression/manifest.json
git commit -m "test: record combined API regression behavior"
```

### Task 3: Independent mathematical oracle and semantic assertions

**Files:**
- Create: `tests/api_regression_oracle.py`
- Create: `tests/test_api_regression_oracle.py`
- Create: `tests/fixtures/api-regression/oracles.json`
- Modify: `tests/api_regression_runner.py`

**Interfaces:**
- Consumes: exact arrays/metadata from Task 1 and normalized observations from Task 2.
- Produces: `OracleResult(case_id, exact_status, rank_a, rank_augmented, method, premises, evidence)` and `verify_semantic_layers(observation, oracle) -> list[CheckResult]`.

- [ ] **Step 1: Write failing oracle tests**

Cover one square graph construction, `T8-008` wide, `T8-010` tall, transition cases on both sides of D/G, all four `T8-012/013/016/017`, one RASG-derived case, and all four SuiteSparse objects. Assert the rank relation and exact class independently of the operational result.

- [ ] **Step 2: Run oracle tests and confirm RED**

Run: `python -m unittest tests/test_api_regression_oracle.py -v`

Expected: import/file failure for the absent oracle implementation.

- [ ] **Step 3: Implement analytic and exact-rank oracle methods**

Use the stored construction proof for deterministic graph/cycle/repeated-path/transition inputs. For external arrays, convert each binary64 value exactly with `as_integer_ratio`, row-scale powers of two to integers, and use modular Gaussian elimination. A full-column-rank modular witness proves exact full column rank; any deficient or inconsistent result must have a separate analytic or exact elimination proof rather than a numerical rank guess.

- [ ] **Step 4: Persist checkable oracle evidence for all 36 cases**

Write `oracles.json` with exact status, ranks, method, premises, and any modular prime/pivot witness. Bind every entry to `A_sha256` and `b_sha256`. Import retained exact-rational conclusions for `T8-012/013/016/017` only after rechecking matching hashes and derivation.

- [ ] **Step 5: Add semantic-layer checks**

Assert API exact-source fields remain `UNKNOWN/NOT_VERIFIED`; do not require operational status to equal the oracle; require certificate mask bits to agree with generator/verifier success and finite eta; require the legacy certificate projection to match the operational status only when that mask bit is accepted.

- [ ] **Step 6: Run oracle and corpus regression tests**

Run: `python -m unittest tests/test_api_regression_oracle.py tests/test_api_regression_runner.py -v`

Expected: all 36 hashes have independent oracle records; special four remain exact `INCONSISTENT` while policy-dependent operational observations are allowed.

- [ ] **Step 7: Commit oracle milestone**

```bash
git add tests/api_regression_oracle.py tests/test_api_regression_oracle.py tests/api_regression_runner.py tests/fixtures/api-regression/oracles.json
git commit -m "test: separate exact and operational regression oracles"
```

### Task 4: Atomic conditions, reachability CNF, and real-case MC/DC

**Files:**
- Create: `tests/api_regression_decisions.py`
- Create: `tests/test_api_regression_decisions.py`
- Create: `reports/api-regression/mcdc.json`
- Create: `reports/api-regression/baseline-report.md`

**Interfaces:**
- Consumes: Task 2 observations across declared policies and Task 3 oracle evidence.
- Produces: `DecisionVector`, `derive_conditions(observation) -> DecisionVector`, `emit_reachability_cnf() -> CNFModel`, and `find_mcdc_pairs(vectors) -> CoverageReport`.

- [ ] **Step 1: Write failing decision-model tests**

Test valid-input, backend-success, resolved-rank, operational-compatibility, full-column-rank, UNIQUE-quality, and per-profile generator/verifier/finite-eta atoms. Test that CNF rejects impossible one-hot/status combinations and that an MC/DC pair changes only its target atom and decision.

- [ ] **Step 2: Run decision tests and confirm RED**

Run: `python -m unittest tests/test_api_regression_decisions.py -v`

Expected: missing module failure.

- [ ] **Step 3: Implement the bounded decision model and CNF**

Derive conditions only where observable fields and inspected source justify them. Encode one-hot operational outcomes, invalid/failure reachability, resolved-rank implications, UNIQUE/INFINITE/INCONSISTENT/UNDECIDABLE necessary conditions, certificate mask equivalences, and legacy projection rules. Label one-way implications explicitly.

- [ ] **Step 4: Search real observations for MC/DC pairs**

Use only the 36 real fixtures plus explicit policy variants. Store case ID, policy, complete condition vector, changed target, and changed decision. Require `T8-012/013/016/017` to retain exact-oracle separation. Record every atom without a real pair as uncovered; keep any purpose-built gap fixture in a distinct `synthetic_gap_fixture` section.

- [ ] **Step 5: Generate the baseline report**

Include corpus inventory distinctions, source revisions, size table, attribution, input-to-output mapping, exact oracle/method, semantic mismatch discussion, CNF, MC/DC table, uncovered conditions, test/CI mapping, resource measurements available at generation time, and post-split rerun criteria. Include the required table columns verbatim.

- [ ] **Step 6: Run decision tests and validate report artifacts**

Run: `python -m unittest tests/test_api_regression_decisions.py -v`

Run: `python -m json.tool reports/api-regression/mcdc.json >/dev/null`

Expected: tests pass; every claimed pair satisfies strict masking MC/DC; report lists uncovered atoms rather than fabricating pairs.

- [ ] **Step 7: Commit decision-analysis milestone**

```bash
git add tests/api_regression_decisions.py tests/test_api_regression_decisions.py reports/api-regression
git commit -m "test: document API decision MC/DC coverage"
```

### Task 5: Required PR/main CI and controlled negative

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/api_regression_runner.py`
- Modify: `tests/test_api_regression_runner.py`

**Interfaces:**
- Consumes: the 36-case runner from Task 2 and semantic checks from Tasks 3-4.
- Produces: CLI `--expect-count 36`, `--expect-ids-from manifest`, and `--inject-wrong-expected CASE:FIELD`; the injected mode must fail with that case/field named.

- [ ] **Step 1: Write failing negative-control tests**

Add tests proving that wrong in-memory status/rank/mask expectations return nonzero, identify the exact case/field, leave fixture/manifest hashes unchanged, and that zero/partial execution cannot pass.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `python -m unittest tests/test_api_regression_runner.py -v`

Expected: negative-mode tests fail because the CLI does not yet exist.

- [ ] **Step 3: Implement non-mutating negative injection**

Parse exactly one `CASE:FIELD`, clone the loaded expectation in memory, replace it with a type-valid wrong value, run ordinary comparison, and require the expected mismatch diagnostic. Never rewrite JSON or NPZ files.

- [ ] **Step 4: Add named required CI steps**

In every `build-and-test` matrix job, run the positive 36-case command with single-thread limits. Add a shell step that fails if the intentionally corrupted command exits zero and also fails unless stderr names the intended case/field. The workflow already runs on every PR and push to `main`; do not add path filters.

- [ ] **Step 5: Run local positive and controlled-negative commands**

Run: `python tests/api_regression_runner.py --expect-count 36`

Run: `python tests/api_regression_runner.py --expect-count 36 --inject-wrong-expected T8-001:operational_status`

Expected: first exits 0 with all 36 IDs; second exits nonzero naming `T8-001` and `operational_status`.

- [ ] **Step 6: Run workflow syntax/static tests**

Run the repository's workflow/YAML validation if present, then inspect `.github/workflows/ci.yml` with `git diff --check`. Assert the two new named steps exist through a small `unittest` that parses the workflow text if no YAML dependency is available.

- [ ] **Step 7: Commit CI gate milestone**

```bash
git add .github/workflows/ci.yml tests/api_regression_runner.py tests/test_api_regression_runner.py
git commit -m "ci: require API regression corpus"
```

### Task 6: Separate qualification workflow and final evidence

**Files:**
- Create: `.github/workflows/api-regression-qualification.yml`
- Create: `tests/api_regression_qualification.py`
- Create: `tests/test_api_regression_qualification.py`
- Create: `reports/api-regression/qualification.json`
- Modify: `reports/api-regression/baseline-report.md`

**Interfaces:**
- Consumes: all Task 1-4 interfaces and the declared policy/invocation matrix.
- Produces: `QualificationSummary` with exact unique IDs, expected/attempted/completed invocation counts, per-mode results, wall seconds, peak RSS, compiler/BLAS/thread configuration, and source/binary identities.

- [ ] **Step 1: Write failing qualification accounting tests**

Test matrix-derived invocation count, exactly 36 unique IDs, missing-mode failure, resource fields, source/binary SHA fields, and rejection of a summary with zero or skipped invocations.

- [ ] **Step 2: Run qualification tests and confirm RED**

Run: `python -m unittest tests/test_api_regression_qualification.py -v`

Expected: missing module failure.

- [ ] **Step 3: Implement qualification runner**

Execute all 36 fixtures under legacy diagnostics, default policy, and the predeclared custom compatibility policies used for semantic boundary cases. Derive total expected invocations from the checked-in matrix. Record wall time and process peak RSS as measurements, never pass/fail performance thresholds.

- [ ] **Step 4: Add separate qualification workflow**

Create a pinned-actions workflow triggered by `workflow_dispatch`, a weekly schedule, and push to `main`. Build once in the reference portable GCC configuration, enforce single-thread settings, run the qualification command, validate JSON/counts/IDs, and upload the JSON artifact with `if-no-files-found: error`.

- [ ] **Step 5: Run local qualification and update report**

Run: `python tests/api_regression_qualification.py --expect-unique-cases 36 --output reports/api-regression/qualification.json`

Expected: exact configured invocation count, 36 unique/complete case IDs, zero skips/crashes; report states local wall/RSS costs and does not generalize them to other hosts.

- [ ] **Step 6: Run full verification before completion**

Run: `./build.sh`

Run the existing CI regression loop from `.github/workflows/ci.yml`, compile/run `tests/test_operational_policy.c`, run all new `unittest` modules, run the positive baseline, run and observe the expected controlled-negative failure, and run qualification. Also run `git diff --check`, JSON validation, fixture SHA validation, `git status -sb`, and recheck both frozen upstream SHAs.

Expected: all positive checks pass; controlled negative fails for the intended mismatch; discovered/executed count is 36; qualification count matches its matrix; no `abs-apps` change exists.

- [ ] **Step 7: Complete report and commit**

Update the report with exact commands, final solver branch/commit predecessor, fixture hashes, processed counts, MC/DC gaps, local resources, CI job names, attribution, and post-separation rerun criteria.

```bash
git add .github/workflows/api-regression-qualification.yml tests/api_regression_qualification.py tests/test_api_regression_qualification.py reports/api-regression
git commit -m "ci: add API regression qualification"
```

- [ ] **Step 8: Request final code review and address findings**

Review the complete branch against the spec, especially mathematical/operational/certificate separation, exact discovery accounting, third-party notices, and CI non-vacuity. Re-run affected tests after every correction and use Conventional Commits for fixes.
