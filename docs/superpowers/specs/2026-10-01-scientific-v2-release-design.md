# Scientific v2 Release Candidate Design

## Purpose

Prepare a reviewable scientific/publication release candidate from canonical
`main` commit `9c5336e1523415c8e93d3ce2632304ea738b6883`.  It documents the
current public API and its evidence boundaries, updates the next software
version through the repository's Release Please contract, and records the
artifacts and metadata needed for a later Zenodo version publication.  It does
not publish to Zenodo, ORCID, HAL, or GitHub Releases.

## Version decision

`v0.4.4` is the latest tag and the v1 scientific archive.  Release Please uses
the `simple` release type, Conventional Commits, and
`bump-minor-pre-major: true`.  The feature commits since that release require
software version `0.5.0`; the scientific publication label is v2.  These are
separate names: scientific v2 does not imply a `v2.0.0` software tag.

## Public model

The manuscript and release material shall describe operation selection by the
called function:

* `bsolve(A,b,...)` computes a candidate and operational evidence.
* `bsolve_ex(A,b,...,BSSolveOptionsV1,...)` performs that same solve with
  advanced numerical controls.
* `abs_check_candidate(A,b,x,...)` evaluates an already supplied candidate;
  its execution status is distinct from its quality verdict.
* `bs_certify_candidate(A,b,x,...)` evaluates nearby-system certificate
  evidence for an already supplied candidate.

Operational classification, candidate-quality evidence, nearby-system
evidence, and exact-source status stay distinct.  A finite nearby-system bound
does not prove the exact status of the stored binary64 input.

## Publication metadata

`CITATION.cff` and the README will identify `0.5.0` as the release candidate
and retain the existing Zenodo concept DOI as the version-history identifier.
They will not name a future version-specific DOI.  A deterministic
repository-managed metadata record will carry the later Zenodo, ORCID, and HAL
submission fields, with the version-specific DOI explicitly unset until Zenodo
publishes it.

## Evidence and artifacts

The release notes will cite only evidence present in the repository or rerun
for the candidate: the unchanged 36-system corpus, 180 legacy calls, split API
qualification, independent solution and quality oracles, MC/DC, ABI, sanitizer
and failure-path checks, and portable/build-provider evidence.  Existing
immutable performance evidence remains scoped to its recorded hardware and
toolchain; no new benchmark claim is made.

The candidate uses the existing release tools.  Their deterministic source and
research archives, SDK archives produced by the binary-qualification workflow,
`BUILD-INFO.json`, and ordered checksum manifest form the release inventory.
The manuscript is built by both the native launcher and the pinned container
path, then hashed.  Provenance and claim-registry validation run after all
source and metadata edits are final.

## Non-goals

This work makes no solver, public-API, numerical-threshold, fixture,
certificate-mathematics, performance, or CI change.  It does not create a
GitHub release or tag and does not modify external publication services.
