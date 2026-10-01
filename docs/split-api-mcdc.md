# Split API MC/DC evidence

## Candidate verdict

The implementation uses:

```text
A = finite(max_abs_residual_up)
B = finite(mixed_backward_error_up)
Q = mixed_backward_error_up <= quality_threshold
available = A AND B
within = available AND Q
```

CNF reasoning gives an independent pair for `Q` by holding `A=B=true`: the exact identity candidate produces `Q=true` and `WITHIN_QUALITY_BOUND`; changing only `x[1]` from `2` to `2.001` produces `Q=false` and `NOT_ESTABLISHED`.

For `B`, the exact identity candidate has `A=B=true`; the finite subnormal case `A=[DBL_TRUE_MIN], b=[0], x=[0.5]` keeps an upward residual enclosure finite while the denominator's rigorous downward lower bound rounds to zero, so `A=true,B=false` and the verdict becomes `BOUND_UNAVAILABLE`.

No independent public-input pair exists for `A=false,B=true`. The backward-error numerator is the same maximum residual enclosure; if that enclosure is non-finite, division cannot yield a finite rigorous upper bound. `A` and `B` are therefore mathematically coupled in that direction. Coverage is partial MC/DC for availability, not claimed full MC/DC.

The CNF for the two decisions is:

```text
available <-> A AND B:
  (!available OR A) AND (!available OR B) AND (!A OR !B OR available)

within <-> available AND Q:
  (!within OR available) AND (!within OR Q)
  AND (!available OR !Q OR within)
```

The executed assignments are:

| Case | A | B | Q | available | within/verdict |
|---|---:|---:|---:|---:|---|
| exact identity candidate | 1 | 1 | 1 | 1 | 1 / WITHIN |
| `x[1] += 0.001` | 1 | 1 | 0 | 1 | 0 / NOT_ESTABLISHED |
| `A=DBL_TRUE_MIN,b=0,x=.5` | 1 | 0 | n/a | 0 | 0 / BOUND_UNAVAILABLE |

Thus exact/perturbed demonstrates the independent effect of `Q`, and
exact/subnormal demonstrates the reachable independent effect of `B` on
availability. `A` has no independent pair for the coupling stated above.

## Candidate input validation

The execution decision is the conjunction:

```text
O = result pointer present and struct_size >= V1
P = policy present and valid
S = A, b, and x pointers present
D = m > 0 and n > 0 and extents representable
F = every A, b, and x element finite
execute = O AND P AND S AND D AND F
```

The all-true assignment uses `A=I`, `b=x=[1]`, default policy, and a V1 result. Concrete independent-effect pairs hold the other materialized conditions true and toggle: each source pointer, `m`, `n`, policy presence, policy threshold validity, candidate finiteness, result presence, and result size. Representability overflow guards are coupled to dimensions and cannot be materialized with accessible caller storage; they are tested as invalid dimensions where possible and are not claimed as independent MC/DC pairs.

For `execute <-> O AND P AND S AND D AND F`, the CNF is one implication
clause per condition plus the reverse clause:

```text
(!execute OR O) AND (!execute OR P) AND (!execute OR S)
AND (!execute OR D) AND (!execute OR F)
AND (!O OR !P OR !S OR !D OR !F OR execute)
```

`test_split_api_decisions.py` and the native contract test use the all-true
case as one member of every pair. They independently toggle `O` with null and
undersized results; `P` with null and invalid threshold policy; each member of
`S` with null `A`, `b`, or `x`; the concrete members of `D` with zero `m` or
`n`; and `F` with non-finite `x`. Non-finite `A` and `b` are covered by the
native test as additional representatives of the same `F` condition.

## Certification and solve wrappers

Their public validation decisions have the same conjunction form and use the
same all-true/one-false construction in `test_solve_api.c` and
`test_candidate_certification.c`: output size, each pointer, each positive
dimension, policy validity for solve, and finiteness are toggled independently
where materializable. Extent-overflow guards remain coupled to dimensions and
addressable storage and are not claimed as independent pairs.

Solve completion is:

```text
success = validation_ok AND router_ok AND least_squares_ok
```

The least-squares test double holds validation and router success true and
independently toggles `least_squares_ok`, once as allocation failure and once
as LAPACK/numerical failure. Router allocation failure already belongs to the
preserved router contract; no new injectable pair was added, so full MC/DC is
not claimed for this composition decision.

The corrected DGESDD fallback decision is:

```text
fallback = witness_prepared AND (qrcp_generation_failed OR qrcp_verify_failed)
```

Its CNF is:

```text
(!fallback OR witness_prepared)
AND (!fallback OR qrcp_generation_failed OR qrcp_verify_failed)
AND (!witness_prepared OR !qrcp_generation_failed OR fallback)
AND (!witness_prepared OR !qrcp_verify_failed OR fallback)
```

The no-failure control and forced-QRCP-rejection case hold witness preparation
true and toggle verifier failure, proving its independent effect. Allocation
failure in `infinite_witness_prepare` gives `witness_prepared=false` while the
failure disjunction is true and proves the preparation guard independently
suppresses fallback. `witness_prepared=true` with
`qrcp_generation_failed=true` is coupled/unreachable because successful
preparation defines the generator code as zero; no independence claim is made
for that term.

Certification success versus an empty nearby mask is deliberately not a
Boolean execution decision: successful operation and evidence acceptance are
separate outputs. The no-re-solve test independently observes router and
candidate-reconstruction counters and demonstrates that candidate checking
and certification leave both unchanged.
