# Immutable focused v3.9 qualification protocol

This protocol binds fresh L/M/A builds to corrected candidate
`40fe4d015d988ce0ea9c6133c8715b424bba51d7` and tree
`d6ac56719d87a9200e6cab48f7a2ce8285eb0873`. No v3.7 observations or binary
hashes are reused. The validated v3.7 input recipe, paired statistics, control
reconstruction, and OpenBLAS bootstrap policy are reused.

The committed schedule contains exactly one excluded warmup plus 31 eligible
observations for each L/M/A arm in V31-025, V31-026, and V31-027: 288 processes,
279 eligible. Seed `2026093904` fixes balanced order. Every subprocess is pinned
to CPUs `1,3,6,8`. L starts both OpenBLAS DSOs at four, retains SciPy OpenBLAS
at four, and lowers inactive system OpenBLAS to one. M/A use system OpenBLAS at
four. Other pools remain at one. Records are atomically persisted after every
process. No exclusion or rerun is permitted.

Paired log ratios use median effects and 100,000 bootstrap resamples with seed
`2026093999`. The complete run passes only if all observations complete; all
meaningful L/A and M/A fields agree; A router count is one; V31-025 M/A API
one-sided 95% upper ratio is at most 1.03; three-slot L/A total-wall geometric
mean speedup is at least 1.5x; no A/M total-wall median ratio exceeds 1.10; A
median RSS is at most 110% of each control; all runtime, thermal, affinity,
identity, and checksum gates pass; and A API medians improve over M for
V31-026 and V31-027.

Any missing or invalid scheduled process ends `FOCUSED_INCOMPLETE`. A complete
run failing a registered gate ends `FOCUSED_NOT_QUALIFIED`.
