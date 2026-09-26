# Task-5 v3.6 initial reconciliation

Recorded before candidate-tree edits on 2026-09-26.

## Authorized identities

- `origin/main`: `bb6c30d03191a92695b16d21581bfea6dce9942e`
- main tree: `e621eef836c2e6edd633c03d657cc582e0e04344`
- main parent: `1621d104a27eef3b12ec291384cac5f517da79f4`
- main parent count: `1`
- main title: `fix: align strict FP build and manuscript`
- Task-1 PR: `#47`, merged as the main SHA above
- reviewed Task-1 head: `521a3e5e1d078ff54d3440aaa72ae742bd415413`
- build-and-test run `36249296448`: `success`, exact head `521a3e5e1d078ff54d3440aaa72ae742bd415413`
- manuscript run `36249296446`: `success`, exact head `521a3e5e1d078ff54d3440aaa72ae742bd415413`
- corrected old candidate: `69728e36e1fd2532503c0fdf2735d02c3322ad94`
- corrected old candidate tree: `7bc54dc7c39352d2eeb52ac791ccd3967d9567a3`
- flag-only commit: `ad8b8bea07feefdbb81fd791459816c5f118c053`
- flag-only tree: `aba3faaa4dc58585b70da16a9d8464ac24daa00c`

Before worktree creation, no local/remote v3.6 candidate or harness ref, matching PR, `campaign-v3.6`, or `task5-v36-isolated-blas` path existed. The original checkout was clean on `fix/manuscript-implementation-drift` at `521a3e5e`; `git stash list` was empty, so no `stash@{0}` existed to inspect or alter. Remote tracking was current after `git fetch --prune origin`.

Isolated worktrees were then created without modifying the preserved checkout:

- `/home/viktor/task5-v36-row-axpy`, branch `perf/task5-v3.6-row-axpy-verifier`, exact base `bb6c30d`;
- `/home/viktor/task5-v36-isolated-blas`, branch `perf/task5-v3.6-isolated-blas-validation`, parent `5d99b26f017c77f972522ecacb48a610c7c19dae`.

The candidate base passed 30/30 system-BLAS CTests. The inherited harness passed 16/16 focused tests.

## Categorized source range

`ad8b8be..69728e` consists of four commits:

1. `7e6c82eb05f8035175d0f202ed18a493100a868e` — row-verifier algorithm only (`src/status_certificate.c`): two directed row passes replace per-entry materialized dot products.
2. `0b9f9cf5a8d223801e2f17c08013f4a0936c632c` — frozen row differential (`tests/test_unique_verifier_rows.c`), private observation hook, CMake registration, and sanitizer partition registration.
3. `27a9f53f410df05a32c93f3092b4ad8eaecd71e2` — fail-closed FP gate and its test; already integrated in accepted Task-1 main and excluded from the v3.6 port.
4. `69728e36e1fd2532503c0fdf2735d02c3322ad94` — sanitizer FakeStack prewarm for ENOMEM; already integrated in accepted Task-1 main and excluded from the v3.6 port.

`bb6c30d..69728e` also reverses or differs from accepted Task-1 manuscript, claim-registry, FP-gate, workflow, and semantics content because the old candidate was based on `1621d104`; none of those old-base differences is authorized for v3.6.

The Task-1 squash tree relative to the old flag-only tree contains the accepted fail-closed gate/test corrections, sanitizer prewarm, claim-registry and manuscript corrections, and related workflow integration. Those are base content, not candidate content. The only v3.6 candidate delta is the algorithm plus its private frozen-row differential and required build/CI registration.

## Remote-state safety

No push, PR, merge, tag, release, history rewrite, or main-branch write occurred during reconciliation. Any interrupted future push/PR/merge will be reconciled through remote state before retry.

