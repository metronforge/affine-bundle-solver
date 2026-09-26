# Measurement-protocol decision

Result: **FAIL — official qualification prohibited**.

The two independently built M libraries loaded identical numeric-library basenames and all six API/end-to-end point ratios stayed within the preregistered `[0.97,1.03]` window. Nevertheless, the complete A/A gate failed:

| Slot | Metric | M2/M1 paired point | One-sided 95% upper | M1/M2 CV |
|---|---|---:|---:|---:|
| V31-025 | API | 0.988691 | 0.996433 | 17.58% / 7.03% |
| V31-025 | end-to-end | 0.999589 | 1.004476 | 13.36% / 4.30% |
| V31-026 | API | 0.995304 | 1.027933 | 13.21% / 13.42% |
| V31-026 | end-to-end | 0.996767 | 1.018140 | 19.10% / 11.82% |
| V31-027 | API | 1.023995 | **1.043563** | 11.28% / 17.75% |
| V31-027 | end-to-end | 1.020223 | **1.046280** | 8.45% / 13.34% |

V31-027 exceeds the frozen 1.03 upper-confidence limit. The absolute order-effect estimates for V31-026 and V31-027 are also above `log(1.02)` even though their wide confidence intervals include zero. Thus both `one_sided_upper_below_1_03` and `no_systematic_order_effect` are false.

As preregistered, no L/M/F/A official dataset was collected, so no Branch A qualification, direct contemporaneous L/A speedup, V31-025 non-inferiority claim, aggregate interval, official RSS result, or dense post-gating result is permitted. Historical ratios were not multiplied.

The thread diagnostic reinforces the environmental explanation without overriding the frozen gate. With pinned CPUs, `OPENBLAS_NUM_THREADS=1` gave API medians of 27.91/89.47/51.94 ms for V31-025/026/027; `OPENBLAS_NUM_THREADS=4` gave 106.42/127.76/129.99 ms when OMP was four. Unpinned results differed again. Every runner process simultaneously mapped system OpenBLAS, SciPy-bundled OpenBLAS, MKL, libgomp, and libiomp. The qualification protocol correctly detected that this mixed-runtime host cannot support a 3% non-inferiority decision under the mandated four-thread settings.
