# Task-5 v3.9 corrected-verifier qualification specification

The binding specification is the user-supplied “Rebuild references, qualify the
corrected verifier, and integrate it” brief dated 2026-09-26.

The immutable base is `bb6c30d03191a92695b16d21581bfea6dce9942e`. The
immutable cumulative candidate is `40fe4d015d988ce0ea9c6133c8715b424bba51d7`,
parent `dd30ef900ff7f48d4fe97e79aae94b7e64c48741`, tree
`d6ac56719d87a9200e6cab48f7a2ce8285eb0873`.

All L/M/A binaries, input bundles, identities, manifests, schedules, timing
records, analyses, and checksum inventories must be regenerated. Historical
v3.7 artifacts may supply only protocol logic, frozen input recipes,
statistical methods, and the reconstructed-control recipe.

The focused campaign is V31-025/026/027 with one warmup and 31 eligible L/M/A
observations per slot, a new deterministic balanced schedule, four active
threads, paired log-ratio analysis, 100,000 bootstrap resamples, and the exact
gates in the user brief.

The authoritative canonical contract is the original V31 27-slot mathematical
manifest under `/projects/research-assistant/task5-v31-final`, combined with the
later frozen v3.6 execution contract: one warmup plus five eligible balanced
L/A observations per slot, seed `2026093606`, 30-second worker timeout,
30-minute campaign envelope, direct geometric mean at least 1.5x, no slot more
than 10% slower, meaningful-field equality, one candidate router execution,
candidate RSS within 10%, valid thermal/runtime/affinity evidence, complete
accounting, and checksum integrity.

The integration branch must remain exactly at the two-commit candidate head.
Preregistration and measurements live on a separate evidence descendant, as in
the validated v3.6 architecture. No candidate modification, history rewrite,
selective rerun, exclusion, release, or stash operation is allowed. No cleanup
is allowed before integration. After a verified squash merge, remove only the
new v3.9 worktrees and temporary build directories created by this task; keep
the pushed evidence branch/history and every pre-existing v3.6/v3.7/v3.8
workspace and artifact.
