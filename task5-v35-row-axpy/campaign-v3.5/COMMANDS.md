# Exact v3.5 commands

Run from `/projects/research-assistant/task5-v35-host-qualification`.

Library assignments used in all commands:

```sh
L=/projects/research-assistant/task5-v35-solver-control/build-v35-native/libcertified_solver.so
M1=/projects/research-assistant/task5-v35-solver-baseline/build-v35-native-1/libcertified_solver.so
M2=/projects/research-assistant/task5-v35-solver-baseline/build-v35-native-2/libcertified_solver.so
F=/projects/research-assistant/task5-v35-solver-flag/build-v35-native/libcertified_solver.so
A=/projects/research-assistant/task5-v35-solver-candidate/build-v35-official/libcertified_solver.so
OUT=task5-v35-row-axpy/campaign-v3.5
```

Diagnostic M/F/A:

```sh
python -m task5v35.protocol --arm-library M=$M1 --arm-library F=$F --arm-library A=$A --arms M F A --slots V31-025 V31-026 V31-027 --repetitions 5 --warmups 1 --seed 2026092601 --cpu-set 1,3,6,8 --out $OUT/timings/effect-diagnostic.json
```

A/A and frozen analysis:

```sh
python -m task5v35.protocol --arm-library M1=$M1 --arm-library M2=$M2 --arms M1 M2 --slots V31-025 V31-026 V31-027 --repetitions 31 --warmups 1 --seed 2026092602 --cpu-set 1,3,6,8 --out $OUT/timings/aa-calibration.json
python -m task5v35.analysis aa --input $OUT/timings/aa-calibration.json --out $OUT/analysis/aa-decision.json --samples 100000 --seed 2026092699
```

Official one-shot and analysis:

```sh
python -m task5v35.protocol --arm-library L=$L --arm-library M=$M1 --arm-library F=$F --arm-library A=$A --arms L M F A --slots V31-025 V31-026 V31-027 --repetitions 31 --warmups 1 --seed 2026092604 --cpu-set 1,3,6,8 --out $OUT/timings/official-qualification.json
python -m task5v35.analysis official --input $OUT/timings/official-qualification.json --out $OUT/analysis/official-decision.json --samples 100000 --seed 2026092699 --integrity
```

Thread matrix consists of eight `task5v35.protocol` invocations using one M arm, five repetitions, one warmup, all slots, derived seeds `2026092603` through `2026092610`, CPU set `1,3,6,8` or `0-21`, and explicit `--thread-value OPENBLAS_NUM_THREADS={1|4} --thread-value OMP_NUM_THREADS={1|4}`. All other supported thread variables remain four.

Dense secondary is invoked through the committed `run_dense_dataset` function with M/A, seed `2026092605`, CPU set `1,3,6,8`, and an atomic checkpoint.
