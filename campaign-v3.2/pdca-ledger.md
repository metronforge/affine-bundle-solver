# Ralph quartet ledger

Exactly four cycles were executed.

| Cycle | Hypothesis | Result | Disposition | Next selection |
|---:|---|---|---|---|
| 1 | One or two high-level phases dominate each slot | Largest two phases explain 67.0–87.6%; V31-027 kernels are 72.2% | Accepted | Attribute V31-027 native kernels |
| 2 | A small native function set explains the dominant phase | 262 QRCP calls consume 73.6% of V31-027; memory syscalls consume 5.151 ms | Accepted | Test scaling and thread sensitivity |
| 3 | The cost shows repeated-computation scaling | QRCP calls follow `2*n+6`; local wall exponent 4.24; four threads hurt all slots | Accepted/refined | Reproduce via public C functions and falsify generic-size explanation |
| 4 | The leading generator remains dominant independently | Direct C generator is 72.2% and 42.37x slower than the larger-element V31-026 generator | Accepted | Stop with `BOTTLENECK_IDENTIFIED` |
