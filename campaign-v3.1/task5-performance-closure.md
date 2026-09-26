# Task-5 v3.1 performance closure

## Verdict

`PERFORMANCE_TARGET_NOT_MET`

Campaign: `task5-v3.1-performance-20260926`. Harness branch/source commit: `perf/task5-v3.1-final` / `79cb9bf`. The solver is `f66cd87a7b198497cc53d63b2bb04b85c3e64f53` (tree `4173cef889e0f1ec3ef60bc8aeadad26937a1711`), merged through one-parent squash PR #45 after clean independent review and successful exact-head CI.

The final required control comparison has geometric-mean speedup 0.940x, not the required 1.5x; V31-027 is 13.7% slower than control. Both candidate and control use the same library and combined API; candidate removes the only permitted preliminary `gelsd` solve and passes NULL `xt`. Changing anything else would not be a compliant legacy-equivalent comparison. No canonical 27-slot execution was started because the stated final-run gate was not met.

Correctness evidence: two byte-identical manifest/ledger generations; 24 small-case NULL-xt, legacy-certified, and router-snapshot differentials; one-router field on every retained trial; strict timing schema; 21 Python tests; and 25 native CTests on the merged library. All non-timing control/candidate fields agree using NaN/Infinity-aware tagged JSON.

V3 and historical artifacts were not modified. No N138, historical 177-case campaign, dirty historical library, merge commit, history rewrite, or unreviewed solver merge was used. The protected `stash@{0}` was not read or modified.
