# Canonical campaign gate

The canonical 27-slot run was intentionally not started. The task requires final canonical execution only after bounded-large acceptance; the retained comparisons fail that gate. Accordingly `execution-ledger.jsonl` remains the reproducible initial ledger and `results/` contains no canonical rows.

Rerun bounded control: `TASK5_SOLVER_LIB=/projects/research-assistant/task5-solver-final/build-task5-final/libcertified_solver.so OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 BLIS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 python -m task5v31.benchmark --out campaign-v3.1/timings/bounded-large-rerun.json --repetitions 3`.

Resume canonical campaign is intentionally unavailable until a compliant bounded-large acceptance is recorded.
