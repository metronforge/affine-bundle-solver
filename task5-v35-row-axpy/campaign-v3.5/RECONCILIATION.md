# Initial reconciliation

- `origin/main` matched `1621d104a27eef3b12ec291384cac5f517da79f4`; it was not modified.
- Branch A and Branch B initially matched the requested heads and trees, and neither had a PR.
- The required fail-closed FP gate audit found two blocking false-success paths: unsupported architecture and absent target symbol. TDD corrections were committed and fast-forward pushed to the two existing branches, as expressly permitted for blocking defects.
- A valid ASan stream-ENOMEM run exposed test-fixture failure before the allocation test: FakeStack allocated lazily after `RLIMIT_AS`. A test-only prewarm correction was committed after RED/GREEN evidence. Official sanitizer runs fix BLAS/OpenMP threads to one for this allocation-limit fixture.
- Corrected A is `69728e36e1fd2532503c0fdf2735d02c3322ad94` / tree `7bc54dc7c39352d2eeb52ac791ccd3967d9567a3`.
- Corrected B is `b8d22717b1cb9a67fe6dd60cf0c8162cbed3d7c2` / tree `1c686f76a86632ce3b526cffe85857a047309414`.
- No performance timing was collected against superseded heads, so no timing dataset required invalidation.
- The v3.4 comparison commit is `5409f2a0ce35e6471b158b92e32eb3af91f68cf6` / tree `f93452c2c4f4735b57b6643f2640de835a973535`.
- All isolated solver worktrees were clean at protocol freeze. The original dirty solver workspace and all historical campaign evidence were untouched.
- No stash entry existed in the inspected authoritative repositories at reconciliation; no stash was created, modified, or dropped.
- No PR, merge, force-push, tag, release, or publication action occurred.
