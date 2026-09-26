# Exact commands

Run harness commands from
`/projects/research-assistant/task5-v34-shared-overhead` and solver commands
from `/projects/research-assistant/task5-solver-v34`.

```sh
# Cycle-1 attribution (diagnostic; regenerates ignored native probes/inputs)
python -m task5v34.cycle1

# Baseline/candidate correctness snapshots
python -m task5v34.cycle2

# Solver normal verification
cmake -S . -B build-v34-candidate
cmake --build build-v34-candidate -j4
ctest --test-dir build-v34-candidate --output-on-failure -j2

# Portable and SciPy-OpenBLAS variants
cmake -S . -B build-v34-portable -DABS_ARCH_FLAGS=''
cmake --build build-v34-portable -j4
ctest --test-dir build-v34-portable --output-on-failure -j2
cmake -S . -B build-v34-scipy -DABS_BLAS=scipy-openblas
cmake --build build-v34-scipy -j4
ctest --test-dir build-v34-scipy --output-on-failure -j2

# Harness verification against exact libraries
TASK5_BASELINE_SOLVER_LIB=/projects/research-assistant/task5-solver-v34/build-v34-baseline/libcertified_solver.so \
TASK5_CANDIDATE_SOLVER_LIB=/projects/research-assistant/task5-solver-v34/build-v34-candidate/libcertified_solver.so \
TASK5_SOLVER_LIB=/projects/research-assistant/task5-solver-v34/build-v34-candidate/libcertified_solver.so \
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 BLIS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 \
python -m pytest -q

# One immutable branch-qualification set; DO NOT rerun this retained dataset
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 BLIS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 \
python -m task5v34.performance \
  --baseline-library /projects/research-assistant/task5-solver-v34/build-v34-baseline/libcertified_solver.so \
  --candidate-library /projects/research-assistant/task5-solver-v34/build-v34-candidate/libcertified_solver.so \
  --out campaign-v3.4/timings/branch-qualification.json
```

There is no post-merge or canonical resume command: the qualification gate
failed, so neither activity was authorized.
