# Task 4.7b campaign-freeze validation

The recovered performance work was adapted—not copied—to current main.  The
parallel change retains the current `unique_row_pass`, non-finite fail-closed
checks, strict floating-point flags, and deterministic source-order maximum.
`ABS_CERT_UNIQUE_THREADS` defaults to one and safely falls back to one for an
invalid setting.

The INFINITE change is internal to the combined certified path: QRCP offers an
untrusted null-vector candidate, the existing strict verifier decides whether
to accept it, and DGESDD generates a fallback candidate only if necessary.
The public standalone DGESVD generator and all public headers remain unchanged.

All fast regressions (37 CTest tests), Task-1, N049, the 8,335 equivalence/PBT
checks, 2,271 certificate checks, strict-FP probes, and the ASan/UBSan focused
suite passed.  The 36-case differential found no status, rank, mask, code, or
router-diagnostic change.  Eta changes are expected witness-only numerical
variation and remain verifier-approved.

N020 combined time fell from the preserved 1,405.55 seconds to 141.09 seconds
at the campaign thread configuration.  Its isolated strict UNIQUE verifier is
bitwise deterministic across 1, 2, 4, 8, and 16 workers, falling from 45.93 to
7.06 seconds.  The Task-5 runner was not resumed; all 13 pre-freeze checkpoints
were checksum-validated after stopping two unexpected runner processes.
