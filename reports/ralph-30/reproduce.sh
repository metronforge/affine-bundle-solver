#!/usr/bin/env bash
# Run from a checkout of the published campaign branch.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
run=$(mktemp -d "${TMPDIR:-/tmp}/abs-ralph-XXXXXX")
cpu=${CPU:-1}
base=1df77461faf407320dab200d025fa846b2151502
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
echo "Measurements and detached build worktrees: $run"
git -C "$repo" worktree add --quiet --detach "$run/base" "$base"
git -C "$repo" worktree add --quiet --detach "$run/final" HEAD
"$run/base/build.sh" >"$run/base-build.log" 2>&1
"$run/final/build.sh" >"$run/final-build.log" 2>&1
for set in final holdout; do
    cases=(w1 w2 w3 extreme tall grouped square grey small)
    if [[ $set == holdout ]]; then cases=(hold1 hold2); fi
    taskset -c "$cpu" python3 "$here/bench.py" "$run/base" "$run/final" \
        "$run/$set.json" "${cases[@]}" --cache "$here/inputs" --blocks 8 --repeats 3
    python3 - "$run/$set.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert all(case["same"] for case in d["summary"].values()), "numerical mismatch"
PY
done
python3 "$here/summarize.py" "$run/final.json"
python3 "$here/summarize.py" "$run/holdout.json" hold1 hold2
