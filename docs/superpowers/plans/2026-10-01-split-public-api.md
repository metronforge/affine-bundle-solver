# Split Public API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish distinct solve, caller-supplied candidate-check, and candidate-based nearby-certification operations while preserving all legacy contracts.

**Architecture:** Add operation-specific public headers and thin strict/public implementations around existing router, least-squares, generator, and verifier primitives. Legacy combined entry points remain unchanged; new deferred paths take `x` explicitly and are instrumented in tests to prove they cannot route or reconstruct it.

**Tech Stack:** C11, CMake, BLAS/LAPACK, Python/NumPy regression harness, CTest, ASan/UBSan.

**Spec:** `docs/superpowers/specs/2026-10-01-split-public-api-design.md`

## Global Constraints

- Preserve all existing exported symbols and public layouts.
- Preserve default thresholds exactly: `1e-13`, `1e-9`, `2e-10`, `1e-14`.
- Preserve all 36 frozen fixtures and their hashes.
- Candidate checking and candidate certification must not invoke router selection or reconstruct `x`.
- Candidate quality, nearby-system evidence, operational classification, and exact-source status remain distinct.
- All production strict arithmetic uses the repository strict floating-point flags.

## Review Focus

- Non-finite candidate: reject execution and leave fail-closed evidence.
- Valid future-sized output/policy: write only V1 prefix and preserve trailing bytes.
- Rank-deficient/wide system: assess semantics without freezing a non-canonical vector.
- Allocation or LAPACK failure: propagate execution failure without partial evidence.
- Extreme finite scaling: return rigorous finite bounds or `BOUND_UNAVAILABLE`, never a false quality success.

---

### Task 1: Candidate-check contract and strict kernel

**Files:**
- Create: `include/affine_bundle/candidate_check.h`
- Create: `src/candidate_check.c`
- Create: `tests/test_candidate_check.c`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: `BSOperationalPolicyV1` and its validator.
- Produces: `BSCandidateVerdict`, `BSCandidateCheckResultV1`, `bs_init_candidate_check_result`, `abs_check_candidate`.

- [ ] Write native tests for exact, perturbed, wrong, zero, non-finite, malformed-size, future-size, policy, allocation, and repeated-call behavior.
- [ ] Run the focused target and confirm missing-symbol/test failures.
- [ ] Implement strict directed-rounding residual and mixed-2-norm bounds with fail-closed initialization.
- [ ] Run focused tests and strict contraction inspection.
- [ ] Commit `feat(api): add caller-supplied candidate checking`.

### Task 2: Standalone numerical solve

**Files:**
- Create: `include/affine_bundle/solve.h`
- Modify: `src/certified_api.c`
- Create: `tests/test_solve_api.c`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: `bsolve_router_policy_api`, existing LAPACK least-squares primitive, `BSOperationalResultV1`.
- Produces: `BSSolveOptionsV1`, `bs_default_solve_options`, `BSSolveResultV1`, `bs_init_solve_result`, `bsolve`, and `bsolve_ex`.

- [ ] Write tests for simple/default equivalence, option validation/versioning, success, operational equivalence, finite `x`, malformed sizes, invalid inputs/policies, allocation/LAPACK failure, and suffix preservation.
- [ ] Run focused tests and confirm missing-symbol/test failures.
- [ ] Extract the least-squares helper into a reusable private primitive and implement `bsolve` without certification.
- [ ] Run focused and legacy operational tests.
- [ ] Commit `feat(api): add standalone numerical solve contract`.

### Task 3: Candidate-based nearby certification

**Files:**
- Modify: `include/affine_bundle/certified_api.h`
- Modify: `src/certified_api.c`
- Create: `tests/test_candidate_certification.c`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: caller `x`, existing witness construction excluding candidate reconstruction, and existing strict verifiers.
- Produces: `BSCertificateResultV1`, `bs_init_certificate_result`, `bs_certify_candidate`.

- [ ] Write tests comparing overlapping nearby profile fields, invalid/future structs, failures, repeatability, and exact-source absence.
- [ ] Add router and candidate-reconstruction hooks; demonstrate zero calls in deferred checking/certification.
- [ ] Refactor unique/infinite witness builders to accept caller `x`, retaining legacy wrappers.
- [ ] Implement candidate certification and run focused plus legacy certified tests.
- [ ] Commit `refactor(cert): separate candidate certification from solve`.

### Task 4: Frozen-corpus split-path qualification and oracle

**Files:**
- Modify: `tests/api_regression_binding.py`
- Create: `tests/split_api_qualification.py`
- Create: `tests/test_split_api_qualification.py`
- Create: `docs/api-semantic-regression.md`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: all three new operations and frozen cases.
- Produces: actual per-path counts and semantic comparison report.

- [ ] Extend ctypes bindings without changing legacy consumers.
- [ ] Add independent residual/backward-error and certificate-inequality checks.
- [ ] Compare unique solutions numerically and non-unique cases semantically.
- [ ] Exercise solver, small/large perturbations, zero, known exact, and clearly wrong candidates where applicable.
- [ ] Compare legacy combined and new composed certificate fields only where semantics overlap.
- [ ] Run both old qualifications and the new qualification; record actual counts.
- [ ] Commit `test(api): qualify split APIs on frozen corpus`.

### Task 5: CNF-derived MC/DC and ABI/error contracts

**Files:**
- Create: `tests/test_split_api_decisions.py`
- Create: `tests/test_split_api_abi.c`
- Create: `docs/split-api-mcdc.md`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: public validation and verdict decisions.
- Produces: explicit Boolean assignments, concrete inputs, independent-effect pairs, and uncovered-condition disclosures.

- [ ] Derive and document CNF pairs for validation, bound availability, and quality threshold decisions.
- [ ] Implement concrete native/Python cases for each reachable pair.
- [ ] Add symbol, installed-header, old-size, new-size, suffix, undersize, and default compatibility checks.
- [ ] Run focused tests and coverage report without overstating coupled guards.
- [ ] Commit `test(api): add MC/DC and ABI coverage for split operations`.

### Task 6: DGESDD hypothesis and sanitizer qualification

**Files:**
- Modify only if reproduced: `src/certified_api.c`
- Create or modify only if needed: allocation/fallback tests
- Create: `docs/dgesdd-fallback-investigation.md`

**Interfaces:**
- Consumes: test-only allocation/LAPACK injection seams.
- Produces: deterministic evidence for or against the reported lifetime defect.

- [ ] Trace allocation ownership and reproduce every DGESDD setup failure point.
- [ ] If unsafe lifetime is observed, write the failing test first, fix minimally, and commit `fix(cert): harden DGESDD allocation failure path`.
- [ ] If not reproduced, document the exact lifetime proof and make no speculative production change.
- [ ] Run focused paths and the full suite under ASan/UBSan, including repeats and partial initialization.
- [ ] Commit investigation/tests as `test(cert): cover DGESDD fallback failures` or documentation as appropriate.

### Task 7: Public workflow documentation and final verification

**Files:**
- Modify: `docs/api.md`
- Modify: `README.md`
- Modify: consumer examples/tests as needed

**Interfaces:**
- Consumes: finalized symbols.
- Produces: documented solve -> check -> optional certify workflow.

- [ ] Document contracts, non-claims, error semantics, and a compilable three-phase example.
- [ ] Run normal build, CTest, Python tests, frozen legacy/new qualifications, ABI checks, ASan, UBSan, and repository-required build/paper checks.
- [ ] Verify fixture hashes and exported symbols against the base.
- [ ] Commit `docs(api): document solve check certify workflow`.
- [ ] Prepare feature branch, Conventional Commit history, PR, exact head SHA, and exact-SHA CI evidence.
