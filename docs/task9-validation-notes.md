# Task 9 review corrections

Independent pre-merge review found that the new custom-quality row reduction
could skip a NaN row error and report zero. The two row orders of
`A=[[1e200,1e200],[1e-200,0]], b=[0,1]` now refuse classification when custom
quality arithmetic is nonfinite. The regression failed before the fix and passed
after explicit bit-safe checks. This fix is confined to custom quality; it does
not change the required DEFAULT behavior or certificate verification.

The concurrency fixture additionally exercises different operational statuses
under two independent policies, not merely different echoed values.

The historical manuscript at baseline `223bd2b87ca74183df834b2abe136cfc9d5de665`
stated 154 known representation-sensitive PBT observations. Its own CI run
`36473835522` already reported 155 in GCC portable/native and Clang portable,
failing the manuscript check. Independent baseline/candidate runs both reproduce
8,335 checks, zero hard failures, and 155 known representation observations:
24 affine_translation_2^30 and 131 inconsistent_affine_translation_sweep.
The current manuscript and its exact equality check are therefore corrected to
155 together. The old 154 statement remains in Git history; no historical result
artifact, benchmark ratio, or solver threshold has been rewritten. This is a
stale documentation correction, not evidence of a Task-9 behavioral change.
