# Split Public API Design

## Intent

Expose numerical solving, evaluation of a caller-owned candidate, and nearby-system certification as three operations with distinct contracts. Preserve every existing symbol and its observable behavior, the four default policy values, and the frozen 36-system regression corpus.

## Public contracts

`bsolve` accepts finite row-major `A`, finite `b`, dimensions, a `BSOperationalPolicyV1`, caller storage for `x`, and a versioned solve result. It uses the canonical router controls `(1, 2, 2, seed 17)` internally. `bsolve_ex` accepts the same operation plus a versioned `BSSolveOptionsV1` for advanced control. Both return a numerical candidate plus operational evidence and share one implementation. Neither runs the nearby-system audit nor claims exact-source status. `BSSolveResultV1` is a typedef of the semantically identical `BSOperationalResultV1`, avoiding an ABI-identical duplicate. The legacy `full` argument remains on released router APIs only and is absent from both new solve entry points and their options.

`abs_check_candidate` accepts finite caller-owned `A`, `b`, and arbitrary finite `x`, dimensions, the existing operational policy, and `BSCandidateCheckResultV1`. The result contains an upper bound for `max_i |a_i x-b_i|`, an upper bound for the established row-wise mixed-2-norm backward error, and a verdict: `WITHIN_QUALITY_BOUND`, `NOT_ESTABLISHED`, or `BOUND_UNAVAILABLE`. The function return describes execution only. A successfully computed bound above `quality_threshold` is `NOT_ESTABLISHED`, never rejection. Invalid inputs and execution failures leave a fail-closed initialized result and do not fabricate a verdict.

`bs_certify_candidate` accepts finite caller-owned `A`, `b`, and `x` and returns a versioned nearby-system profile. Candidate-dependent UNIQUE and INFINITE witnesses use the supplied `x`; the operation never invokes router selection and never solves to reconstruct `x`. Certificate-only computations needed for proof objects remain permitted. The result retains the existing nearby-system meaning and does not claim exact-source status.

Existing `bsolve_router_policy_api`, `bsolve_certified_policy_api`, `bsolve_certified_api`, `bsolve_certified_diag_api`, policy/result layouts, and defaults remain unchanged. The combined functions remain compatibility/composition APIs.

## Internal architecture

Before:

```text
combined certified call -> router -> hidden operational witness
                        -> independent generators (including fresh x solves)
                        -> nearby profile
```

After:

```text
bsolve(defaults)      -> shared solve -> router evidence + numerical x
bsolve_ex(options)    -> shared solve -> router evidence + numerical x
abs_check_candidate  -> strict candidate-bound kernel(A,b,x)
bs_certify_candidate -> proof generators using caller x + strict verifiers
legacy combined      -> unchanged compatibility path
```

The solve implementation may use the existing LAPACK least-squares kernel to materialize the public candidate after the router establishes operational information. Deferred checking and certification receive `x` explicitly and have deterministic test hooks proving that they do not enter router selection or candidate reconstruction.

## Versioning and failures

New result structures begin with `struct_size`. Initializers write only the V1 prefix, callers may advertise larger storage, and suffix bytes remain untouched. Undersized outputs are untouched and rejected. Valid-sized outputs are initialized before validating other inputs. Policies retain their current validation and default values (`1e-13`, `1e-9`, `2e-10`, `1e-14`).

Execution statuses and evidence verdicts are separate. Allocation and LAPACK failures are execution failures. Candidate bound unavailability after otherwise valid evaluation is represented by `BOUND_UNAVAILABLE` only when no finite rigorous bound can be returned.

## Semantic regression classification

| Field/category | Regression expectation |
|---|---|
| Unique-system `x` | Numerical agreement with independent LAPACK/oracle solution |
| Non-unique-system `x` | Residual and promised minimum-norm semantics, not vector identity |
| Residual and candidate bounds | Independent numerical enclosure/agreement |
| Operational classification | Exact semantic agreement with the legacy operational path |
| Candidate verdict | Exact enum agreement with independently evaluated threshold decision |
| Certificate verdict/mask/codes | Exact semantic agreement where inputs and generators overlap |
| Certificate bounds | Numerically equivalent under existing tolerance plus independent inequalities |
| Exact-source fields | Exactly UNKNOWN / NOT_VERIFIED |
| Timings | Not contractual |
| Internal iteration/diagnostic counts | Not contractual unless already frozen by a legacy test |
| Backend metadata | Not contractual |
| SVD/null-space basis or witness choice | Not contractual |

## Decisions and MC/DC

Candidate verdict logic is expressed as:

```text
available = residual_bound_finite AND backward_error_bound_finite
within = available AND backward_error_bound <= quality_threshold
verdict = !available ? BOUND_UNAVAILABLE
        : within     ? WITHIN_QUALITY_BOUND
                     : NOT_ESTABLISHED
```

CNF-derived pairs independently toggle each finiteness condition while holding the other true, and toggle the threshold comparison while both are true. Input-validation decisions similarly receive independent pairs for pointer presence, positive/representable dimensions, finite source data, finite candidate data, valid policy, and sufficient result size. Coupled overflow guards that cannot be materialized without an invalid address are reported as unreachable rather than claimed covered.

## DGESDD/fallback hypothesis

Inspect `smallest_right_vector_dgesdd` and its callers on the canonical base. Its local buffers are freed only after the final `dgesdd` and subspace extraction, and each allocation/query failure frees all owned buffers before returning. Add deterministic failure coverage only if a reproducible unsafe lifetime exists; do not change code speculatively.

## Verification

Keep the existing 36-system files and hashes unchanged. Run the legacy 36-case baseline and 36x5 qualification independently, then consume the same cases through solve, candidate check, candidate certification, combined-vs-composed comparisons, arbitrary/perturbed candidates, and independent NumPy/SVD/residual oracles. Add native ABI/error/no-re-solve tests, MC/DC evidence, symbol/header checks, and ASan/UBSan runs covering repeated operations and injected failures.
