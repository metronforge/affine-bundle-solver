# Focused qualification report

Verdict: **FOCUSED_NOT_QUALIFIED**.

The remotely verified preregistration was commit
`72bb497fd73536f66543693cac46f36e77041edd`, tree
`0b52e6c6f324a7854dd03049607727b3c993ec76`. The exact candidate branch was
`40fe4d015d988ce0ea9c6133c8715b424bba51d7`, tree
`d6ac56719d87a9200e6cab48f7a2ce8285eb0873`, and origin/main remained
`bb6c30d03191a92695b16d21581bfea6dce9942e`.

## Accounting and integrity

- Schedule: 288/288 retained in exact order; nine warmups and 279 eligible.
- Eligible observations: 31 per arm per slot; zero missing, duplicated,
  unregistered, excluded, rerun, or failed processes.
- Meaningful L/A and M/A fields: equal for every eligible trial.
- Candidate router executions: exactly one in every candidate process.
- Binary and input hashes, active compute budget, affinity, and DSO-specific
  thread policies: passed.
- Raw record SHA-256:
  `54f007d7be3ad81507b76d043540a632ab5837021170e6bf8428551f38d33bb9`.

## Registered performance results

All ratios are candidate/reference. Confidence intervals are the registered
100,000-resample paired-log bootstrap results.

| Slot | Pair/field | Median ratio | One-sided 95% upper | Two-sided 95% CI | Speedup of medians |
|---|---|---:|---:|---:|---:|
| V31-025 | L/A API | 0.94913 | 1.06227 | [0.91983, 1.07123] | 1.05360x |
| V31-025 | L/A wall | 0.79575 | 0.91156 | [0.77541, 0.91678] | 1.25668x |
| V31-025 | M/A API | 0.99121 | **1.03918** | [0.97108, 1.04258] | 1.00887x |
| V31-025 | M/A wall | 0.99142 | 1.03912 | [0.97119, 1.04253] | 1.00865x |
| V31-026 | L/A API | 0.23024 | 0.23123 | [0.21624, 0.23138] | 4.34323x |
| V31-026 | L/A wall | 0.21871 | 0.22012 | [0.20478, 0.22060] | 4.57217x |
| V31-026 | M/A API | 0.20643 | 0.21194 | [0.20440, 0.21237] | 4.84415x |
| V31-026 | M/A wall | 0.20653 | 0.21206 | [0.20451, 0.21247] | 4.84201x |
| V31-027 | L/A API | 0.51980 | 0.51621 | [0.46257, 0.51714] | 1.92381x |
| V31-027 | L/A wall | 0.50991 | 0.50705 | [0.45478, 0.50731] | 1.96111x |
| V31-027 | M/A API | 0.67627 | 0.68476 | [0.67018, 0.70048] | 1.47870x |
| V31-027 | M/A wall | 0.67628 | 0.68483 | [0.67026, 0.70053] | 1.47867x |

The direct L/A total-wall geometric-mean speedup is **2.24190x**, with
bootstrap 95% interval **[2.14019, 2.30449]**. The per-slot speedups are
1.25668x, 4.57217x, and 1.96111x.

## Resource, order, and stability findings

Candidate median RSS was within 110% of both controls in every slot. A/M RSS
ratios were 1.00250, 1.00027, and 0.99679 for V31-025/026/027; A/L ratios were
0.45455, 0.86769, and 0.99508. Affinity was `[1,3,6,8]` throughout and all
runtime fingerprints and thread pools matched the registered policy.

One eligible process, `focused-v3.9:V31-025:eligible:2:L`, recorded
`INVALID_THROTTLE` because the package-throttle counter incremented by one.
It remains in the raw data and was neither excluded nor rerun. All other
processes were thermally eligible.

Order effects and coefficients of variation are preserved in `audit.json`.
The largest absolute candidate-order log-ratio difference was 0.10656 for
V31-025 L/A total wall. V31-025 showed high M/A timing variability (API CVs
0.79731 for M and 0.81517 for A), which is consistent with—but does not excuse
or alter—the failed confidence-bound gate.

## Gate decision

The run failed two registered gates:

1. V31-025 M/A API one-sided 95% upper ratio was **1.03918**, above the
   required `<= 1.03`.
2. The protocol requires no thermal/throttling violation, but one L process
   recorded a package-throttle counter increment.

Every other registered focused gate passed, including the 1.5x geometric-mean
speedup, no A/M wall regression over 10%, V31-026/V31-027 API improvement,
meaningful-field equality, router counts, RSS, runtime policy, identity, and
record integrity. Because the complete focused qualification failed registered
gates, the canonical campaign, PR, CI wait, and merge were not started.
