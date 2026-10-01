# Scientific v2 release candidate

Scientific v2 prepares the second version of the same published Affine Bundle
Solver research output. It is based on the canonical post-PR-58 `main` commit
`9c5336e1523415c8e93d3ce2632304ea738b6883` and proposes software version
`0.5.0`. The version follows the repository's pre-1.0 Release Please policy:
feature commits advance the minor version. It does not create a `v2.0.0`
software tag.

## Scientific changes since v1

The prior scientific release is the `v0.4.4` source archive, version DOI
`10.5281/zenodo.22753773`, within concept record
`10.5281/zenodo.22753772`. The verified substantive changes since that state
are:

* a versioned operational-policy API that keeps operational classification,
  nearby-system evidence, and exact-source reporting separate;
* strengthened certificate generation and checking, including independent
  verification profiles, exponent-framed scaling coverage, and strict
  floating-point environment checks;
* the corrected compact DGESDD fallback state: after a partial
  infinite-witness allocation failure, the old fallback could enter DGESDD
  with the cleared witness vector and write through null. The fallback is now
  gated on successful witness preparation, and deterministic failure controls
  plus sanitizer coverage protect the path;
* a frozen, sourced 36-system SLAE corpus with independent solution and
  quality oracles, legacy 180-call qualification, and CNF-derived MC/DC
  evidence whose coupled conditions are documented rather than claimed as
  independently covered;
* the public solve/check/certify architecture: simple `bsolve`, advanced
  `bsolve_ex` controls, caller-supplied candidate-quality checking, and
  deferred nearby-system certification; and
* qualified build-provider, portable/native, cross-platform, installed
  consumer, ABI, allocation-failure, ASan, and UBSan evidence.

The retained timing observations are unchanged and remain tied to the
immutable benchmark package, its named Intel Core Ultra 9 185H system, its
recorded software stack, one-thread protocol, and exact source provenance.
They are not new v2 performance measurements or portable speed claims.

## Public API and migration

Operation choice is represented by the function called:

```c
bsolve(A, b, m, n, policy, x, solve_result);
bsolve_ex(A, b, m, n, options, policy, x, solve_result);
abs_check_candidate(A, b, x, m, n, policy, candidate_result);
bs_certify_candidate(A, b, x, m, n, certificate_result);
```

`bsolve` uses the documented deterministic solve controls. `bsolve_ex` accepts
versioned `BSSolveOptionsV1` for advanced numerical routing controls. Candidate
checking and certification consume the supplied `x`; neither operation solves
again. A candidate verdict of `BS_CANDIDATE_NOT_ESTABLISHED` does not reject
the candidate. A finite certificate bound establishes a nearby exact system,
not the exact status of the stored binary64 `A,b`.

All released legacy router and certified APIs remain available. The historical
`full` parameter remains only on the legacy router ABI; it is absent from the
new solve functions and solve-options structure.

## Verification and artifacts

Candidate-specific commands and local counts are recorded in
`reports/scientific-v2/qualification.md`. The exact-head CI release-dry-run
artifact is the authoritative source for the final five-archive checksums and
`BUILD-INFO.json` identities, because a source archive cannot contain its own
non-self-referential digest. The release contract requires deterministic source
and research archives, three platform SDK archives, ordered SHA-256 checksums,
and `BUILD-INFO.json` identity binding before an immutable GitHub release can
be created.

## Publication metadata

`docs/publication/scientific-v2-metadata.yaml` is the handoff record for the
future Zenodo New Version, ORCID link, and HAL v2 submission. It intentionally
contains no version-specific DOI: Zenodo mints that identifier only when the
new version is published. The existing HAL v1 deposit remains untouched while
awaiting moderation.
