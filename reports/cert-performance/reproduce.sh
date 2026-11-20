#!/usr/bin/env bash
# From a checkout of the certificate-performance branch, on Linux.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
run=$(mktemp -d "${TMPDIR:-/tmp}/abs-cert-XXXXXX")
cpu=${CPU:-1}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 ABS_CERT_UNIQUE_THREADS=1
echo "Builds and raw measurements in $run"
git -C "$repo" worktree add --quiet --detach "$run/base" 361f068d9fa10b603e99ca12ccce6afe35784d90
git -C "$repo" worktree add --quiet --detach "$run/final" HEAD
for side in base final; do
    "$run/$side/build.sh" >"$run/$side-build.txt" 2>&1
done
(cd "$here/inputs" && sha256sum -c SHA256SUMS)
for set in primary holdout controls previous; do
    case "$set" in
        primary) cases=(t1 t2 t3) ;;
        holdout) cases=(th1 th2) ;;
        controls) cases=(w1 w2 w3 extreme square grouped grey defect conflict) ;;
        previous) cases=(previous_w2) ;;
    esac
    taskset -c "$cpu" python3 "$here/experiment.py" "$run/base" "$run/final" \
        "$run/$set.json" "${cases[@]}" --blocks 8
done
