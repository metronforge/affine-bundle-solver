# Scientific v2 Release Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reviewable v2 scientific release-preparation PR for the
`0.5.0` software candidate without publishing it.

**Architecture:** Release Please remains the authority for software version
fields.  Manuscript, README, citation metadata, release notes, and a
machine-readable submission record share the same evidence boundaries and
refer to the existing qualification tools rather than duplicating their logic.

**Tech Stack:** CMake, C99, Python test/qualification tools, LaTeX, pinned
TeX container, Release Please, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-01-scientific-v2-release-design.md`

## Global Constraints

* Base all work on `9c5336e1523415c8e93d3ce2632304ea738b6883`.
* Use version `0.5.0`, derived from Release Please's pre-1.0 feature policy.
* Do not change solver APIs, thresholds, fixtures, numerical algorithms, or CI.
* Do not publish to Zenodo, ORCID, HAL, GitHub Releases, or create a release tag.
* Do not invent a version-specific DOI.

## Review Focus

* A future DOI must remain absent from all current candidate metadata.
* Version fields in the manifest, CMake, CFF, and external-consumer test must agree.
* The manuscript must describe candidate checking and certification as operations on supplied `x`.
* Release claims must keep nearby-system evidence distinct from exact-source status.
* Archive/checksum evidence must bind to the final release-preparation commit.

---

### Task 1: Version and publication metadata

**Files:**
- Modify: `.release-please-manifest.json`, `CMakeLists.txt`,
  `tests/consumer/CMakeLists.txt`, `CITATION.cff`, `README.md`
- Create: `docs/publication/scientific-v2-metadata.yaml`

**Interfaces:**
- Consumes: Release Please `simple` policy and the `release_assets.py identity`
  contract.
- Produces: consistent candidate version and submission metadata.

- [ ] Update the four generated-by-Release-Please version fields to `0.5.0`.
- [ ] Retain only the existing Zenodo concept DOI in candidate-facing metadata;
  add empty future-version DOI fields to the submission record.
- [ ] Run `python3 tools/release_assets.py identity . 0.5.0 <HEAD> <HEAD>` after
  committing the version change.
- [ ] Commit with `chore: prepare 0.5.0 release metadata`.

### Task 2: Scientific v2 narrative

**Files:**
- Modify: `paper.tex`, `README.md`
- Create: `docs/releases/scientific-v2.md`

**Interfaces:**
- Consumes: public headers, API documentation, frozen-corpus qualification,
  MC/DC documentation, DGESDD regression, and immutable benchmark evidence.
- Produces: factual manuscript and release notes for v2.

- [ ] Document the four public operations and their separate evidence roles.
- [ ] State candidate verdict and certificate limitations using current API names.
- [ ] Update software-availability wording for the v2 release candidate without
  claiming a new DOI.
- [ ] Build the manuscript and run its claim validators.
- [ ] Commit with `docs: prepare scientific v2 narrative`.

### Task 3: Final qualification and release evidence

**Files:**
- Create: `reports/scientific-v2/qualification.md`,
  `reports/scientific-v2/artifacts.sha256`

**Interfaces:**
- Consumes: final commit, build products, manuscript PDF, release tools, and
  existing qualification commands.
- Produces: candidate-specific commands, counts, hashes, and publication
  handoff inventory.

- [ ] Run the required normal, corpus, split API, MC/DC, ABI, sanitizer,
  installed-consumer, claim/provenance, manuscript, and dry-run release checks.
- [ ] Run the binary-qualification dry-run path and record its immutable
  archive/BUILD-INFO/checksum results.
- [ ] Hash immutable candidate artifacts and commit the report with
  `test: qualify scientific v2 release candidate`.

### Task 4: Review and PR handoff

**Files:**
- Modify: none unless verification exposes a release blocker.

**Interfaces:**
- Consumes: the committed candidate and exact PR-head CI.
- Produces: a reviewable PR and a final report with deferred public actions.

- [ ] Push `release/scientific-v2` and open a PR against `main`.
- [ ] Wait for exact-head PR CI and the verification gate.
- [ ] Record any intentionally conditional skips and leave the PR unmerged.
