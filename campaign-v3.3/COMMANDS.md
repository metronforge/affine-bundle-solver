# Exact rerun commands

Run from `/projects/research-assistant/task5-v33-reusable-qrcp`.

```sh
# Immutable manifest regeneration
python -m task5v33.campaign --out campaign-v3.3/manifest.rerun.json

# Exact-library harness verification
TASK5_BASELINE_SOLVER_LIB=/projects/research-assistant/task5-solver-final/build-task5-final/libcertified_solver.so \
TASK5_CANDIDATE_SOLVER_LIB=/projects/research-assistant/task5-solver-v33-merged/build-v33-final/libcertified_solver.so \
TASK5_SOLVER_LIB=/projects/research-assistant/task5-solver-v33-merged/build-v33-final/libcertified_solver.so \
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 BLIS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 \
pytest -q

# Official uninstrumented comparison
python -m task5v33.performance \
  --baseline-library /projects/research-assistant/task5-solver-final/build-task5-final/libcertified_solver.so \
  --candidate-library /projects/research-assistant/task5-solver-v33-merged/build-v33-final/libcertified_solver.so \
  --out campaign-v3.3/timings/official-bounded-large.rerun.json \
  --repetitions 5

# Diagnostic residual profile; excluded from official statistics
TASK5_SOLVER_LIB=/projects/research-assistant/task5-solver-v33-merged/build-v33-final/libcertified_solver.so \
TASK5_SOLVER_INCLUDE=/projects/research-assistant/task5-solver-v33-merged/include \
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 BLIS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 \
python -m task5v32.cycle2 \
  --out campaign-v3.3/evidence/cycle-04-residual-profile-rerun.json \
  --build-dir /tmp/task5-v33-residual-profile \
  --trials 5
```

There is no canonical resume command: the 27-slot campaign was correctly never started because the pre-gate failed.
