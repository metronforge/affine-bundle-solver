# PDCA 1 — prove the reuse boundary

## PLAN

Hypothesis: the compatible-tall fallback refactorizes one invariant normalized matrix. The falsifier was more than one matrix hash, a nonzero pivot seed, a changing rank/tolerance policy, or mutation of the source buffer. Safety controls were the exact frozen V31-027 input, the unchanged f66cd87 library, four frozen threads, and a native linker-wrapper test written before implementation.

## DO

The exact V31-027 call was traced at every `dgeqp3_` boundary. A native 8x4 compatible-tall fixture was added with an assertion requiring one workspace query and one executing call. Against the baseline it failed RED with ten calls.

## CHECK

The complete supported API made 262 `dgeqp3_` calls. The targeted 256x128/`lda=256` domain made 258: 129 queries and 129 executions. Every call had the identical FNV-1a byte hash `ae484947e5ef1103` and zero `jpvt` seed. The native fixture likewise found one input hash across five repeated factorizations.

`An` is normalized once and remains read-only. DGELSY copies it before solving. Each historical QR helper copied it again before LAPACK modified the copy. Rank, scan bounds, pivot seed, tail threshold, and good-support threshold do not change across iterations. The reusable domain is therefore exactly one `bs_generate_inconsistent_witness` invocation after normalization.

## ACT

Accept and proceed. Factorized matrix/Householder vectors and `tau` are consumed only by Q/Q^T applications; `jpvt` is retained metadata but has no later consumer; R is not read directly. Cycle 2 may replace the 129 identical factorizations with one invocation-local state.
