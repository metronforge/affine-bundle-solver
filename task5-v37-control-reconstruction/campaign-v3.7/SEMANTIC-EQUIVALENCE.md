# L-v3.7 semantic-equivalence ledger

L-v3.7 is a reconstructed legacy-equivalent baseline, not the crashed v3.6
binary. It is rebuilt from exact commit/tree
`f66cd87a7b198497cc53d63b2bb04b85c3e64f53` /
`4173cef889e0f1ec3ef60bc8aeadad26937a1711` with the frozen compiler, system
BLAS, `-march=native`, and strict FP flags. Its only behavioral-environment
change is the root-cause-qualified OpenBLAS bootstrap described in
`ROOT-CAUSE.md`.

The original v3.6 binary and reconstructed L-v3.7 binary produced identical
meaningful fields on six safe cases spanning small wide (V31-001), small square
(V31-008), small tall (V31-015), scaled edge (V31-022), bounded-large wide
(V31-025), and bounded-large tall (V31-027). On targeted V31-026, L-v3.7, M,
and A all completed and agreed on every meaningful field. Ten additional fresh
isolated L-v3.7 V31-026 processes completed with full output and router count
one.

System-BLAS focused native checks passed 9/9, including the separate ENOMEM
fixture. SciPy-OpenBLAS focused native checks passed 8/8. The valid ASan/UBSan
partition passed 8/8; the address-space-limited ENOMEM fixture was classified
invalid under ASan and passed separately without instrumentation. Public-header
hashes and exported-symbol-set hashes are identical across L/M/A.

The raw validation ledger is
`evidence/cycle-03-semantic-stability.json`. These results defend numerical and
workload equivalence, but make no claim of byte identity with the original
v3.6 binary.
