# Recovered Task-5 certificate-performance source

This directory preserves engineering evidence recovered on 2026-09-28 before
adapting it to current solver main.  It is archival evidence only; it is not a
patch series intended to apply to the current tree.

## Source identity

- Session log: `/home/viktor/.codex/sessions/2026/09/20/rollout-2026-09-20T18-44-27-01a0bf7d-7d9a-70e0-9a9d-28cf6e5bf4b8.jsonl`
- SHA-256 of session log: `de398e877cb7a711c0c701a9ad4e4b97b37e3079e1d41bd9510bb06393569908`
- Relevant recovered tool-call records: 577--581 (parallel UNIQUE) and
  641--644 (QRCP/DGESDD INFINITE candidate and combined build).
- Historical target: `/tmp/abs-v044-task4-corrective`, with candidate copies
  `/tmp/abs-v044-cert-opt-A`, `/tmp/abs-v044-cert-opt-C`, and
  `/tmp/abs-v044-task5-cert-perf`.  Those temporary source directories are
  no longer present and were not used as a source tree for this recovery.
- SHA-256 of recovered-parallel-unique.patch:
  `3f1b6cb52a3c7baa1eee58af68f047c8914215bbbe7816ff0dde046264e7115e`
- SHA-256 of recovered-infinite-qrcp-dgesdd.patch:
  `1c93e8a65407205153c44eee2eb11d8b207c133878c7b88f4cc09c60f075d094`

## Historical validation statements recorded in that session

- The parallel UNIQUE checker had bitwise-identical `eta_unique` and verifier
  return codes at 1, 2, 4, 8, and 16 workers; a thread-local fenv/MXCSR probe
  passed.
- N020 UNIQUE verification was reported as approximately 1494.7 seconds on
  the historical baseline and 91.7 seconds at 16 workers.
- The QRCP candidate was verified before acceptance; rejected/unavailable
  candidates fell back to DGESDD and the unchanged verifier.
- Historical full audit measurements were N020 1548.57 -> 173.75 seconds and
  N016 178.30 -> 20.92 seconds.

## Recovery rule

The historical patches are authoritative evidence of the intended algorithms,
not authority to bypass current-main hardening.  Current-main non-finite
fail-closed behavior, `unique_row_pass`, strict-FP flags, compact-DGESDD router
state, source least-squares reuse, inconsistent QRCP reuse, one-call certified
diagnostics, and source arbitration take precedence.
