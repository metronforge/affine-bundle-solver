# API Regression Baseline Design

## Purpose

Create a regression baseline before the linear-system solving API is separated
from certificate generation. The change records current behavior; it does not
perform the API separation and does not alter historical evidence in
`metronforge/abs-apps`.

The baseline follows `metalogic-revised.md`: every technical claim is bound to
an inspected source revision or a fresh execution, mathematical and behavioral
claims remain distinct, discovery counts are asserted, and conclusions are
limited to the cases actually processed.

## Frozen source revisions

- `metronforge/abs-apps` main:
  `ae9b662d7f5755418aa80f31ade1fffcbefebafd`
- `metronforge/affine-bundle-solver` main:
  `2741af01f0c0116347dbc81b21998f538690dcea`

The implementation branch starts from the solver revision above. Before final
verification, mutable upstream refs are checked again; evidence continues to be
reported against the frozen SHAs even if a remote branch subsequently moves.

## Corpus boundary

The historical design manifest contains 1000 slots, but a slot or retained
result is not automatically a reproducible input. The retained Task 7 inventory
contains 399 evidence records (122 historical, 177 migrated, and 100 freshly
executed), while the repository does not contain exact input files for all 399.
The solver's `results/blockprefix_final_1000.json` is an aggregate result and is
never treated as an input corpus.

The separate V31 engineering dataset has 27 slot IDs and 324 retained
observations. Its input bundles are referenced through absolute paths outside
both repositories and are not present in either repository. It remains
result-only evidence and is not imported.

The self-contained baseline uses the 36 concrete Task 8 NPZ inputs tracked by
`abs-apps`:

```text
campaigns/affine-bundle-solver-1000/results/
  task8-targeted-expansion/inputs/T8-001.npz ... T8-032.npz
  task8-targeted-expansion/inputs/T8-036.npz ... T8-039.npz
```

`T8-033`, `T8-034`, and `T8-035` were planned but not materialized and are not
invented or counted. Selection depends only on dimensional spread and includes
all 36 available inputs:

- 26 square systems, from 16x16 through 153x153;
- 8 tall systems: 75x40, four 30x16, and three 64x32 systems;
- 2 wide systems: 21x24 and 56x64.

Thus the asserted shape partition is 26 square, 8 tall, and 2 wide, for exactly
36 systems. The manifest generator must derive and assert these counts from the
arrays rather than trust this prose.

No prior solver status, family label, campaign group, or performance result is
used to select a case.

## Provenance and attribution

Each fixture manifest entry records the `abs-apps` SHA, source slot ID, original
path, shape, NPZ SHA-256, and SHA-256 of canonical contiguous little-endian
binary64 bytes for `A` and `b` separately. It also records the source category
and the transformation that produced the solver input.

Attribution is preserved by category:

- `T8-001` through `T8-029` are deterministic constructions implemented in
  `abs-apps` `task8_cases.py`. Their notice credits the `metronforge/abs-apps`
  source revision and identifies the construction parameters.
- `T8-030` through `T8-032` derive from the Radio Astronomy Software Group
  `rasg-datasets` PAPER observation at revision
  `55bd68b28fabe0936011bd9540cbaef9e20809db`, source artifact SHA-256
  `2544212e4bba85319c4628b1e019aa79b6e988a310cd258b258165a3999439e9`.
  The BSD-2-Clause copyright notice for Radio Astronomy Software Group is
  reproduced in the solver's third-party notice.
- `T8-036` through `T8-039` derive from SuiteSparse Matrix Collection objects
  `HB/bcsstk01`, `HB/bcsstk02`, `HB/bcsstk04`, and `HB/bcsstk05`. The notice
  retains the object-header credit to J. Lewis and editors I. Duff, R. Grimes,
  and J. Lewis, records the collection's CC-BY-4.0 attribution requirement, and
  cites Davis and Hu (2011), DOI `10.1145/2049662.2049663`, and Kolodziej et al.
  (2019), DOI `10.21105/joss.01244`. The transformation to dense binary64 and
  the controlled unit-load right-hand side are stated explicitly.

The attribution file distinguishes a copied/derived fixture from authorship of
the solver. It does not imply endorsement by the upstream data providers.

## Fixture representation and discovery

The solver vendors the 36 NPZ fixtures because their combined size is small and
exact byte identity matters. A checked-in JSON manifest is the single discovery
index. The runner rejects:

- any discovered count other than 36;
- a missing, extra, or duplicate ID;
- a shape that disagrees with the manifest;
- an NPZ, `A`, or `b` hash mismatch;
- non-binary64 or non-finite input;
- a skipped or unexecuted case.

The manifest records recipe parameters for traceability, but CI consumes the
frozen arrays and does not depend on `abs-apps`, its Python package, or network
access.

## API observations

Each fixture is freshly run against the solver implementation under test. The
runner captures the policy and invocation mode, API return code, operational
status/certainty/rank or rank interval, solution-dependent fields when present,
residual and quality fields, the nearby-status mask and eta profile, proof
generator/verifier codes, the compatibility projection, and exact-source
verification fields.

Expected fields are classified as:

- `oracle`: independently established from the stored `A,b`;
- `invariant`: required by the public API contract;
- `behavior`: a regression snapshot of the current implementation;
- `dont_care`: timing, unstable diagnostics, semantically absent fields, and
  any field for which no justified portable assertion is available.

Floating comparisons use a field-specific absolute/relative tolerance derived
from the fresh reference executions and cross-build observations. NaN presence
is compared semantically, never by ordinary floating equality. Elapsed time is
always `dont_care`.

The same binary64 inputs are also executed in fresh processes with one and two
BLAS threads. Status, rank, certificate mask, and generator/verifier codes must
match exactly. Finite floating diagnostics must agree within `atol=1e-12` or
`rtol=1e-10`. This bound admits only rounding-scale reduction differences in
the selected corpus: it deliberately rejects the pre-baseline T8-038 defect,
where `eta_inconsistent` changed by about `8e-2` solely with thread count. In
addition, T8-038's repaired deterministic full-row-rank construction is checked
bit-for-bit across thread counts and must be accepted by the unchanged strict
verifier in both processes.

## Mathematical oracle and semantic separation

Every fixture receives an independent mathematical classification. Analytic
constructions use their checkable rank/null-space derivation. Other fixtures use
exact ranks of `A` and `[A|b]` over the rational values represented by binary64;
integer scaling and modular nonsingularity witnesses may be used to make a full
rank proof practical. The classification follows:

- `rank(A) = rank([A|b]) = n`: unique;
- `rank(A) = rank([A|b]) < n`: infinite;
- `rank(A) < rank([A|b])`: inconsistent.

A NumPy/SciPy result or a prior solver verdict is never promoted to the
mathematical oracle.

Operational status and certificate guarantees remain separate. A nearby-status
certificate establishes an accepted nearby construction with radius `eta`; it
does not establish the exact source class. `certified_status` is tested as the
legacy projection of operational status onto an accepted profile, not as an
exact-source theorem.

For `T8-012`, `T8-013`, `T8-016`, and `T8-017`, the stored binary64 systems have
an independently retained exact-rational `INCONSISTENT` adjudication. The current
operational API can report different statuses under different compatibility
tolerances. Tests preserve both facts and never use a prior solver verdict as
the mathematical oracle.

## Composite decisions, reachability, and MC/DC

The report derives atomic conditions from the current public boundary and
implementation source. At minimum it distinguishes valid input/policy, backend
completion, resolved rank interval, operational compatibility, full column rank,
accepted UNIQUE quality, and the generator/verifier/finite-eta predicates for
each nearby proof type.

Reachability constraints are emitted as CNF. Equivalence is claimed only for a
source path whose implementation establishes it; otherwise the report records
the supported one-way implication. MC/DC pairs are searched among the real 36
fixtures and explicit policy invocations. A pair is accepted only when the
target condition changes, all other modeled conditions stay fixed, and the
decision outcome changes. Conditions without such a real pair are reported as
uncovered. Purpose-built negative fixtures may close a gap, but are stored and
reported separately from `abs-apps` examples.

## Tests and controlled negative

The primary regression test:

1. discovers and hash-validates exactly 36 IDs;
2. executes every discovered case;
3. asserts the exact executed-ID set and count;
4. checks independently justified oracle and API-invariant fields;
5. checks only explicitly selected behavioral fields within justified
   tolerances;
6. reports `dont_care` fields without making them gates.

A controlled negative mode changes one in-memory expected result without
modifying the fixture or manifest. The negative CI step succeeds only when the
regression runner returns nonzero and identifies the intended case and field.
This proves the gate detects a wrong result rather than merely discovering
files or exiting successfully.

## CI and qualification

The 36-case regression job is required on pull requests and pushes to `main`.
It builds the current solver, runs the baseline, and publishes a small execution
summary. Any empty run, missing ID, extra ID, skip, crash, or count mismatch
fails the job.

A separate qualification job executes the same exact 36 fixtures across the
full declared invocation/policy matrix. Its configuration records compiler,
BLAS, thread limits, wall time, and peak RSS. The job asserts exactly 36 unique
fixture IDs and the expected number of total invocations derived from the
matrix. Qualification is separate from the required short regression so its
resource cost and broader semantic matrix are visible rather than hidden in a
single test command.

## Report and post-separation rerun criteria

The checked-in report includes the requested mapping:

`API condition -> MC/DC pair -> abs-apps slot IDs -> input hashes -> expected
outputs/oracle -> test -> CI job`.

It records both frozen repository SHAs, exact commands, processed IDs and counts,
resource observations, uncovered conditions, attribution, and claim limits.

After the future API separation, the same fixtures pass when:

- discovery, hashes, and processed IDs remain identical;
- solving-only outputs match the baseline for fields assigned to that layer;
- certificate-only outputs match the baseline for fields assigned to that layer;
- combined compatibility output equals the documented composition of the two
  new calls;
- exact-source oracle results are unchanged;
- operational outcomes are not substituted for certificate guarantees;
- every intentional semantic change is explicitly reviewed and rebaselined,
  rather than accepted by regenerating snapshots blindly.

## Non-goals

- No API split or ABI change.
- No solver threshold or verifier verdict-rule change.
- No edits to historical `abs-apps` records.
- No claim that 36 cases represent all 1000 planned slots.
- No claim that the V31 27-slot result archive contains reproducible inputs.
