# Exact command ledger

Commands execute from `/home/viktor/task5-v36-isolated-blas` with the system
`python3` unless a command says otherwise. Paths are intentionally absolute.

## Harness tests and manifest

```sh
python3 -m pytest -q tests/test_v36_isolated_blas.py
python3 -m pytest -q
python3 -m task5v36.campaign \
  --out task5-v36-isolated-blas/campaign-v3.6/manifest.json
python3 -m task5v36.bundle \
  --out task5-v36-isolated-blas/campaign-v3.6/bundles \
  --slots V31-025 V31-026 V31-027
```

## Independent accepted-main builds

```sh
git -C /home/viktor/affine-bundle-solver worktree add --detach \
  /home/viktor/task5-v36-main-calibration \
  bb6c30d03191a92695b16d21581bfea6dce9942e
cmake -S /home/viktor/task5-v36-main-calibration \
  -B /home/viktor/task5-v36-main-calibration/build-m1 -G "Unix Makefiles" \
  -DABS_BLAS=system -DABS_ARCH_FLAGS=-march=native \
  -DABS_BUILD_TESTING=OFF -DABS_BUILD_EXAMPLES=OFF
cmake --build /home/viktor/task5-v36-main-calibration/build-m1 -j2
cmake -S /home/viktor/task5-v36-main-calibration \
  -B /home/viktor/task5-v36-main-calibration/build-m2 -G "Unix Makefiles" \
  -DABS_BLAS=system -DABS_ARCH_FLAGS=-march=native \
  -DABS_BUILD_TESTING=OFF -DABS_BUILD_EXAMPLES=OFF
cmake --build /home/viktor/task5-v36-main-calibration/build-m2 -j2
```

## Calibration

For C1, replace `CONFIG`, `SEED`, and output names below with
`C1`, `2026093601`, and `aa-C1`; for C2 use `C2`, `2026093602`, and `aa-C2`.

```sh
python3 -m task5v36.protocol \
  --dataset aa-CONFIG --configuration CONFIG \
  --arm M1=solver=/home/viktor/task5-v36-main-calibration/build-m1/libcertified_solver.so \
  --arm M2=solver=/home/viktor/task5-v36-main-calibration/build-m2/libcertified_solver.so \
  --bundle-root task5-v36-isolated-blas/campaign-v3.6/bundles \
  --slots V31-025 V31-026 V31-027 \
  --repetitions 31 --warmups 1 --seed SEED --timeout-seconds 30 \
  --checkpoint task5-v36-isolated-blas/campaign-v3.6/timings/aa-CONFIG.json
python3 -m task5v36.analysis aa --configuration CONFIG \
  --input task5-v36-isolated-blas/campaign-v3.6/timings/aa-CONFIG.json \
  --output task5-v36-isolated-blas/campaign-v3.6/analysis/aa-CONFIG.json \
  --samples 100000 --seed 2026093699
```

C3 uses role `mixed`, five repetitions, seed `2026093603`, and dataset/output
name `aa-C3-diagnostic`; its analysis is recorded but not selectable.

```sh
python3 -m task5v36.analysis select \
  --decision C1=task5-v36-isolated-blas/campaign-v3.6/analysis/aa-C1.json \
  --decision C2=task5-v36-isolated-blas/campaign-v3.6/analysis/aa-C2.json \
  --decision C3=task5-v36-isolated-blas/campaign-v3.6/analysis/aa-C3-diagnostic.json \
  --output task5-v36-isolated-blas/campaign-v3.6/analysis/selection.json
```
