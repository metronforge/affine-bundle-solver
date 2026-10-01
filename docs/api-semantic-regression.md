# Split API semantic regression fields

The frozen 36-system corpus is consumed without changing any matrix, right-hand side, expected property, hash, or provenance field.

| Field/category | Comparison |
|---|---|
| Unique-system `x` | Numerically equivalent to independent NumPy/LAPACK solution |
| Non-unique `x` | Residual and minimum-norm property; vector identity is not required |
| Operational status/certainty | Exact equality with the preserved combined API |
| Candidate residual/backward bounds | Independently recomputed in `numpy.longdouble` and required to enclose the result |
| Candidate verdict | Exact enum contract; quality success must agree with the independent threshold check |
| Nearby mask and generator/verifier codes | Exact equality for legacy combined vs composed path |
| Nearby eta bounds | Numerical equivalence under the existing floating tolerance |
| Exact-source status | Remains UNKNOWN / NOT_VERIFIED |
| Timings | Not contractual and never compared |
| `bsolve` vs `bsolve_ex(defaults)` router metadata | All exposed non-timing fields compared on all 36 systems |
| Router diagnostics/backend metadata | Not compared by the split-path qualification |
| SVD/null-space basis and witness choice | Not contractual and never compared |

The preserved legacy combined API does not expose its numerical solution
vector (`solution_vector` is explicitly `not_exposed_by_current_api` in the
frozen manifest), so a direct `x_legacy` comparison cannot be made without
turning an internal witness into a new legacy contract. Unique new-solve
vectors are instead compared with an independent LAPACK/NumPy solution and
both residuals are checked; rank-deficient vectors are checked by residual
and the promised minimum-norm property.

Certificate acceptance is not justified only by old/new equality. The strict
verifier recomputes each accepted inequality from source `A,b` rather than
trusting generator or router values; the frozen oracle suite checks mask/code/
finite-bound consistency for every case, and the existing independent
high-precision projector oracle checks the non-canonical SVD cases
T8-030/031/032. Exact stored-input ranks remain independently adjudicated by
integer row scaling, modular witnesses, and fraction-free Bareiss elimination.
