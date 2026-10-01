# Scientific v2 release-candidate qualification

## Candidate identity

- Scientific publication version: v2
- Proposed software version: 0.5.0
- Canonical base: `9c5336e1523415c8e93d3ce2632304ea738b6883`
- Release candidate source identity: the exact pull-request head recorded by
  the CI release dry run.

The repository's release archive contains this report. The final archive
checksums therefore cannot be committed inside that same archive without a
self-referential digest. The exact-head release-dry-run artifact supplies the
authoritative five-archive `SHA256SUMS.txt`, `BUILD-INFO.json` files, and
qualification evidence; it is recorded in the review handoff.

## Locally reproduced qualification

The following commands were run against this release-preparation branch before
the exact-head CI qualification.

| Layer | Result |
| --- | --- |
| CMake system-BLAS build and CTest | 57/57 passed |
| Canonical `build.sh` strict-FP build | passed: directed rounding, MXCSR, and no-FMA gates |
| Frozen API corpus unit suite | 32/32 passed |
| Legacy frozen-corpus runner | 36/36 systems passed |
| Legacy qualification | 36 unique systems, 180 attempted/completed invocations, 0 skipped |
| Split API qualification | 36 solve, 36 default-equivalence, 36 solve/check, 36 certification, 36 combined/composed, 144 caller candidates, 180 independent quality-oracle, and 36 independent solution-oracle observations |
| Split API CNF-derived MC/DC decision tests | 4/4 passed |
| Property evidence | equivalence: 8,335 checks with 155 documented known-representation diagnostics and no hard failures; certificate equivariance: 2,271 checks and zero failures |
| Installed external consumer | C, C++, and pkg-config consumer passed after relocation with the build tree unavailable |
| Manuscript native build | passed, no unresolved reference/citation or overfull-box diagnostics; PDF SHA-256 `de55aa13e20b456159911ec9347e24cd030162897ce59129afd8d87ccd5a6af5` |
| Manuscript claim reproduction | 8/8 claims reproduced |

The local ASan/UBSan build completed. This sandbox cannot run full
LeakSanitizer because it is ptrace-confined and its address-space mapping is
restricted; the exact-head CI sanitizer partitions are consequently the
authoritative sanitizer result.

## Exact-head CI obligations

The review PR must have successful exact-head evidence for:

- normal build/test and verification gate;
- pinned manuscript container build;
- portable/native, cross-platform, and BLAS-independence agreement;
- ASan, UBSan, and allocation/failure-path partitions;
- API/ABI, installed-consumer, frozen-corpus, oracle, and MC/DC checks; and
- workflow-dispatched binary release qualification with the complete five
  archive inventory, checksum chain, BUILD-INFO identities, exact-byte
  consumer evidence, and no-publication dry run.

`tests/fixtures/api-regression` has no changes relative to the canonical base.
