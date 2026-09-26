# Exact command ledger

All relative commands ran from
`/home/viktor/task5-v37-control-reconstruction`. The immutable qualification
commands are reproduced verbatim in `PROTOCOL.md`.

Diagnostic construction:

```sh
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  BLIS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 OMP_DYNAMIC=FALSE \
  MKL_DYNAMIC=FALSE PYTHONHASHSEED=0 \
  taskset -c 1,3,6,8 /home/viktor/miniconda3/bin/python3 \
  -m task5v36.worker --role legacy --configuration C1 \
  --bundle /home/viktor/task5-v36-isolated-blas/task5-v36-isolated-blas/campaign-v3.6/bundles/V31-026 \
  --library /home/viktor/task5-v36-legacy-control/build-v36-qualification/libcertified_solver.so
```

The identical argument/environment construction was run under gdb with
`info threads`, `thread apply all bt full`, registers, disassembly, shared
libraries, and mappings enabled. Root-cause controls changed only
`OPENBLAS_NUM_THREADS` and solver-library presence as recorded in
`ROOT-CAUSE.md`.

Control builds:

```sh
cmake -S /home/viktor/task5-v36-legacy-control -B build-l-v37-control \
  -G 'Unix Makefiles' -DABS_BLAS=system -DABS_ARCH_FLAGS=-march=native \
  -DABS_BUILD_TESTING=ON -DABS_BUILD_EXAMPLES=OFF
cmake --build build-l-v37-control -j2

cmake -S /home/viktor/task5-v36-legacy-control -B build-l-v37-asan \
  -G 'Unix Makefiles' -DABS_BLAS=system -DABS_ARCH_FLAGS=-march=native \
  -DABS_SANITIZE=ON -DABS_BUILD_TESTING=ON -DABS_BUILD_EXAMPLES=OFF
cmake --build build-l-v37-asan -j2

cmake -S /home/viktor/task5-v36-legacy-control -B build-l-v37-scipy \
  -G 'Unix Makefiles' -DABS_BLAS=scipy-openblas \
  -DABS_ARCH_FLAGS=-march=native -DABS_BUILD_TESTING=ON \
  -DABS_BUILD_EXAMPLES=OFF
cmake --build build-l-v37-scipy -j2
```

Validation and analysis:

```sh
python3 -m task5v37.validation --bundle-root \
  task5-v37-control-reconstruction/campaign-v3.7/validation-bundles \
  --legacy-original /home/viktor/task5-v36-legacy-control/build-v36-qualification/libcertified_solver.so \
  --legacy-reconstructed /home/viktor/task5-v37-control-reconstruction/build-l-v37-control/libcertified_solver.so \
  --main /home/viktor/task5-v36-main-calibration/build-m1/libcertified_solver.so \
  --candidate /home/viktor/task5-v36-row-axpy/build-v36-qualification/libcertified_solver.so \
  --safe-slots V31-001 V31-008 V31-015 V31-022 V31-025 V31-027 \
  --target-slot V31-026 --stability-runs 10 \
  --output task5-v37-control-reconstruction/campaign-v3.7/evidence/cycle-03-semantic-stability.json

python3 -m task5v37.audit \
  --input task5-v37-control-reconstruction/campaign-v3.7/timings/qualification.json \
  --schedule task5-v37-control-reconstruction/campaign-v3.7/schedule.json \
  --output task5-v37-control-reconstruction/campaign-v3.7/analysis/audit.json
```
