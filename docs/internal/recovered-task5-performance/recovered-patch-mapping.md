# Recovered Task-5 performance patch mapping

Mapping target: current main `369c7d1c298ac0fa9ea21ac469c97ced5e53af86`,
tree `632c6855f8baa4bf66e4f892c822df6c450d50b3`.

| Recovered hunk | Classification | Current-main adaptation |
| --- | --- | --- |
| OpenMP include and `ABS_CERT_UNIQUE_THREADS` | REQUIRES_MANUAL_ADAPTATION | Current verifier has `unique_row_pass`, which replaces the historical materialized L/U-dot path. The adaptation parallelizes source rows around that kernel. |
| Per-worker directed passes and scratch | CLEANLY_APPLICABLE | Each worker owns `ehi`, `elo`, and `evec`, captures/restores `fenv_t`, and executes the existing down/up passes unchanged. |
| Historical OpenMP `reduction(max:best)` | CONFLICTS_WITH_CURRENT_SEMANTICS | Replaced by per-source-row `row_eta[]` followed by a serial, ascending-source-row maximum. |
| Historical fenv restoration by rounding-mode integer | OBSOLETE_DUE_TO_LATER_FIX | Current adaptation uses full `fenv_t` capture/restore, preserving more than only the rounding direction. |
| Historical omitted non-finite row checks | OBSOLETE_DUE_TO_LATER_FIX | Current fail-closed `elo/ehi/evec`, residual, perturbation, and source checks are retained. |
| QRCP right-null candidate | REQUIRES_MANUAL_ADAPTATION | Retained as an untrusted candidate helper in `certified_api.c`; it does not classify rank or alter public status semantics. |
| DGESDD full right-vector candidate | REQUIRES_MANUAL_ADAPTATION | Uses `LDVT` indexing, avoiding the historical wide-core stride bug. The combined path uses it only after QRCP unavailability/rejection. |
| Historical standalone generator replacement | CONFLICTS_WITH_CURRENT_SEMANTICS | Rejected: public `bs_generate_infinite_witness()` retains established DGESVD behavior. Only the combined audit uses QRCP then DGESDD. |
| Historical independent source solve | CURRENT_MAIN_ALREADY_CONTAINS_EQUIVALENT | The combined path passes UNIQUE's existing least-squares witness to the INFINITE preparation path; if UNIQUE generation fails, exactly one INFINITE source solve is performed. |
| Router DGESDD work | CURRENT_MAIN_ALREADY_CONTAINS_EQUIVALENT | Current compact router DGESDD state is untouched. |
| Inconsistent QRCP work | CURRENT_MAIN_ALREADY_CONTAINS_EQUIVALENT | Current reusable normalized QRCP state is untouched. |
| Combined diagnostics and source arbitration | CURRENT_MAIN_ALREADY_CONTAINS_EQUIVALENT | The public one-router `bsolve_certified_diag_api()` and router source are untouched. |

`ABS_CERT_UNIQUE_THREADS` defaults to `1`. A positive decimal integer is
bounded by the source-row count. Empty, malformed, zero, negative, and
overflowing values use the deterministic one-worker default.
