# v3.7 one-shot qualification summary

All 288 scheduled processes completed: nine retained/excluded warmups and 279
eligible records (31 per arm per slot). No process was rerun and no v3.6 timing
was imported. All registered gates passed.

## Direct legacy/candidate results

Ratios are A/L; speedups are L/A. Confidence intervals are paired-log
two-sided 95% intervals for the ratio.

| Slot | API A/L | API 95% CI | API speedup | E2E A/L | E2E 95% CI | E2E speedup |
|---|---:|---:|---:|---:|---:|---:|
| V31-025 | 0.988744 | 0.903874–1.038596 | 1.011384x | 0.798953 | 0.767463–0.893583 | 1.251639x |
| V31-026 | 0.228215 | 0.223189–0.233712 | 4.381842x | 0.215781 | 0.208193–0.223216 | 4.634333x |
| V31-027 | 0.505920 | 0.460909–0.508364 | 1.976595x | 0.495622 | 0.450453–0.499200 | 2.017665x |

Direct three-slot L/A total-wall geometric mean: **2.270414x**; registered
aggregate bootstrap 95% interval: **2.142973–2.325095x**. The 1.5x point gate
passes.

## Main/candidate results

Ratios are A/M; speedups are M/A.

| Slot | API A/M | API 95% CI | API upper 95% | API speedup | E2E A/M | E2E 95% CI | E2E speedup |
|---|---:|---:|---:|---:|---:|---:|---:|
| V31-025 | 0.986479 | 0.896591–1.007523 | 1.005952 | 1.013706x | 0.986490 | 0.896752–1.007730 | 1.013695x |
| V31-026 | 0.205951 | 0.205874–0.216736 | 0.211622 | 4.855534x | 0.206065 | 0.205980–0.216826 | 4.852845x |
| V31-027 | 0.678996 | 0.664247–0.705093 | 0.702962 | 1.472763x | 0.679018 | 0.664278–0.705143 | 1.472715x |

V31-025 M/A API non-inferiority passes: one-sided 95% upper ratio
`1.005952 <= 1.03`. No M/A E2E median regression exists; all three ratios are
below one.

## Resource and robustness assessment

| Slot | L RSS median KiB | M RSS median KiB | A RSS median KiB | A/max-control |
|---|---:|---:|---:|---:|
| V31-025 | 84628 | 39164 | 38880 | 0.993 |
| V31-026 | 84680 | 73840 | 73748 | 0.999 |
| V31-027 | 109444 | 109188 | 110220 | 1.009 |

There were zero thermal invalidations, zero affinity deviations, zero runtime
policy deviations, and zero nonzero return codes. All 96 candidate processes
(warmups included) recorded exactly one router execution. Every meaningful
field agreed in every eligible L/A and M/A pair.

V31-025 individual-process CVs were high (API: L 0.586, M 0.550, A 1.058),
but paired-log confidence bounds retained the registered conclusion. The
affected slots had lower CVs except legacy V31-027 (0.282). Order-stratified
ratios did not reverse any conclusion: V31-025 M/A API strata were 0.978 and
0.978; affected-path M/A strata remained improvements. Legacy-inclusive order
differences were largest on V31-025 (about 9.6% in log-ratio difference), but
both strata retained an L/A E2E speedup and no throttle/runtime violation was
present. No protocol threshold was altered after observing these data.
