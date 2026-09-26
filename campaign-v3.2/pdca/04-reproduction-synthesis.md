# PDCA 4 — reproduction, falsification, and synthesis

## PLAN

- Hypothesis: V31-027's compatible-tall inconsistent-witness generator remains dominant through an independently structured measurement route.
- Method: a standalone C driver, linked directly to the frozen libraries, times the public combined API, router snapshot, inconsistent generator, and verifier with `CLOCK_MONOTONIC_RAW`; one warmup is excluded and five trials retained. Separately rerun uninstrumented Python timings and the frozen legacy-equivalent control.
- Acceptance: generator share above 60%, stable ranking, supported API success, semantic equality, and one router execution in every candidate trial.
- Falsifier: a larger-element-count slot costs as much within the same generator, or the finding disappears without interposition.
- Safety: exact binary inputs are hashed; the public API path is unchanged; profiler timing and production timing remain separate.

## DO

Executed the cycle-4 command. The standalone C driver measured V31-025/026/027 directly. The Python route then collected five new uninstrumented trials per slot and five interleaved legacy-equivalent/candidate trials per slot.

## CHECK

The C driver measured the V31-027 combined API at 61.345 ms median (CV 1.22%) and `bs_generate_inconsistent_witness` at 44.288 ms, 72.2%. V31-026 has more matrix elements (36,864 versus 32,768) yet its same generator took 1.045 ms: V31-027 is 42.37x slower. This rejects generic matrix size as the generator explanation. The predeclared total-combined comparison alone was inconclusive (V31-027/V31-026 = 1.033) because V31-026 has a separate verifier hotspot; the narrower public-generator comparison supplies the successful falsifier.

For V31-027, generator return code 6 is expected for a compatible system with no inconsistent certificate; verifier code 99 is the driver's not-invoked sentinel. The supported combined API returned zero on all five trials.

Fresh uninstrumented medians were 94.982, 153.287, and 288.334 ms. Relative to cycle 1 they changed -10.2%, +3.4%, and +0.8%; V31-027, which drives the attribution, was stable. Coefficients of variation were 15.9%, 10.8%, and 13.1%, while the direct C V31-027 route was 1.22%. The full control differential retained semantic equality for every slot and every candidate trial had exactly one router execution.

## ACT

Accept. Two independent routes agree on a 72–74% V31-027 share and the call-count/scaling probe explains why. Terminal verdict: `BOTTLENECK_IDENTIFIED`. The next task should cache or hoist the single QRCP factorization and reuse its implicit-Q completion vectors during the compatible-tall null-direction scan, guarded by regression, sanitizer, ABI, and exact-head performance checks. No optimization is implemented here.
