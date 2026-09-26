# Porting and net-diff proof

## RED/GREEN

The frozen `0b9f9cf` row differential and its CMake/CI registration were applied first to unoptimized `bb6c30d`.

- RED: `candidate-red-ctest.log` exits nonzero with `1,968 failures`; every call reports zero observed optimized rows, ending with `1,968 calls, 0 rows, 0 entries compared`. This is the expected failure because the private hook/optimized row pass do not exist yet.
- GREEN: after overlaying the reviewed source delta, `candidate-green-ctest.log` passes and reports `1,968 calls, 31,160 rows, 1,502,768 entries compared; 228 signed-zero-only endpoint differences; 0 failures`.

The test exercises finite normal values, positive/negative zero, subnormals, wide exponents (including supported non-finite intermediate outcomes), all four supported initial rounding modes, structural-zero diagonal rows, dense rows, and the production alias pattern in which `evec` is the accumulator and `elo`/`ehi` are the two output buffers.

## Exact source correspondence

Candidate commit: `dd30ef900ff7f48d4fe97e79aae94b7e64c48741`

Candidate tree: `a89ce2def1fc1b2ef4644cc4d17f13c533b099b7`

Parent: `bb6c30d03191a92695b16d21581bfea6dce9942e`

The final delta is exactly four files, 303 insertions and 17 deletions:

- `.github/workflows/ci.yml`: register the row differential in the native-leak partition and exclude it from the Python-semantics partition;
- `CMakeLists.txt`: build the frozen differential with the strict flags and private hook;
- `src/status_certificate.c`: reviewed two-pass row reconstruction plus private hook;
- `tests/test_unique_verifier_rows.c`: frozen differential.

The production source blob is exactly `adf511947e58cffff0456365514c0ab6c5a7fa44`, identical to `0b9f9cf:src/status_certificate.c`. The test blob is exactly `2c37edfa83d4b4fdd8e03c0e6ecbbf11ad901536`, identical to `0b9f9cf:tests/test_unique_verifier_rows.c`.

An explicit three-way overlay with merge base `ad8b8bea07feefdbb81fd791459816c5f118c053`, accepted main `bb6c30d`, and old candidate `0b9f9cf` auto-merges CMake and reports only a workflow content conflict. The conflict is caused by accepted Task-1 sanitizer/FP partition edits in the same two regexes. Resolution retained main verbatim and inserted only the same `test_unique_verifier_rows` token in each regex. No old FP-gate, ENOMEM, manuscript, claim-registry, or semantics delta was reintroduced. `git diff --check` passes.

## Signed-zero observer audit

The potentially differing `elo[j]` and `ehi[j]` endpoints are consumed in production only by:

```c
evec[j] = fmax(fabs(elo[j]), fabs(ehi[j]));
da_up = norm_up(evec, n);
```

The private test hook is compiled only into the differential executable and observes the raw endpoints to classify exact equality versus signed-zero-only differences. Repository search finds no production `signbit`, `copysign`, reciprocal, branch, serialization, or other sign-sensitive observation of `elo`, `ehi`, or `evec` before the contract-normalizing `fabs`. Therefore all 228 endpoint sign changes are explicitly justified contract-equivalent differences and downstream radii are bit-identical.

