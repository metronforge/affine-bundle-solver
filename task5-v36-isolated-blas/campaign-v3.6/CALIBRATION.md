# Cycle 2 calibration decision

All data are fresh M/M observations from accepted main
`bb6c30d03191a92695b16d21581bfea6dce9942e`; no candidate timing existed when
this decision was sealed. Every scheduled record was retained and no
observation was rerun or excluded.

| Config | Eligible records | Worst API upper | Worst E2E upper | Fingerprints | Order | Thermal | Decision |
|---|---:|---:|---:|---|---|---|---|
| C1 | 186/186 | 1.023451 | 1.023410 | pass | pass | pass | eligible, selected |
| C2 | 186/186 | 1.013460 | 1.013220 | pass | pass | fail | ineligible |
| C3 diagnostic | 30/30 diagnostic | 1.210205 | 1.210030 | mixed as specified | diagnostic effects observed | pass | nonselectable |

C1 passed all six strict `<1.03` API/end-to-end bounds, all six frozen order
checks, exact M1/M2 fingerprint matching, fixed affinity, equal budgets, direct
runtime limits, complete records, and throttle checks. Its solver processes
mapped only system OpenBLAS (four threads) and libgomp (one thread) among
numeric/OpenMP pools.

C2's statistical bounds passed, but observation
`aa-C2:V31-025:eligible:19:M1` recorded an increase in the available package
throttle counters during the timed process. The raw record is retained. Under
the preregistered fail-closed thermal gate C2 is ineligible; it was not rerun.

C3 reproduced the previous mixed environment: system OpenBLAS, SciPy OpenBLAS,
MKL, libgomp, and libiomp5 were all mapped at four threads. It showed a
V31-025 API upper bound of 1.210205 and a preregistered order effect. C3 was
diagnostic and could never be selected.

The frozen selection rule therefore chooses **C1**, the only eligible
configuration. The tie-break was not reached.

