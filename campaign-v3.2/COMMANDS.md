# Task-5 v3.2 exact commands

All commands run from `/projects/research-assistant/task5-v32-bottleneck` with the frozen solver build and all supported thread variables set to four:

```sh
export TASK5_SOLVER_ROOT=/projects/research-assistant/task5-solver-final
export TASK5_SOLVER_BUILD=/projects/research-assistant/task5-solver-final/build-task5-final
export TASK5_SOLVER_INCLUDE=/projects/research-assistant/task5-solver-final/include
export TASK5_SOLVER_LIB=/projects/research-assistant/task5-solver-final/build-task5-final/libcertified_solver.so
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 BLIS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4

python -m task5v32.cycle1 --out campaign-v3.2/evidence/cycle-01-phase-decomposition.json --build-dir /tmp/task5-v32-trace-build --trials 5
python -m task5v32.cycle2 --out campaign-v3.2/evidence/cycle-02-native-hotspots.json --build-dir /tmp/task5-v32-trace-build
python -m task5v32.cycle3 --out campaign-v3.2/evidence/cycle-03-sensitivity.json --build-dir /tmp/task5-v32-trace-build
python -m task5v32.cycle4 --out campaign-v3.2/evidence/cycle-04-reproduction.json --build-dir /tmp/task5-v32-reproduction --trials 5
pytest -q
```

The raw `perf` failure, fallback profiler command, `strace` command, standalone-driver commands, and exact binary-input hashes are embedded in their respective evidence JSON files.
