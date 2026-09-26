# Bounded-large comparison

Final eligible comparison: `timings/bounded-large-cycle-05.json`, three alternating trials after one warm-up per path, all in isolated processes with all five thread variables set to `4`.

| Slot | Control median | Candidate median | Speedup | Semantic agreement |
| --- | ---: | ---: | ---: | --- |
| V31-025 | 95.471 ms | 99.186 ms | 0.963x | yes |
| V31-026 | 182.479 ms | 182.795 ms | 0.998x | yes |
| V31-027 | 307.489 ms | 356.290 ms | 0.863x | yes |

Geometric mean: **0.940x**. This fails the required 1.5x and the no-slot-more-than-10%-slower condition (V31-027 is 13.7% slower). The retained earlier cycle-04 result was 1.172x, also insufficient. No median approaches the 300-second bound; candidate RSS did not regress.
