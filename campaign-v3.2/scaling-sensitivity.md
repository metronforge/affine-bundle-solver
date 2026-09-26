# Scaling and sensitivity table

Official comparison remains four threads. One-thread rows are attribution probes only.

| Case | Shape | Threads | Cold wall (ms) | Warm wall median (ms) | CPU equivalents | Peak RSS (KiB) | QRCP calls/call | QRCP time/call (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V31-025 | 128x256 | 1 | 20.211 | 8.861 | 1.000 | 89,520 | 4 | 3.681 |
| V31-025 | 128x256 | 4 | 95.768 | 15.836 | 4.442 | 90,784 | 4 | 23.440 |
| V31-026 | 192x192 | 1 | 84.779 | 58.082 | 1.000 | 86,904 | 4 | 2.088 |
| V31-026 | 192x192 | 4 | 177.593 | 67.448 | 1.073 | 87,012 | 4 | 18.812 |
| V31-027 | 256x128 | 1 | 157.633 | 71.161 | 1.000 | 86,140 | 262 | 47.819 |
| V31-027 | 256x128 | 4 | 252.957 | 232.330 | 1.382 | 86,456 | 262 | 194.629 |
| V32-TALL-128x64 | 128x64 | 4 | 35.694 | 8.971 | 3.959 | 85,568 | 134 | 3.879 |
| V32-TALL-192x96 | 192x96 | 4 | 129.336 | 103.036 | 1.321 | 86,288 | 198 | 83.070 |
| V32-TALL-256x128 | 256x128 | 4 | 257.945 | 266.053 | 1.396 | 86,564 | 262 | 216.273 |
| V32-TALL-320x160 | 320x160 | 4 | 544.421 | 421.775 | 1.405 | 87,268 | 326 | 384.946 |

The nearby 2:1 tall series has empirical warm-wall exponent 4.24 and QRCP-time exponent 5.02 versus `n`. These are local empirical fits, not asymptotic proofs. The directly measured structural result is the linear call-count law `2*n + 6`; combined with repeated QR factorization, it explains the steep growth.
