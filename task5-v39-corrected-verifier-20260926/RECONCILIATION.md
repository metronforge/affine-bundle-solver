# Task-5 v3.9 initial reconciliation

Recorded: `2026-09-26T21:03:42+03:00`.

## Immutable identities

- `origin/main`: `bb6c30d03191a92695b16d21581bfea6dce9942e`
- main parent/tree/title: `1621d104a27eef3b12ec291384cac5f517da79f4` / `e621eef836c2e6edd633c03d657cc582e0e04344` / `fix: align strict FP build and manuscript`
- L source/parent/tree: `f66cd87a7b198497cc53d63b2bb04b85c3e64f53` / `0ace47c78b7ed2e7b067a77254326bd17f2e2623` / `4173cef889e0f1ec3ef60bc8aeadad26937a1711`
- optimization/parent/tree: `dd30ef900ff7f48d4fe97e79aae94b7e64c48741` / `bb6c30d03191a92695b16d21581bfea6dce9942e` / `a89ce2def1fc1b2ef4644cc4d17f13c533b099b7`
- corrected candidate/parent/tree/title: `40fe4d015d988ce0ea9c6133c8715b424bba51d7` / `dd30ef900ff7f48d4fe97e79aae94b7e64c48741` / `d6ac56719d87a9200e6cab48f7a2ce8285eb0873` / `fix: reject non-finite verifier bounds`

`bb6c30d` is an ancestor of `40fe4d0`; the complete candidate ancestry is the
two commits `dd30ef9`, then `40fe4d0`. The cumulative binary diff SHA-256 is
`8d8972e96a9d652f0a81ebf9812c8128284c27c2b4d07498f1c97d789ec09bbf`;
the correction-only binary diff SHA-256 is
`c497264c9981a1d1289f302ade6844cc034355abeff6ba42d809f7fc633d80cd`.

The cumulative diff changes exactly `.github/workflows/ci.yml`,
`CMakeLists.txt`, `src/status_certificate.c`, and
`tests/test_unique_verifier_rows.c`. It consists of the strict row-wide
verifier implementation, strict-FP/test registration, focused row tests, and
the non-finite-bound correction. No public header, certificate structure,
router source, or unrelated solver source changes. The base and candidate
`include/` tree are both `846f0605aa5413010a39ab49b8f6f87d5538099d`.

## Local and remote state

- Fresh fetch verified `origin/main` at the required base before worktree creation.
- Integration worktree: `/home/viktor/task5-v39-corrected-verifier`, branch `perf/task5-v3.9-corrected-row-verifier`, exact clean head `40fe4d0`.
- Evidence worktree: `/home/viktor/task5-v39-corrected-verifier-evidence`, branch `evidence/task5-v3.9-corrected-verifier-20260926`, based on verified v3.7 evidence head `758de2d`.
- Every pre-existing solver worktree was clean at reconciliation. Historical v3.6, v3.7, and v3.8 worktrees remain untouched.
- No `refs/stash` existed at reconciliation; no stash operation was performed.
- The new integration branch/path and evidence branch/path did not exist before this task.
- GitHub did not contain object `40fe4d0`; the all-PR query returned no PR whose head or merge commit was `40fe4d0`. No prior merge exists.

## Retained evidence

- v3.6 `SHA256SUMS`: `81/81` entries verified.
- v3.7 `SHA256SUMS`: `57/57` entries verified, including the three retained historical libraries and the candidate safety bundle.
- `/home/viktor/task5-v37-candidate-dd30ef9.bundle` SHA-256: `40b9193f5d048d3bcc80c0efb0409a11ad49ebc2b72d0a3bb53acd66c09bf2e0`.
- `/tmp` contains extracted committed/remote v3.7 evidence trees consistent with the retained worktree.
- `/projects/research-assistant/task5-v31-final` contains the authoritative original V31 27-slot manifest and canonical gate record.

No historical campaign file, timing record, binary, branch, bundle, or worktree
was modified during reconciliation.
