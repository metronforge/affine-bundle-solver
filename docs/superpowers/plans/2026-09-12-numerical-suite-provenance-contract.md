# Numerical Suite Provenance Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and verify a fail-closed, machine-scoped, hash-bound contract for a future main numerical-suite evidence package without running or changing the numerical protocol.

**Architecture:** A pure `numerical_suite_contract` module owns protocol/schema/provenance validation and atomic package publication. The existing numerical runner retains all generators and C calls but delegates evidence recording, exact library binding, and eligibility checks to that module. Claim auditing and CI consume the pure validator without executing numerical work.

**Tech Stack:** Python 3.12, `unittest`, NumPy/SciPy, scikit-learn, threadpoolctl, JSON/SHA-256, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-12-numerical-suite-provenance-design.md`

## Global Constraints

- Base is exactly `86b050f931099e869d11f548de444f8221474d3b` on branch `provenance/numerical-suite-contract`.
- Never run `build.sh`, `experiments/rerun_numerical_suite.py`, a solver/LAPACK call, benchmarks, PBT, regression suites, manuscript compilation, or production-size matrix construction.
- Never modify `src/`, `include/`, `paper.tex`, `results/`, `build.sh`, `experiments/synthetic_bench.py`, PBT reports, or the two protected figures.
- Preserve the exact existing generators, distributions, dimensions, seeds, warmups, repetitions, calls, timing sources, and OpenMP `1,2,4` schedule.
- Tests are fixture-only and mock CDLL/build/runtime boundaries; they never load `libaffine_bundle_solver.so`.
- Candidate files are not generated in this iteration.

---

### Task 1: Dependency closure and adversarial RED suite

**Files:**
- Create: `requirements-numerical-suite.txt`
- Create: `tests/test_numerical_suite_contract.py`

**Interfaces:**
- Consumes: exact pins from `requirements-ci.txt` and the immutable protocol inventoried from `experiments/rerun_numerical_suite.py`.
- Produces: literal fixture expectations for `CANONICAL_SECTIONS`, `CANONICAL_CASE_IDS`, schema validators, build binding, package audit/publication, runner integration, registry state, and CI behavior.

- [ ] **Step 1: Resolve the Digits dependency closure in a disposable environment**

Create `/tmp/abs-numerical-suite-dependency-check`, use pip's Python 3.12 binary-only resolver, and verify imports for these exact candidate pins:

```text
numpy==2.5.3
scipy==1.18.1
mpmath==1.4.1
threadpoolctl==3.6.0
scikit-learn==1.9.1
joblib==1.6.0
cloudpickle==3.1.2
narwhals==2.26.0
```

Save the resolver report under `/tmp` and compute the canonical C-order hash of the filtered `load_digits().data` design matrix without invoking the numerical runner.

- [ ] **Step 2: Write the dedicated lock**

Write the eight exact pins above, with the four CI pins unchanged and the scikit-learn closure explicit.

- [ ] **Step 3: Write failing fixture tests**

Create one `unittest` module that safely tolerates the contract module being absent so the run produces assertion failures rather than import errors. Cover every adversarial case named in the task, including literal section/case order, strict JSON, hashes, source/build/runtime drift, ABI layout, raw timing recomputation, numerical outcomes, registry mappings, legacy audit behavior, and the nonnumerical CI boundary.

- [ ] **Step 4: Run the RED suite**

Run:

```bash
python3 tests/test_numerical_suite_contract.py
```

Expected: assertion failures identifying absent contract behavior, with no syntax/import error and no shared-library load.

---

### Task 2: Pure protocol, schema, provenance, and package contract

**Files:**
- Create: `experiments/numerical_suite_contract.py`
- Test: `tests/test_numerical_suite_contract.py`

**Interfaces:**
- Produces: `PROTOCOL_ID`, `PROTOCOL_SIGNATURE`, `CANONICAL_SECTIONS`, `CANONICAL_CASE_IDS`, `ensure_abi_arrays`, `describe_input`, `timing_record`, `ratio_record`, `parse_sections`, `validate_result_document`, `validate_metadata_document`, `evaluate_eligibility`, `verify_build_manifest`, `resolve_and_load_router`, `audit_package`, and `publish_package_atomic`.

- [ ] **Step 1: Implement immutable protocol identity**

Encode all 82 ordered cases with literal generators and complete parameters/distributions, dimensions, input/routing seeds, numerical expectations, timing sources, warmups, repetitions, exact run/ratio identities, and scaling schedule. Compute the signature from stable strict canonical JSON and compare it with an independent literal test fixture.

- [ ] **Step 2: Implement strict input and timing records**

Validate native float64 C-contiguous `A`, `b`, and `x`; record shape, strides, row-major layout, seeds, and C-order hashes. Reject nonpositive/nonfinite timing arrays and recompute median, MAD, ratios, counts, and geomeans.

- [ ] **Step 3: Implement fail-closed result and metadata validation**

Collect stable reason codes for schema/order/case/input/timing/numerical/provenance failures. Require clean matching 40-character source states, exact build identities, linked/runtime BLAS hash agreement, one-thread BLAS pools, complete machine/software/lock identity, sanitized paths, and internally consistent eligibility.

- [ ] **Step 4: Implement exact library binding and atomic packages**

Resolve `ABS_LIB_DIR/libaffine_bundle_solver.so`, verify only its adjacent manifest and exact hashes, load that resolved file once, and configure router/sequential/LAPACK/counter symbols on the same handle. Serialize with `allow_nan=False`, validate before replacement, write all temporaries in one directory, replace result/metadata, and replace the relative-name checksum last.

- [ ] **Step 5: Run the contract tests**

Run `python3 tests/test_numerical_suite_contract.py`. Expected: pure contract tests pass; runner/registry/CI integration tests remain RED until later tasks.

---

### Task 3: Numerical runner integration

**Files:**
- Modify: `experiments/rerun_numerical_suite.py`
- Test: `tests/test_numerical_suite_contract.py`

**Interfaces:**
- Consumes: every public helper from Task 2.
- Produces: schema-v2 section records, `--reference-machine`, `--metadata-out`, `--checksum-out`, `--candidate`, and nonzero numerical failure exits.

- [ ] **Step 1: Make loading exact and lazy**

Set BLAS controls before NumPy/SciPy imports, resolve through the contract module, and control the router's observed OpenMP runtime through `threadpoolctl` without hard-coding or loading `libgomp` separately.

- [ ] **Step 2: Add ABI checks and evidence records without changing generators**

Call `ensure_abi_arrays` immediately before every router, sequential, and LAPACK API call. Replace discarded raw arrays with timing records; store every timed router invocation with stable case/run IDs, actual generator/routing seeds, repetition and requested/observed OpenMP identity, seconds, full diagnostics and per-run verdicts; retain input hashes, `router_berr`, and `null` when transition residuals are unavailable.

- [ ] **Step 3: Add numerical contracts and recomputable summaries**

Store explicit expected/actual/valid/reasons objects for every case, preserve timing ratios and directions, and return nonzero if any case fails. Timing-range observations never participate in validity.

- [ ] **Step 4: Add candidate preflight/postflight and atomic publication**

Reject malformed sections before loading. Allow partial diagnostics but never a candidate checksum. In candidate mode require exact sections, `--omp=4`, canonical filenames, reference machine, complete identities, and repeated source/router/manifest/runtime verification immediately before publication.

- [ ] **Step 5: Run the focused suite**

Run `python3 tests/test_numerical_suite_contract.py`. Expected: runner integration tests pass without executing a real generator or C API.

---

### Task 4: Claim registry and numerical audit

**Files:**
- Modify: `experiments/manuscript_performance_claims.json`
- Modify: `tests/check_paper_claims.py`
- Test: `tests/test_numerical_suite_contract.py`

**Interfaces:**
- Produces: `audit_numerical_suite_package(package_root, registry=None)` and CLI `--audit-numerical-suite ROOT`.

- [ ] **Step 1: Correct only the two specified claims**

Set `guard.rank1_cost` to historical `results/numerical_final_suite.json` `guard_timing` `m=10000,n=64,r=1`, protocol `3 warmups, 9 timed calls`, historical-unconfirmed, null mapping, blocker. Set `transition.rank_gate` to `512x256`, 20 seeds, six epsilon levels, historical suite source, null mapping, blocker; remove its PR #34 expected mapping.

- [ ] **Step 2: Add the separate numerical audit**

Return independent artifact-integrity, source/build/runtime, protocol, numerical-contract, supported-mapping, claim-coverage, and readiness verdicts. Legacy `results/numerical_final_suite.json` must return explicit missing schema/raw/provenance reasons rather than raise.

- [ ] **Step 3: Verify exact inventory stability**

Run `python3 tests/check_paper_claims.py --check-performance-inventory`. Expected: 20 claims, the same exact 18 blockers, and only `grouped.dgelsy` plus `scope.tall_directional` nonblocked.

---

### Task 5: Documentation and CI

**Files:**
- Create: `docs/numerical-suite-provenance.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_synthetic_bench_contract.py`
- Test: `tests/test_numerical_suite_contract.py`

**Interfaces:**
- CI step: `Numerical suite provenance contract`, gated to gcc/portable.

- [ ] **Step 1: Document schemas, protocol, privacy, dependency closure, and claim status**

Record the exact protocol signature, package files, ABI claim boundary, eligibility rules, Digits fingerprint, dependency versions, historical-unconfirmed status, and no-candidate limitation.

- [ ] **Step 2: Add the nonnumerical CI step**

Create a disposable venv, install `requirements-numerical-suite.txt`, compare all eight installed versions exactly, run the focused suite and claim inventory, and py-compile the four modified Python files. Do not invoke the runner, build, benchmarks, solver, production matrices, or artifact upload.

- [ ] **Step 3: Update the PR #34 audit**

Fetch the pinned artifact/source commits for Git-object verification, audit the tracked checkout, and compare strict readiness to literal equality with all 18 blocker IDs.

- [ ] **Step 4: Run focused compatibility tests**

Run:

```bash
python3 tests/test_numerical_suite_contract.py
python3 tests/test_synthetic_bench_contract.py
```

Expected: all tests pass without numerical execution.

---

### Task 6: Final verification, review, commits, and draft PR

**Files:**
- Create: `/tmp/numerical-suite-pdca-iteration3-final-report.md`

**Interfaces:**
- Produces: pushed branch, draft PR, CI conclusions, and final report.

- [ ] **Step 1: Run only the authorized verification commands**

Run the focused tests, synthetic contract tests, inventory, tracked PR #34 audit, exact py-compile command, `git diff --check`, the protected-path diff, and the historical SHA-256 check. Require 43 focused tests (or the final explicit count), 80 synthetic tests, PR #34 integrity/protocol/coverage PASS, and exactly 18 readiness blockers.

- [ ] **Step 2: Review the full diff**

Check every changed path against the restrictions and inspect schema/protocol/runner/audit/CI interactions. Because repository instructions prohibit unsolicited subagents, perform inline review unless the user explicitly requests delegation.

- [ ] **Step 3: Make logical commits**

Commit the contract/runner/tests/docs/dependency work and the registry/audit/CI work without rewriting main history.

- [ ] **Step 4: Push and open the requested draft PR**

Push `provenance/numerical-suite-contract`, create draft PR titled `experiments: add provenance contract for numerical suite`, include every required body statement, and never mark ready or merge.

- [ ] **Step 5: Observe CI for at most 15 minutes**

Watch once without manual reruns. Record exact workflow/job/step conclusions, including failures.

- [ ] **Step 6: Write the final report**

Write every requested identity, version, RED/GREEN result, schema/protocol detail, correction, guard, audit, CI conclusion, and no-numerical-run confirmation to `/tmp/numerical-suite-pdca-iteration3-final-report.md`, ending with the user-supplied sentence verbatim.
