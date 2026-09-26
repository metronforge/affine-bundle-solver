# Independent adversarial review

## Branch A algorithm

`unique_row_pass` reconstructs a selected packed-LU row twice, once under downward rounding and once under upward rounding. For each accumulator `j`, it visits the nonzero products in increasing `k`, matching the frozen implementation's term order after removing structural-zero products. Removing an exact structural zero cannot change a nonzero partial sum in either directed mode. An all-zero accumulation can differ only in zero sign; the consumer applies `fabs` before forming a radius. The frozen row-level differential confirms that boundary directly.

The helper is `noinline`, the strict compilation adds `-ffp-contract=off`, and the gate disassembles the expected source-specific symbols. The two pass calls set `acc=evec`; `e=elo` and `e=ehi` are distinct owned arrays. The `restrict` promises therefore match actual calls, including the named alias patterns, and no buffer overlaps. Neither pass mutates packed LU, source rows, scales, or permutation data.

The allocation count, size class, ordering, cleanup, and failure behavior remain equivalent: after `pos`, M owned `ucol`, `lrow`, and `evec`; A owns `ehi`, `elo`, and `evec`, all `n` doubles. There is no global cache, static mutable production state, or changed reentrancy model. Validated ENOMEM and repeated/reentrant tests pass.

No Critical or Important defect remains. The original branch did contain a blocking false-PASS in its build gate and an invalid sanitizer allocation-limit fixture. Both were corrected test-first before timing, producing the new immutable A identity.

## FP contraction gate

The corrected gate fails closed when objdump is missing, disassembly is empty, the expected symbol is absent, no relevant instruction is inspected, architecture is unsupported, or an x86/aarch64 fused-operation mnemonic is present. The normal build prints `fp-contraction check: PASSED`. A deliberately contracted build fails. Source-to-symbol mapping ensures the intended object and relevant routine are inspected; a whole-object scan still catches fused instructions elsewhere in each strict object.

## Comparison with v3.4 candidate

Both Branch A and `5409f2a0ce35e6471b158b92e32eb3af91f68cf6` remove work from unique-witness verification, but they are not the same optimization. v3.4 introduces `packed_lu_interval` per output entry: it avoids dense temporary row/column materialization and removes two allocations, but still changes rounding mode inside every column computation. Branch A retains three work arrays but performs two row-wide directed passes, changes mode only twice per selected row, and traverses packed rows contiguously. Branch A has the stronger bit-level argument because its term-order proof is backed by the frozen 1.5-million-entry differential and a fail-closed no-contraction gate. Results from the branches were not combined.

## Effect separation

The five-pair diagnostic is deliberately non-official. Ratio-of-medians speedups were:

| Slot | M→F API / E2E | F→A API / E2E | M→A API / E2E |
|---|---:|---:|---:|
| V31-025 | 1.035 / 1.002 | 0.992 / 1.013 | 1.026 / 1.015 |
| V31-026 | 1.038 / 1.193 | 2.248 / 1.597 | 2.333 / 1.906 |
| V31-027 | 1.014 / 1.001 | 1.148 / 1.107 | 1.164 / 1.109 |

The flag-only effect is near 1× in API time. The algorithmic effect is large on V31-026, positive on V31-027, and immaterial/noisy on V31-025. With only five observations and wide intervals, these data support attribution, not qualification.
