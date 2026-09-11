#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
out_dir=${1:-vectorization-report}
mkdir -p "$out_dir"
out_dir=$(cd "$out_dir" && pwd)

cc=${CC:-gcc}
optimized="$out_dir/optimized.txt"
missed="$out_dir/missed.txt"
summary="$out_dir/summary.txt"
hotspots="$out_dir/possible-strided-access.txt"
object="$out_dir/bsolver.vectorization.o"
raw="$out_dir/compiler.txt"

# This is observability for the fast router, not a change to the numerical
# contract.  The strict verifier is deliberately absent from this compile.
"$cc" -std=c11 -O3 -march=native -ffast-math -fopenmp -fPIC \
  -I"$repo_root/include" -I"$repo_root/src" -DABS_SCIPY_BLAS \
  -fopt-info-vec-all="$raw" \
  -c "$repo_root/src/bsolver.c" -o "$object"
rm -f "$object"

# Keep paths stable enough to compare reports from different runners.
sed -i "s|$repo_root/|./|g" "$raw"
grep "optimized:" "$raw" > "$optimized" || :
grep "missed:" "$raw" > "$missed" || :

optimized_count=$(grep -c "vectorized" "$optimized" || true)
missed_count=$(grep -c "missed:" "$missed" || true)
strided_count=$(grep -ciE "strided|not suitable for gather|complicated access pattern" "$missed" || true)
grep -iE "strided|not suitable for gather|complicated access pattern" \
  "$missed" > "$hotspots" || :

{
  echo "compiler=$($cc --version | head -1)"
  echo "optimized_loop_reports=$optimized_count"
  echo "missed_reports=$missed_count"
  echo "possible_strided_access_reports=$strided_count"
  echo
  echo "This report is diagnostic, not a performance gate."
  echo "Counts vary with compiler releases and runner CPUs."
  echo "Only src/bsolver.c (the fast router) is compiled with fast-math."
} > "$summary"

echo "vectorization report written to $out_dir"
