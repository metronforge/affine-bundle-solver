# PDCA 04 — native duplicate certified least-squares work

## PLAN

Hypothesis: the certified combined path repeats the source least-squares solve when producing UNIQUE and INFINITE profiles. Frozen input: the exact baseline `0ace47c`, bounded design unchanged. Falsifier: an exact-field differential or a regression in normal/sanitizer/ABI consumer checks. Acceptance: remove one source solve without changing certificates.

## DO

Test-first PR #45 added a private call counter that failed at three source solves and passed at two. The implementation reuses the successful UNIQUE witness only to seed the INFINITE SVD construction; it keeps independent verification and the failure fallback. Exact head: `01dd3ca`; squash result: `f66cd87`.

## CHECK

Independent review was CLEAN. CI run 36197900181 passed gcc, clang, ASan/UBSan, install-consumer, portable/native agreement, and verification gate. Local release build ran 25/25 CTests. The exact merged commit has one parent `0ace47c` and tree `4173cef`.

## ACT

Accepted and squash-merged as `perf: reuse certified source least-squares witness (#45)`. Rebuilt V3.1 only against `f66cd87`.
