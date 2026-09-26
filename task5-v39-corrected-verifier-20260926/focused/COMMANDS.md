# Exact focused commands

Run from `/home/viktor/task5-v39-corrected-verifier-evidence`:

```sh
python -m task5v39.protocol --dataset focused-v3.9 --configuration C1 \
  --arm L=legacy=/tmp/task5-v39-work/builds/L-native-system/libcertified_solver.so \
  --arm M=solver=/tmp/task5-v39-work/builds/M-native-system/libcertified_solver.so \
  --arm A=solver=/tmp/task5-v39-work/builds/A-native-system/libcertified_solver.so \
  --bundle-root task5-v39-corrected-verifier-20260926/input-bundles \
  --slots V31-025 V31-026 V31-027 --repetitions 31 --warmups 1 \
  --seed 2026093904 --timeout-seconds 30 \
  --checkpoint task5-v39-corrected-verifier-20260926/focused/timings/qualification.json

python -m task5v39.analysis qualification --configuration C1 \
  --input task5-v39-corrected-verifier-20260926/focused/timings/qualification.json \
  --expected-library L=303f03ca96d5262503e1c4b7b6bfede33758f30526a7a89566c37b088bba55ae \
  --expected-library M=c65f2fccc64b383b316c08a68fc9d566878537412de13e3cff7844da3223824c \
  --expected-library A=4794da8b7ce6ac626955e77bc45e9e02440f2cc470b3cb222503eb7adf6cd124 \
  --output task5-v39-corrected-verifier-20260926/focused/analysis/qualification.json \
  --samples 100000 --seed 2026093999 --integrity

python -m task5v39.audit \
  --input task5-v39-corrected-verifier-20260926/focused/timings/qualification.json \
  --schedule task5-v39-corrected-verifier-20260926/focused/schedule.json \
  --output task5-v39-corrected-verifier-20260926/focused/analysis/audit.json
```
